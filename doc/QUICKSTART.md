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
  "api_auth": false,
  "api_keys": ["<YOUR_AGENT_LAB_API_KEY>"],
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
  "api_auth": false,
  "api_keys": ["<YOUR_AGENT_LAB_API_KEY>"],
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

# 使用共享 background 目录（注入该目录下全部 .md 到 system prompt，位于 memory 之前）
agent-lab chat -b "d:/shared/background" "请基于背景设定继续剧情"

# 强制重建本轮 system prompt（默认不重建）
agent-lab chat -rb -b "d:/shared/background" "请重新按新背景回答"

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

# 启动轻量 Web 聊天界面（默认连接上面的 API）
agent-lab web --host 127.0.0.1 --port 7860 --api-base http://127.0.0.1:8000

# 启动 memory 后台服务（持续运行）
agent-lab service start

# 默认扫描所有已注册 workspace 并处理各自 memory 队列
agent-lab service run

# 如需只处理某个 workspace，也可以显式指定
agent-lab service run -w "d:/workspace/ws01"

# 仅执行一次待处理 memory 任务
agent-lab service once

# 前台运行 memory 服务（便于观察日志）
agent-lab service run

# 停止后台 memory 服务
agent-lab service stop
```

### 4.4 Web UI 使用说明

`agent-lab web` 提供一个轻量浏览器聊天界面，适合本地调试和演示。

- 访问地址：`http://127.0.0.1:7860`
- 左侧参数支持：`api_base`、`api_key`、`model`、`workspace`、`session`、`background`、`session_mode`
- 聊天体验：SSE 流式输出、Enter 发送、Shift+Enter 换行、Stop 中断、Clear 清空

实现说明：

- 页面模板位于：`agent_lab/web/templates/index.html`
- Python 端在运行时读取模板并注入默认配置（不是硬编码 HTML）
- UI 字体使用本地系统字体栈，不依赖 `fonts.googleapis.com` 远程资源

常见排查：

1. 修改模板后请重启 `agent-lab web` 并强刷浏览器（Ctrl+F5）。
2. `api_base` 推荐填写 `http://127.0.0.1:8000`（无需手动拼接 `/v1/chat/completions`）。
3. 若启用了 API 鉴权，请在页面中填写 `api_key`。

### 4.1 记忆系统说明（2026-04-12 优化版）

记忆架构采用**三层隔离 + session-local compression** 设计：

**三层记忆职责明确分工：**
- **短期记忆 (short_term_{session_id}.md)**: 
  - **职责**：压缩当前session的对话内容
  - **更新频率**：每次整理任务都重写（覆盖，不合并其他session）
  - **特点**：session间完全隔离，自动清理跨session污染
  
- **用户档案 (user.md)**:
  - **职责**：沉淀用户偏好、背景、身份、工作风格
  - **更新频率**：高频率（任何相关信息都积极更新）
  - **特点**：跨session累积，增量补充而非保守替换
  
- **Agent身份 (agent_identity.md)**:
  - **职责**：记录agent的能力范围、工作方式、约束边界
  - **更新频率**：高频率（任何相关信息都积极更新）
  - **特点**：跨session学习，逐次完善agent的行为模式

- **长期记忆 (long_term.md)**:
  - **职责**：储存跨session的稳定事实、规则、架构决策、通用约束
  - **更新频率**：中等（只记录真正普遍适用的信息）
  - **特点**：高度审慎，仅在信息明确有持久价值时更新

**关键改进点：**

1. **短期记忆隔离** 
   - 旧版：全局shared short_term.md，多个session混淆
   - 新版：每个session独立的 `short_term_{session_id}.md`，完全隔离

2. **用户/Agent信息积极更新**
   - 旧版：需要LLM返回 `should_update_user=true` 才更新，容易遗漏
   - 新版：LLM返回的merged内容直接写入，无条件更新，增强实时学习能力

3. **提示词引导改进**
   - 旧版："偏积极但仍需确定"，模糊不清
   - 新版：明确告诉LLM各层职责，以及user/agent需积极合并

**整理逻辑流程：**
1. 当chat/API会话超过4个user turn时，触发后台整理任务
2. 整理时同时处理4层记忆：
   - ✅ short_term：新session数据完全覆盖旧内容（隔离）
   - ✅ user.md：积极合并新信息（无条件更新）
   - ✅ agent_identity.md：积极合并新能力边界（无条件更新）
   - ✅ long_term.md：仅当LLM识别普遍规则时更新
3. 任务队列处理（由 `agent-lab service run` 管理）

**配置与扩展：**
- 记忆整理提示词：`config/memory_organizer_prompt.md`
- 修改该文件可调整各层的更新策略
- 若文件缺失，系统回退到内置默认（完全兼容）

### 4.1.1 记忆整理提示词配置

- 记忆整理提示词已抽离到：`config/memory_organizer_prompt.md`
- 可直接修改该文件，调整“长期记忆判断、用户/agent 信息判断、短期压缩策略”。
- 若文件缺失，系统会回退到内置默认提示词。

### 4.2 日志说明

- 开启 `config.json` 根字段 `log: true` 后，所有 LLM 请求/响应都会写入工作区 `log/`。
- 日志包含：时间戳、请求类型、provider、model、base_url、payload。

### 4.3 API 鉴权配置

- 配置文件根字段：
  - `api_auth: boolean`
  - `api_keys: string[]`
- 当 `api_auth=true` 时，`/v1/models` 和 `/v1/chat/completions` 需要提供有效 API Key。
- 支持两种传法：
  - `Authorization: Bearer <key>`
  - `X-API-Key: <key>`

示例：

```json
{
  "api_auth": true,
  "api_keys": [
    "key-prod-001",
    "key-internal-002"
  ]
}
```

### 5. 通过 OpenAI 协议调用 Agent

服务启动后，可以通过 OpenAI Chat Completions 协议调用：

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer key-prod-001" \
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

### 5.1 API 指定 workspace / background / session

API 现在支持通过三种方式指定 `workspace`、`background` 和 `session`：

1. 请求体字段（优先级最高）
- `workspace`
- `background`（可选，background 目录路径）
- `session`
- `session_mode`: `append | stateless | replace`
- `RebuildSystemPrompt`: `true | false`（默认 false）

2. Query 参数
- `?workspace=...&background=...&session=...&session_mode=...`

3. Header
- `X-AgentLab-Workspace`
- `X-AgentLab-Background`
- `X-AgentLab-Session`
- `X-AgentLab-Session-Mode`

优先级规则：
- body > query > header > 默认配置

会话模式：
- `append`: 默认模式。有显式历史时优先使用请求内历史，否则读取并续写 `sessions/{session}.json`
- `replace`: 用本次请求历史重建并覆盖该 session
- `stateless`: 不读写 session 文件

示例 1：请求体方式

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer key-prod-001" \
  -d '{
    "model": "qwen3.5-flash",
    "workspace": "d:/workspace/ws01",
    "background": "d:/shared/background/storypack-a",
    "session": "demo01",
    "session_mode": "append",
    "RebuildSystemPrompt": true,
    "messages": [{"role": "user", "content": "介绍下产品"}],
    "stream": false
  }'
```

示例 2：Query 参数方式

```bash
curl "http://127.0.0.1:8000/v1/chat/completions?workspace=d:/workspace/ws01&background=d:/shared/background/storypack-a&session=demo01&session_mode=append" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer key-prod-001" \
  -d '{
    "model": "qwen3.5-flash",
    "messages": [{"role": "user", "content": "介绍下产品"}],
    "stream": false
  }'
```

示例 3：Header 方式

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer key-prod-001" \
  -H "X-AgentLab-Workspace: d:/workspace/ws01" \
  -H "X-AgentLab-Background: d:/shared/background/storypack-a" \
  -H "X-AgentLab-Session: demo01" \
  -H "X-AgentLab-Session-Mode: append" \
  -d '{
    "model": "qwen3.5-flash",
    "messages": [{"role": "user", "content": "介绍下产品"}],
    "stream": false
  }'
```

说明：
- `background` 不指定时，不注入任何 background 内容。
- 指定后会读取目录内全部 `.md`（含子目录）注入 system prompt。
- 注入顺序：`workspace prompt/identity/profile -> background -> memory -> runtime/policies/skills/knowledge`。
- `RebuildSystemPrompt` 默认 `false`，仅当显式为 `true` 时才强制重建第一条 internal system prompt。

### 5.2 API 流式 SSE

- 当 `stream=true` 时，API 现在返回标准 `text/event-stream`
- 输出形态兼容 OpenAI `chat.completion.chunk`
- 流结束时返回 `data: [DONE]`

示例：

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -N \
  -d '{
    "model": "qwen3.5-flash",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }'
```

可用端点：
- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`

当前限制：
- CLI `--streaming` 已支持增量显示（OpenAI 兼容与 Anthropic provider）
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

