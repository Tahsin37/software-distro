"""
LLM Manager — manages provider instances, API keys via secret store,
and supports provider presets (Ollama, OpenRouter, generic OpenAI-compat).
API keys are NEVER logged, exposed in events, or sent to the frontend.
"""
from typing import Optional
from llm.base import LLMProvider, LLMConfig
from llm.openai_compat import OpenAICompatibleProvider
from config import settings
from secret_store import secret_store


# Provider presets with sensible defaults
PROVIDER_PRESETS = {
    "ollama": {
        "display_name": "Ollama (Local)",
        "base_url": "http://localhost:11434",
        "api_key_required": False,
        "default_model": "qwen2.5:7b",
        "supports_vision": True,
        "supports_tool_calling": True,
        "supports_streaming": True,
    },
    "openrouter": {
        "display_name": "OpenRouter",
        "base_url": "https://openrouter.ai/api",
        "api_key_required": True,
        "default_model": "qwen/qwen3-235b-a22b",
        "supports_vision": True,
        "supports_tool_calling": True,
        "supports_streaming": True,
    },
    "openai": {
        "display_name": "OpenAI",
        "base_url": "https://api.openai.com",
        "api_key_required": True,
        "default_model": "gpt-4o",
        "supports_vision": True,
        "supports_tool_calling": True,
        "supports_streaming": True,
    },
    "custom": {
        "display_name": "Custom OpenAI-Compatible",
        "base_url": "http://localhost:8080",
        "api_key_required": False,
        "default_model": "default",
        "supports_vision": False,
        "supports_tool_calling": True,
        "supports_streaming": True,
    },
}


def create_provider(config: Optional[LLMConfig] = None) -> LLMProvider:
    """Create an LLM provider from configuration."""
    if config is None:
        # Load from settings + secret store
        api_key = secret_store.get(f"llm_api_key_{settings.llm_provider}", "")
        config = LLMConfig(
            provider=settings.llm_provider,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            context_size=settings.llm_context_size,
            max_output=settings.llm_max_output,
            timeout=settings.llm_timeout,
            api_key=api_key or None,
        )

    return OpenAICompatibleProvider(config)


class LLMManager:
    """Manages the active LLM provider. API keys stored securely, never exposed."""

    def __init__(self):
        self._provider: Optional[LLMProvider] = None
        self._config: Optional[LLMConfig] = None

    @property
    def provider(self) -> LLMProvider:
        if self._provider is None:
            self._provider = create_provider()
            self._config = self._provider.config
        return self._provider

    @property
    def config(self) -> LLMConfig:
        if self._config is None:
            self._config = LLMConfig(
                provider=settings.llm_provider,
                base_url=settings.llm_base_url,
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                context_size=settings.llm_context_size,
                max_output=settings.llm_max_output,
                timeout=settings.llm_timeout,
            )
        return self._config

    def get_config_safe(self) -> dict:
        """Get config for API response — never includes API key."""
        c = self.config
        return {
            "provider": c.provider,
            "base_url": c.base_url,
            "model": c.model,
            "temperature": c.temperature,
            "context_size": c.context_size,
            "max_output": c.max_output,
            "timeout": c.timeout,
            "api_key_set": secret_store.has(f"llm_api_key_{c.provider}"),
            "api_key_masked": secret_store.mask(secret_store.get(f"llm_api_key_{c.provider}", "")) if secret_store.has(f"llm_api_key_{c.provider}") else "",
        }

    def update_config(self, **kwargs) -> dict:
        """Update LLM configuration. API key stored separately in secret store."""
        # Handle API key separately — never in config dict
        api_key = kwargs.pop("api_key", None)
        provider_name = kwargs.get("provider", self.config.provider)

        if api_key is not None:
            if api_key == "":
                # Delete API key
                secret_store.delete(f"llm_api_key_{provider_name}")
            else:
                # Store encrypted
                secret_store.set(f"llm_api_key_{provider_name}", api_key)

        # Update non-secret config
        current = self.config.to_dict()
        current.update(kwargs)

        # Set API key from store for the new provider
        actual_key = secret_store.get(f"llm_api_key_{provider_name}", "")

        self._config = LLMConfig(**current, api_key=actual_key or None)
        self._provider = create_provider(self._config)
        return self.get_config_safe()

    def apply_preset(self, preset_name: str) -> dict:
        """Apply a provider preset (e.g., 'openrouter', 'ollama')."""
        preset = PROVIDER_PRESETS.get(preset_name)
        if not preset:
            raise ValueError(f"Unknown preset: {preset_name}")

        return self.update_config(
            provider=preset_name,
            base_url=preset["base_url"],
            model=preset["default_model"],
        )

    async def test(self) -> dict:
        """Test current provider connection. Redacts API key from errors."""
        try:
            result = await self.provider.test_connection()
            # Redact any API key from error messages
            api_key = secret_store.get(f"llm_api_key_{self.config.provider}", "")
            if api_key and result.get("error"):
                result["error"] = secret_store.redact_from_text(result["error"], [api_key])
            return result
        except Exception as e:
            api_key = secret_store.get(f"llm_api_key_{self.config.provider}", "")
            error_msg = str(e)
            if api_key:
                error_msg = secret_store.redact_from_text(error_msg, [api_key])
            return {"connected": False, "error": error_msg}

    async def list_models(self) -> list[str]:
        return await self.provider.list_models()

    def get_presets(self) -> dict:
        """Get available provider presets."""
        return PROVIDER_PRESETS


# Global LLM manager
llm_manager = LLMManager()
