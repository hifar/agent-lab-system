"""Provider factory and registry."""

from agent_lab.config.schema import Config
from agent_lab.providers.anthropic_compat import AnthropicCompatProvider
from agent_lab.providers.base import LLMProvider
from agent_lab.providers.openai_compat import OpenAICompatProvider


def create_provider(config: Config, model: str | None = None) -> LLMProvider:
    """Create an LLM provider based on configuration."""
    model_name = model or config.agents.defaults.model
    provider_name = config.agents.defaults.provider

    # Auto-detect provider from model name
    if provider_name == "auto":
        if model_name.startswith("claude"):
            provider_name = "anthropic"
        else:
            provider_name = "openai"

    # Get provider config
    if provider_name == "anthropic":
        prov_config = config.providers.anthropic
        model_name = model_name or "claude-3-5-sonnet-20241022"
        return AnthropicCompatProvider(
            api_key=prov_config.api_key or None,
            api_base=prov_config.api_base,
            default_model=model_name,
        )
    elif provider_name == "openai":
        prov_config = config.providers.openai
        model_name = model_name or "gpt-4o"
        return OpenAICompatProvider(
            api_key=prov_config.api_key or None,
            api_base=prov_config.api_base,
            default_model=model_name,
        )
    elif provider_name == "custom":
        prov_config = config.providers.custom
        return OpenAICompatProvider(
            api_key=prov_config.api_key or None,
            api_base=prov_config.api_base or "http://localhost:8000/v1",
            default_model=model_name,
        )
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
