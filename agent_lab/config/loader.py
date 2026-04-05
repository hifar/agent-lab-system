"""Configuration loading and management."""

import json
from pathlib import Path

from agent_lab.config.schema import Config


def get_default_config_path() -> Path:
    """Get default configuration file path."""
    return Path.home() / ".agent-lab" / "config.json"


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from file or return defaults."""
    path = config_path or get_default_config_path()

    config = Config()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            config = Config(**data)
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            print(f"Warning: Failed to load config from {path}: {e}")
            print("Using default configuration.")

    return config


def save_config(config: Config, config_path: Path | None = None) -> None:
    """Save configuration to file."""
    path = config_path or get_default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump(mode="json", by_alias=False)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
