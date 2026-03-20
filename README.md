# Vollama (Virtual Ollama)

> 将任意 OpenAI 兼容 API 转换为 Ollama 兼容 API 的轻量工具，并提供简单的接口管理

Vollama 是一个命令行工具，可以在本地启动一个服务端，将任何兼容 OpenAI 接口的大模型服务包装成 Ollama 兼容的 API 接口。完美解决那些只支持 Ollama 但不支持自定义 OpenAI API 的工具（比如 GitHub Copilot、Cursor 等）使用自定义模型的需求。

## 📦 安装

### 方法一：使用 uvx（推荐）

如果已经安装了 [uv](https://github.com/astral-sh/uv)，可以直接运行：

```bash
uvx vollama --help
```

## 🚀 快速开始

### 方式1：快速启动（简单模式）

直接指定上游 API 信息即可启动：

```bash
vollama run --api-key sk-xxx --base-url https://api.example.com/v1 --models "['qwen-max','gpt-4o']"
```

服务启动后，默认会在 `http://localhost:11434` 提供 Ollama 兼容 API，你可以在支持 Ollama 的工具中直接配置这个地址。

### 方式2：配置组管理（推荐）

对于需要使用多个上游服务的场景，推荐使用配置组管理：

1. **添加配置组**
   ```bash
   vollama config add my-openai --base-url https://api.openai.com/v1 --api-key sk-xxx
   ```
   添加时会自动从上游发现可用模型。

2. **查看所有配置组**
   ```bash
   vollama config list
   ```

3. **启动服务**
   ```bash
   vollama run --config my-openai
   ```

4. **设置默认配置组**
   ```bash
   vollama config use my-openai
   ```
   设置后可以直接用 `vollama run` 启动，不需要每次指定 `--config`。

## 📖 完整命令参考

### 基础命令

| 命令 | 说明 |
|------|------|
| `vollama run` | 启动 API 服务 |
| `vollama status` | 查看当前配置和状态 |
| `vollama --help` | 查看帮助信息 |

### 配置组管理

```bash
# 列出所有配置组
vollama config list

# 查看配置组详情
vollama config show <group-name>

# 添加新的配置组
vollama config add <group-name> --base-url <api-url> --api-key <key>

# 手动触发模型发现
vollama config discover <group-name>

# 设置默认配置组
vollama config use <group-name>
```

### 模型注册表管理

```bash
# 列出所有已知模型
vollama model list

# 添加/更新模型元数据
vollama model set <model-name> --context-length 128k --capability tools --capability vision --description "通义千问大模型"

# 删除模型
vollama model remove <model-name>
```

## ⚙️ 配置说明

### 配置文件路径

默认配置文件位于：
```bash
~/.config/vollama/config.toml   # 配置组信息
~/.config/vollama/models.toml   # 模型注册表信息
```

### 环境变量支持

你也可以使用 `.env` 文件配置参数：

```properties
# 基础配置
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.example.com/v1

# 服务配置
HOST=0.0.0.0
PORT=11434

# 模型配置
MODELS=["qwen-max","gpt-4o"]
CAPABILITIES=["vision","thinking"]
```

### 配置文件示例

`~/.config/vollama/config.toml` 示例：
```toml
default_config = "aliyun"

[groups.aliyun]
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
api_key = "sk-xxx"
auto_discover = true
model_names = ["qwen-max", "qwen-plus"]

[groups.deepseek]
base_url = "https://api.deepseek.com"
api_key = "sk-xxx"
auto_discover = true
```



## 📄 许可证

[MIT License](LICENSE.txt) © 2026 Czy014


