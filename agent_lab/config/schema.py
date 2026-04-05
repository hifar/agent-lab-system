"""Configuration schema using Pydantic."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from pydantic_settings import BaseSettings


class Base(BaseModel):
    """Base model accepting both camelCase and snake_case."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ProviderConfig(Base):
    """LLM provider configuration."""

    api_key: str = ""
    api_base: str | None = None
    extra_headers: dict[str, str] | None = None


class ProvidersConfig(Base):
    """Configuration for all LLM providers."""

    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    custom: ProviderConfig = Field(default_factory=ProviderConfig)


class AgentDefaults(Base):
    """Default agent configuration."""

    model: str = "gpt-4o"
    provider: str = "auto"  # "openai", "anthropic", or "auto"
    max_tokens: int = 4096
    temperature: float = 0.7
    max_iterations: int = 20
    enable_think_mode: bool = False
    enable_streaming_mode: bool = False
    workspace: str = "~/.agent-lab/workspace"


class AgentsConfig(Base):
    """Agent configuration."""

    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class ToolsConfig(Base):
    """Tools configuration."""

    enable_read_file: bool = True
    enable_write_file: bool = True
    enable_list_dir: bool = True


class Config(BaseSettings):
    """Root configuration."""

    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)

    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agents.defaults.workspace).expanduser()
