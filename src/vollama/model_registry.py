import tomllib
from sys import stderr
from typing import Literal, TypedDict

from .config import MODEL_REGISTRY_FILE, ModelRegistryEntry
from .toml_io import to_toml_str


class ModelInfo(TypedDict):
    context_length: int
    capabilities: list[Literal["tools", "vision", "insert", "embedding", "thinking", "completion"]]


BUILTIN_MODELS: dict[str, ModelInfo] = {
    "gpt-4o": {"context_length": 128000, "capabilities": ["tools", "vision"]},
    "gpt-4o-mini": {"context_length": 128000, "capabilities": ["tools", "vision"]},
    "gpt-4-turbo": {"context_length": 128000, "capabilities": ["tools", "vision"]},
    "gpt-4": {"context_length": 8192, "capabilities": ["tools"]},
    "gpt-3.5-turbo": {"context_length": 16384, "capabilities": ["tools"]},
    "gpt-3.5-turbo-16k": {"context_length": 16384, "capabilities": ["tools"]},
    "claude-3-opus": {"context_length": 200000, "capabilities": ["tools", "vision"]},
    "claude-3-sonnet": {"context_length": 200000, "capabilities": ["tools", "vision"]},
    "claude-3-haiku": {"context_length": 200000, "capabilities": ["tools", "vision"]},
    "claude-2.1": {"context_length": 200000, "capabilities": ["tools"]},
    "doubao-seed-2-0-pro-260215": {"context_length": 256000, "capabilities": ["tools", "vision"]},
    "doubao-seed-2-0-code-preview-260215": {"context_length": 256000, "capabilities": ["tools"]},
    "doubao-1.5-pro": {"context_length": 128000, "capabilities": ["tools", "vision"]},
    "doubao-lite-4k": {"context_length": 4096, "capabilities": ["tools"]},
    "doubao-lite-32k": {"context_length": 32768, "capabilities": ["tools"]},
    "doubao-lite-128k": {"context_length": 128000, "capabilities": ["tools"]},
    "llama3:8b": {"context_length": 8192, "capabilities": ["tools"]},
    "llama3:70b": {"context_length": 8192, "capabilities": ["tools"]},
    "llama3.1:8b": {"context_length": 128000, "capabilities": ["tools"]},
    "llama3.1:70b": {"context_length": 128000, "capabilities": ["tools"]},
    "llama3.1:405b": {"context_length": 128000, "capabilities": ["tools"]},
    "mistral-large": {"context_length": 128000, "capabilities": ["tools"]},
    "mistral-medium": {"context_length": 32768, "capabilities": ["tools"]},
    "mistral-small": {"context_length": 32768, "capabilities": ["tools"]},
}


def _flatten_model_registry_data(raw: dict) -> dict[str, dict]:
    flattened: dict[str, dict] = {}
    entry_fields = {"context_length", "capabilities", "description"}

    def walk(prefix: str, value):
        if not isinstance(value, dict):
            return

        if any(field in value for field in entry_fields):
            flattened[prefix] = {key: value[key] for key in ("context_length", "capabilities", "description") if key in value}
            return

        for key, nested in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            walk(next_prefix, nested)

    for key, value in raw.items():
        walk(str(key), value)

    return flattened


class ModelRegistry:
    """Global model registry that combines built-in and user-defined metadata."""

    def __init__(self):
        self.builtin = BUILTIN_MODELS
        self.user_defined: dict[str, ModelRegistryEntry] = {}
        self.reload()

    def _ensure_registry_file(self):
        if MODEL_REGISTRY_FILE.exists():
            return
        try:
            MODEL_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with MODEL_REGISTRY_FILE.open("w", encoding="utf-8") as f:
                f.write(to_toml_str({}))
        except Exception as err:
            print(f"\n  Warning: failed to create model registry file: {err}\n", file=stderr)

    def reload(self):
        self.user_defined = {}
        self._ensure_registry_file()
        if MODEL_REGISTRY_FILE.exists():
            try:
                with MODEL_REGISTRY_FILE.open("rb") as f:
                    model_data = tomllib.load(f)
                if not isinstance(model_data, dict):
                    return

                flattened = _flatten_model_registry_data(model_data)
                for name, entry in flattened.items():
                    try:
                        self.user_defined[name] = ModelRegistryEntry(**entry)
                    except Exception as entry_err:
                        print(f"\n  Warning: invalid model registry entry '{name}': {entry_err}\n", file=stderr)
            except Exception as err:
                print(f"\n  Warning: failed to load model registry: {err}\n", file=stderr)

    def get_model_config(self, model_name: str, group_overrides: dict[str, dict] | None = None) -> dict[str, int | list[str] | str | None]:
        config: dict[str, int | list[str] | str | None] = {
            "context_length": 32768,
            "capabilities": ["completion"],
        }

        if model_name in self.builtin:
            builtin_entry = self.builtin[model_name]
            config["context_length"] = builtin_entry["context_length"]
            config["capabilities"] = list(builtin_entry["capabilities"])

        if model_name in self.user_defined:
            config.update(self.user_defined[model_name].model_dump(exclude_none=True))

        if group_overrides and model_name in group_overrides:
            config.update(group_overrides[model_name])

        return config
