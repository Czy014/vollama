# Oai2Ollama

This is a CLI tool that starts a server that wraps an OpenAI-compatible API and expose an Ollama-compatible API,
which is useful for providing custom models for coding agents that don't support custom OpenAI APIs but do support Ollama
(like GitHub Copilot for VS Code).

## Usage

### with Python

You can run directly via `uvx` (if you have `uv` installed) or `pipx`:

```sh
uvx oai2ollama --help
```

常用命令：

```sh
oai2ollama status
oai2ollama config list
oai2ollama config add demo --base-url https://example.com/v1 --api-key sk-xxx
oai2ollama config discover demo
oai2ollama run --config demo
```

模型仓库命令：

```sh
oai2ollama model list
oai2ollama model set my-model --context-length 128k --capability tools --capability vision
oai2ollama model remove my-model
```

配置文件默认位于：

```text
~/.config/oai2ollama/config.toml
~/.config/oai2ollama/models.toml
```

仍兼容旧参数（会自动映射到 `run`）：

```sh
oai2ollama --api-key sk-xxx --base-url https://example.com/v1 --models "['custom-model']"
```

也可以使用 `.env` 文件：

```properties
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=your_base_url
HOST=0.0.0.0
CAPABILITIES=["vision","thinking"]
MODELS=["custom-model1","custom-model2"]
```

> [!WARNING]
> The option name `capacities` is deprecated. Use `capabilities` instead. The old name still works for now but will emit a deprecation warning.

### with Docker

First, build the image:

```sh
docker build -t oai2ollama .
```

Then, run the container with your credentials:

```sh
docker run -p 11434:11434 \
  -e OPENAI_API_KEY="your_api_key" \
  -e OPENAI_BASE_URL="your_base_url" \
  oai2ollama
```

Or you can pass these as command line arguments:

```sh
docker run -p 11434:11434 oai2ollama --api-key your_api_key --base-url your_base_url
```

To have the server listen on a different host, like all IPv6 interfaces, use the `--host` argument:

```sh
docker run -p 11434:11434 oai2ollama --host "::"
```
