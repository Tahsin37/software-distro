"""
OpenAI-compatible LLM provider — works with Ollama, LM Studio, vLLM,
and any server that implements the OpenAI chat completions API.
"""
import json
import aiohttp
from typing import AsyncIterator, Optional
from llm.base import LLMProvider, LLMConfig, LLMMessage, LLMResponse, StreamChunk


class OpenAICompatibleProvider(LLMProvider):
    """
    Provider for any OpenAI-compatible API endpoint.
    This is the primary provider — Ollama, LM Studio, and others expose this API.
    """

    def _get_base_url(self) -> str:
        url = self.config.base_url.rstrip("/")
        # Ollama uses /v1 prefix for OpenAI compat
        if "11434" in url and "/v1" not in url:
            url += "/v1"
        return url

    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _build_request(
        self,
        messages: list[LLMMessage],
        tools: Optional[list[dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> dict:
        body = {
            "model": self.config.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_output,
            "stream": stream,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        return body

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: Optional[list[dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        url = f"{self._get_base_url()}/chat/completions"
        body = self._build_request(messages, tools, temperature, max_tokens, stream=False)

        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=body, headers=self._get_headers()) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise ConnectionError(f"LLM API error {resp.status}: {text}")

                data = await resp.json()
                choice = data["choices"][0]
                message = choice["message"]

                return LLMResponse(
                    content=message.get("content"),
                    tool_calls=message.get("tool_calls"),
                    finish_reason=choice.get("finish_reason"),
                    usage=data.get("usage"),
                )

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        tools: Optional[list[dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[StreamChunk]:
        url = f"{self._get_base_url()}/chat/completions"
        body = self._build_request(messages, tools, temperature, max_tokens, stream=True)

        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=body, headers=self._get_headers()) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise ConnectionError(f"LLM API error {resp.status}: {text}")

                # Accumulate tool calls across chunks
                accumulated_tool_calls = {}

                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        yield StreamChunk(done=True)
                        return

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    if not data.get("choices"):
                        continue

                    choice = data["choices"][0]
                    delta = choice.get("delta", {})
                    finish_reason = choice.get("finish_reason")

                    # Handle streamed content
                    content = delta.get("content")

                    # Handle streamed tool calls
                    tool_calls_delta = delta.get("tool_calls")
                    if tool_calls_delta:
                        for tc in tool_calls_delta:
                            idx = tc.get("index", 0)
                            if idx not in accumulated_tool_calls:
                                accumulated_tool_calls[idx] = {
                                    "id": tc.get("id", f"call_{idx}"),
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            if tc.get("id"):
                                accumulated_tool_calls[idx]["id"] = tc["id"]
                            func = tc.get("function", {})
                            if func.get("name"):
                                accumulated_tool_calls[idx]["function"]["name"] = func["name"]
                            if func.get("arguments"):
                                accumulated_tool_calls[idx]["function"]["arguments"] += func["arguments"]

                    if finish_reason:
                        final_tool_calls = list(accumulated_tool_calls.values()) if accumulated_tool_calls else None
                        yield StreamChunk(
                            content=content,
                            tool_calls=final_tool_calls,
                            finish_reason=finish_reason,
                            done=True,
                        )
                        return

                    if content:
                        yield StreamChunk(content=content)

    async def test_connection(self) -> dict:
        """Test connection to the LLM API."""
        try:
            url = f"{self._get_base_url()}/models"
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=self._get_headers()) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = [m.get("id", m.get("name", "unknown")) for m in data.get("data", data.get("models", []))]
                        return {"connected": True, "models": models}
                    else:
                        return {"connected": False, "error": f"HTTP {resp.status}"}
        except aiohttp.ClientConnectorError:
            return {"connected": False, "error": "Cannot connect to LLM API. Is the server running?"}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    async def list_models(self) -> list[str]:
        result = await self.test_connection()
        return result.get("models", [])
