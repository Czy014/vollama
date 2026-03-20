import httpx

from .config import ConfigGroup


async def discover_models(group: ConfigGroup) -> list[str]:
    """Discover models from an upstream OpenAI-compatible API"""
    if not group.auto_discover:
        return group.model_names

    try:
        async with httpx.AsyncClient(base_url=str(group.base_url), headers={"Authorization": f"Bearer {group.api_key}"}, http2=True, timeout=30.0) as client:
            # Keep relative paths first so providers with path-prefixed base_url work,
            # e.g. https://host/api/coding/v3 + models -> /api/coding/v3/models.
            for endpoint in ("api/tags", "/api/tags"):
                response = await client.get(endpoint)
                if response.status_code == 200:
                    data = response.json()
                    models = [m["name"] for m in data.get("models", [])]
                    if models:
                        return models

            for endpoint in ("models", "/models"):
                response = await client.get(endpoint)
                if response.status_code == 200:
                    data = response.json()
                    models = [m["id"] for m in data.get("data", [])]
                    if models:
                        return models

            return group.model_names

    except Exception as e:
        print(f"  Warning: failed to discover models from {group.base_url}: {e}", flush=True)
        return group.model_names
