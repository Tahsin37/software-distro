"""
LLM provider abstraction — supports Ollama, OpenAI-compatible APIs, and local HTTP.
Provider-agnostic interface for streaming, tool calling, and model discovery.
"""
import json
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional, Any
from enum import Enum


@dataclass
class LLMMessage:
    role: str  # system, user, assistant, tool
    content: Optional[str] = None
    tool_calls: Optional[list[dict]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None  # tool name for tool role messages

    def to_dict(self) -> dict:
        d = {"role": self.role}
        if self.content is not None:
            d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d


@dataclass
class LLMConfig:
    provider: str = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:7b"
    temperature: float = 0.1
    context_size: int = 8192
    max_output: int = 4096
    timeout: int = 120
    api_key: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "temperature": self.temperature,
            "context_size": self.context_size,
            "max_output": self.max_output,
            "timeout": self.timeout,
        }


@dataclass
class LLMResponse:
    content: Optional[str] = None
    tool_calls: Optional[list[dict]] = None
    finish_reason: Optional[str] = None
    usage: Optional[dict] = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


@dataclass
class StreamChunk:
    """A chunk from a streaming response."""
    content: Optional[str] = None
    tool_calls: Optional[list[dict]] = None
    finish_reason: Optional[str] = None
    done: bool = False


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        tools: Optional[list[dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Send a chat completion request."""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[LLMMessage],
        tools: Optional[list[dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Send a streaming chat completion request."""
        ...

    @abstractmethod
    async def test_connection(self) -> dict:
        """Test if the LLM provider is reachable and working."""
        ...

    async def list_models(self) -> list[str]:
        """List available models. Not all providers support this."""
        return []
