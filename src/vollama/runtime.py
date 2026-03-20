from functools import lru_cache

from .config import Settings
from .model_registry import ModelRegistry


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_model_registry() -> ModelRegistry:
    return ModelRegistry()
