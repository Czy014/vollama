from urllib.parse import urljoin

import httpx

from .config import ConfigGroup


async def discover_models(group: ConfigGroup) -> list[str]:
    """Discover models from an upstream OpenAI-compatible API"""
    if not group.auto_discover:
        return group.model_names

    try:
        async with httpx.AsyncClient(http2=True, timeout=30.0) as client:
            # Try Ollama /api/tags endpoint first
            response = await client.get(urljoin(str(group.base_url), "/api/tags"), headers={"Authorization": f"Bearer {group.api_key}"})
            if response.status_code == 200:
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
                if models:
                    return models

            # Fallback to OpenAI /models endpoint
            response = await client.get(urljoin(str(group.base_url), "/models"), headers={"Authorization": f"Bearer {group.api_key}"})
            if response.status_code == 200:
                data = response.json()
                models = [m["id"] for m in data.get("data", [])]
                return models

            return group.model_names

    except Exception as e:
        print(f"  Warning: failed to discover models from {group.base_url}: {e}", flush=True)
        return group.model_names
