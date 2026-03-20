from fastapi import Depends, FastAPI, Request
from fastapi.responses import StreamingResponse

from .runtime import get_model_registry, get_settings

app = FastAPI()


@Depends
async def _new_client():
    from httpx import AsyncClient

    active_config = get_settings().get_active_config()

    async with AsyncClient(base_url=str(active_config.base_url), headers={"Authorization": f"Bearer {active_config.api_key}"}, timeout=60, http2=True, follow_redirects=True) as client:
        yield client


@app.get("/api/tags")
async def models(client=_new_client):
    active_config = get_settings().get_active_config()
    res = await client.get("/models")
    res.raise_for_status()
    try:
        data = res.json()["data"]
    except (KeyError, TypeError):
        data = []
    models_map = {i["id"]: {"name": i["id"], "model": i["id"]} for i in data} | {i: {"name": i, "model": i} for i in active_config.extra_models}

    # Add models from config group model_names list
    for model_name in active_config.model_names:
        models_map[model_name] = {"name": model_name, "model": model_name}

    return {"models": list(models_map.values())}


@app.post("/api/show")
async def show_model(request: Request):
    data = await request.json()
    model = data.get("model")
    model_info: dict[str, str | int] = {"general.architecture": "CausalLM"}
    active_config = get_settings().get_active_config()

    # Get model config from registry with group overrides
    if model:
        model_config = get_model_registry().get_model_config(model, active_config.model_overrides)
        context_length = model_config.get("context_length", 8000)
        if not isinstance(context_length, int):
            context_length = 8000

        capabilities_raw = model_config.get("capabilities", ["completion"])
        capabilities = [cap for cap in capabilities_raw if isinstance(cap, str)] if isinstance(capabilities_raw, list) else ["completion"]

        model_info["general.architecture"] = model
        model_info[model + ".context_length"] = context_length
    else:
        capabilities = ["completion"]

    return {
        "model_info": model_info,
        "capabilities": ["completion", *capabilities],
    }


@app.get("/v1/models")
async def list_models(client=_new_client):
    res = await client.get("/models")
    res.raise_for_status()
    return res.json()


@app.post("/v1/chat/completions")
async def chat_completions(request: Request, client=_new_client):
    data = await request.json()

    if data.get("stream", False):

        async def stream():
            async with client.stream("POST", "/chat/completions", json=data) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk

        return StreamingResponse(stream(), media_type="text/event-stream")

    else:
        res = await client.post("/chat/completions", json=data)
        res.raise_for_status()
        return res.json()


@app.get("/api/version")
async def ollama_version():
    return {"version": "0.12.10"}
