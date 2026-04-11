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

可选：初始化到指定 workspace（并写入配置默认 workspace）

```bash
agent-lab init -w "d:/workspace/ws01"
```

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

# 使用指定 workspace（不修改全局配置）
agent-lab chat -w "d:/workspace/ws01" "你好"

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

# 启动 memory 后台服务（持续运行）
agent-lab service start

# 仅执行一次待处理 memory 任务
agent-lab service once

# 前台运行 memory 服务（便于观察日志）
agent-lab service run

# 停止后台 memory 服务
agent-lab service stop
```

### 4.1 记忆系统说明（2026-04-07）

- 三层记忆：
  - 长期：`agent_identity.md`、`user.md`、`long_term.md`
  - 短期：`short_term.md`
  - 上下文窗口：最近 4 组对话
- 聊天时仅保留最近 4 组对话给主模型，历史部分进入后台整理任务。
- 记忆文件采用“合并重写”策略，不做简单追加。
- 默认包含安全解析兜底：若 memory 模型返回非标准 JSON，不会导致任务失败。

### 4.1.1 记忆整理提示词配置

- 记忆整理提示词已抽离到：`config/memory_organizer_prompt.md`
- 可直接修改该文件，调整“长期记忆判断、用户/agent 信息判断、短期压缩策略”。
- 若文件缺失，系统会回退到内置默认提示词。

### 4.2 日志说明

- 开启 `config.json` 根字段 `log: true` 后，所有 LLM 请求/响应都会写入工作区 `log/`。
- 日志包含：时间戳、请求类型、provider、model、base_url、payload。

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
- API/CLI 仅负责触发 memory 整理任务，具体整理由 `agent-lab service` 执行

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

## 参考文档

- `doc/SYSTEM_PROMPT_INJECTION.md` - 说明 system prompt 的注入内容与顺序

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

