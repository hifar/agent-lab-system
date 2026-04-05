# QUICKSTART.md

## 快速开始指南

### 1. 安装

```bash
# 从项目目录安装
pip install -e .
```

### 2. 初始化工作区

```bash
agent-lab init
```

这会创建：
- `~/.agent-lab/config.json` - 配置文件
- `~/.agent-lab/workspace/` - 工作目录及其子文件夹

### 3. 配置 API 密钥

编辑 `~/.agent-lab/config.json`：

**OpenAI 示例：**
```json
{
  "providers": {
    "openai": {
      "api_key": "sk-..."
    }
  },
  "agents": {
    "defaults": {
      "model": "gpt-4o",
      "provider": "auto"
    }
  }
}
```

**Anthropic 示例：**
```json
{
  "providers": {
    "anthropic": {
      "api_key": "sk-ant-..."
    }
  },
  "agents": {
    "defaults": {
      "model": "claude-3-5-sonnet-20241022",
      "provider": "anthropic"
    }
  }
}
```

也可以直接参考项目内模板：

- `config/config.json`
- `config/agent.md`
- `config/workspace/`

### 4. 基本命令

```bash
# 查看配置
agent-lab config show

# 列出可用工具
agent-lab tools-list

# 单次聊天
agent-lab chat "What's in the current directory?"

# 交互式聊天（多轮对话）
agent-lab chat

# 使用特定模型
agent-lab chat -m "gpt-4-turbo" "Your message here"

# 使用特定会话
agent-lab chat -s "session-name" "Your message"

# 启用 think 模式
agent-lab chat --think "帮我分析这个设计方案"

# 显式切换 streaming 模式（CLI 会增量输出）
agent-lab chat --streaming "给我一个 Python 示例"

# 启动 OpenAI 兼容 API 服务
agent-lab api --host 127.0.0.1 --port 8000
```

### 5. 通过 OpenAI 协议调用 Agent

服务启动后，可以通过 OpenAI Chat Completions 协议调用：

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.5-flash",
    "messages": [
      {"role": "system", "content": "You are helpful."},
      {"role": "user", "content": "帮我看看当前目录里有什么"}
    ],
    "think_mode": true,
    "streaming_mode": false,
    "temperature": 0.3,
    "max_tokens": 800
  }'
```

可用端点：
- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`

当前限制：
- CLI `--streaming` 已支持增量显示（OpenAI 兼容与 Anthropic provider）
- API 的 `streaming_mode` / `stream` 目前仍返回非流式一次性 JSON
- 暂不支持请求体传入 `tools`（使用本地已配置内置工具）

## 架构概览

```
agent-lab/
├── config/              # 配置系统
│   ├── schema.py       # Pydantic 模型
│   └── loader.py       # 加载/保存
├── providers/          # LLM 提供商
│   ├── base.py         # 基类
│   ├── openai_compat.py    # OpenAI 兼容实现
│   ├── anthropic_compat.py # Anthropic 实现
│   └── factory.py       # 工厂函数
├── tools/              # 工具系统
│   ├── base.py         # 工具基类
│   ├── registry.py      # 工具注册表
│   └── builtin.py       # 内置工具
├── agent/              # Agent 循环
│   └── __init__.py      # Agent 主类
├── api/                # OpenAI 兼容 API
│   ├── __init__.py
│   └── server.py        # FastAPI 服务
├── workspace/          # 工作区管理
│   └── __init__.py
├── skills/             # 技能管理
│   └── __init__.py
├── context.py          # 上下文构建
├── session.py          # 会话管理
└── cli.py              # CLI 入口
```

## 内置工具

### read_file
读取文件内容

```
read_file(path: str) -> str
```

### write_file
写入文件

```
write_file(path: str, content: str) -> str
```

### list_dir
列出目录内容

```
list_dir(path: str = ".") -> str
```

## 扩展

### 添加自定义工具

```python
from agent_lab.tools import Tool

class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    @property
    def description(self) -> str:
        return "Description of my tool"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string"}
            },
            "required": ["param1"]
        }
    
    async def execute(self, param1: str) -> str:
        return f"Result: {param1}"

# 使用
from agent_lab.tools import ToolRegistry
registry = ToolRegistry()
registry.register(MyTool())
```

### 创建自定义提供商

```python
from agent_lab.providers import LLMProvider, LLMResponse

class MyProvider(LLMProvider):
    async def chat(self, messages, tools=None, **kwargs) -> LLMResponse:
        # 实现你的提供商逻辑
        return LLMResponse(content="Hello!")
```

## 环境变量

- `OPENAI_API_KEY` - OpenAI API 密钥
- `ANTHROPIC_API_KEY` - Anthropic API 密钥
- `AGENT_LAB_WORKSPACE` - 覆盖工作区路径

## 故障排除

### "Configuration not found"
运行 `agent-lab init` 初始化工作区

### "API key not configured"
1. 检查 `~/.agent-lab/config.json`
2. 设置对应提供商的 `api_key`

### API 调用返回 400
1. 检查 `model` 是否是当前 provider 支持的模型
2. 检查 `messages` 是否至少包含一条 user 消息
3. 如果使用 DashScope/OpenAI 兼容网关，确认 `api_base` 和 `extra_headers` 正确

### 模型不可用
检查配置中的 `model` 字段，确保与提供商兼容

## 支持的模型

**OpenAI:**
- gpt-4o
- gpt-4-turbo
- gpt-3.5-turbo

**Anthropic:**
- claude-3-5-sonnet-20241022
- claude-3-opus-20240229
- claude-3-haiku-20240307

## 下一步

1. 查看 [README.md](README.md) 了解更多细节
2. 创建自定义工具扩展功能
3. 添加技能到 `~/.agent-lab/workspace/skills/`
4. 尝试多工具链式调用

