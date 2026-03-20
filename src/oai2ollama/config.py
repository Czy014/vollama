import re
import tomllib
from pathlib import Path
from sys import stderr
from typing import Literal, Self

from platformdirs import user_config_dir
from pydantic import Field, HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, CliSuppress

# Configuration directory setup
CONFIG_DIR = Path(user_config_dir("oai2ollama", appauthor=False))
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "config.toml"
MODEL_REGISTRY_FILE = CONFIG_DIR / "models.toml"


class InvalidContextLengthError(ValueError):
    def __init__(self):
        super().__init__("invalid context length")


class ConfigGroupNotFoundError(ValueError):
    def __init__(self, name: str, available: list[str]):
        super().__init__(f"Configuration group '{name}' not found. Available groups: {', '.join(available)}")


class NoConfigGroupError(ValueError):
    def __init__(self):
        super().__init__("No configuration groups found. Please add one using `oai2ollama config add ...`.")


def _parse_context_length(value: int | str) -> int:
    """Parse context length with support for k/m suffixes"""
    if isinstance(value, int):
        return value

    parsed = re.fullmatch(r"\s*(\d+)\s*([kKmM]?)\s*", value)
    if not parsed:
        raise InvalidContextLengthError

    amount = int(parsed.group(1))
    suffix = parsed.group(2).lower()
    if suffix == "k":
        return amount * 1000
    if suffix == "m":
        return amount * 1000 * 1000
    return amount


class ConfigGroup(BaseSettings):
    """Represents a single upstream service configuration group"""

    base_url: HttpUrl
    api_key: str
    auto_discover: bool = True
    model_names: list[str] = Field(default_factory=list)
    extra_models: list[str] = Field(default_factory=list, description="Extra models to include in the /api/tags response")
    model_overrides: dict[str, dict] = Field(default_factory=dict, description="Per-model configuration overrides for this group")

    @model_validator(mode="after")
    def merge_extra_models(self: Self) -> Self:
        """Merge extra_models into model_names, deduplicate"""
        all_models = list(dict.fromkeys(self.model_names + self.extra_models))
        self.model_names = all_models
        return self


class ModelRegistryEntry(BaseSettings):
    """Entry in the global model registry"""

    context_length: int = Field(default=8000, description="Model context window size")
    capabilities: list[Literal["tools", "insert", "vision", "embedding", "thinking", "completion"]] = Field(default_factory=list)
    description: str | None = None


class Settings(BaseSettings):
    model_config = {
        "cli_parse_args": False,  # Disable pydantic CLI parsing, use typer instead
        "env_file": ".env",
        "extra": "ignore",
    }

    # Legacy top-level parameters (for backward compatibility, map to default config group)
    api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY", description="API key for authentication (for default configuration)")
    base_url: HttpUrl | None = Field(default=None, validation_alias="OPENAI_BASE_URL", description="Base URL for the OpenAI-compatible API (for default configuration)")
    capacities: CliSuppress[list[Literal["tools", "insert", "vision", "embedding", "thinking"]]] = Field([], repr=False)
    capabilities: CliSuppress[list[Literal["tools", "insert", "vision", "embedding", "thinking"]]] = Field([], repr=False)
    extra_models: CliSuppress[list[str]] = Field([], repr=False, alias="models")
    context_lengths: CliSuppress[dict[str, int]] = Field({}, repr=False)

    # Global configuration
    host: str = Field("localhost", description="IP / hostname for the API server")
    port: int = Field(11434, description="Port for the API server")
    default_config: str | None = Field(None, description="Default configuration group to use")

    # Runtime parameter (not persisted)
    config: str | None = Field(None, description="Configuration group to use for this run")
    config_groups: dict[str, ConfigGroup] = Field(default_factory=dict, exclude=True)

    @field_validator("context_lengths", mode="before")
    @classmethod
    def _parse_context_lengths(cls, value):
        if not isinstance(value, dict):
            return value
        return {k: _parse_context_length(v) for k, v in value.items()}

    @model_validator(mode="after")
    def load_config_groups(self: Self) -> Self:
        """Load configuration groups from local config file, and merge with command line/env parameters"""
        # Load existing config from file
        self.config_groups = {}
        if CONFIG_FILE.exists():
            try:
                with CONFIG_FILE.open("rb") as f:
                    config_data = tomllib.load(f)

                file_default_config = config_data.get("default_config")
                if isinstance(file_default_config, str):
                    self.default_config = file_default_config

                for name, group_data in config_data.get("groups", {}).items():
                    if isinstance(group_data, dict):
                        model_overrides = group_data.get("model_overrides")
                        if isinstance(model_overrides, dict):
                            # Recover from older malformed TOML that wrote default_config
                            # inside model_overrides as a plain string value.
                            misplaced_default = model_overrides.get("default_config")
                            if self.default_config is None and isinstance(misplaced_default, str):
                                self.default_config = misplaced_default

                            group_data["model_overrides"] = {k: v for k, v in model_overrides.items() if isinstance(v, dict)}

                    self.config_groups[name] = ConfigGroup(**group_data)
            except Exception as e:
                print(f"\n  Warning: failed to load config file: {e}\n", file=stderr)

        # Merge command line/env parameters into default group
        if self.base_url and self.api_key:
            default_group = self.config_groups.get(
                "default",
                ConfigGroup(
                    base_url=self.base_url,
                    api_key=self.api_key,
                    extra_models=self.extra_models,
                ),
            )
            # Update with command line values
            if self.base_url:
                default_group.base_url = self.base_url
            if self.api_key:
                default_group.api_key = self.api_key
            if self.extra_models:
                default_group.extra_models.extend(self.extra_models)
            self.config_groups["default"] = default_group

            # Merge legacy context lengths into model overrides
            for model, length in self.context_lengths.items():
                if model not in default_group.model_overrides:
                    default_group.model_overrides[model] = {}
                default_group.model_overrides[model]["context_length"] = length

        # Handle legacy capacities warning
        if self.capacities:
            print("\n  Warning: 'capacities' is a previous typo, please use 'capabilities' instead.\n", file=stderr)
            self.capabilities.extend(self.capacities)

        # Merge legacy capabilities into default group model overrides (apply to all models)
        if self.capabilities and "default" in self.config_groups:
            default_group = self.config_groups["default"]
            for model in default_group.model_names:
                if model not in default_group.model_overrides:
                    default_group.model_overrides[model] = {}
                if "capabilities" not in default_group.model_overrides[model]:
                    default_group.model_overrides[model]["capabilities"] = []
                default_group.model_overrides[model]["capabilities"].extend(self.capabilities)

        return self

    def get_active_config(self) -> ConfigGroup:
        """Get the currently active configuration group"""
        config_name = self.config if self.config is not None else self.resolve_default_config_name()
        if config_name not in self.config_groups:
            raise ConfigGroupNotFoundError(config_name, list(self.config_groups.keys()))
        return self.config_groups[config_name]

    def resolve_default_config_name(self) -> str:
        if self.default_config is not None:
            return self.default_config
        if self.config_groups:
            return next(iter(self.config_groups))
        raise NoConfigGroupError


# Do NOT initialize at import time, let CLI handle it
__all__ = [
    "CONFIG_DIR",
    "CONFIG_FILE",
    "MODEL_REGISTRY_FILE",
    "ConfigGroup",
    "ConfigGroupNotFoundError",
    "InvalidContextLengthError",
    "ModelRegistryEntry",
    "NoConfigGroupError",
    "Settings",
    "_parse_context_length",
]
