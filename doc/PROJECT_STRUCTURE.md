# 项目结构完全指南

## 目录树

```
agent-lab-system/
│
├── pyproject.toml              # 项目配置和依赖
├── README.md                   # 项目主文档
├── QUICKSTART.md              # 快速开始指南
├── ARCHITECTURE.md            # 架构文档
├── config/memory_organizer_prompt.md # 记忆整理提示词（可配置）
├── verify.py                  # 快速验证脚本
│
├── agent_lab/                 # 主包
│   ├── __init__.py            # 包版本和标志
│   ├── cli.py                 # CLI 入口点
│   ├── context.py             # 上下文构建
│   ├── session.py             # 会话管理
│   ├── memory/                # 记忆管理模块
│   │   └── __init__.py        # MemoryManager / MemoryTask
│   │
│   ├── api/                   # OpenAI 兼容 API
│   │   ├── __init__.py
│   │   └── server.py          # FastAPI 服务
│   │
│   ├── config/                # 配置模块
│   │   ├── __init__.py
│   │   ├── schema.py          # Pydantic 模型
│   │   └── loader.py          # 加载/保存逻辑
│   │
│   ├── providers/             # LLM 提供商模块
│   │   ├── __init__.py
│   │   ├── base.py            # 抽象基类
│   │   ├── openai_compat.py   # OpenAI 兼容
│   │   ├── anthropic_compat.py# Anthropic 实现
│   │   └── factory.py         # 创建函数
│   │
│   ├── tools/                 # 工具系统模块
│   │   ├── __init__.py
│   │   ├── base.py            # 工具抽象基类
│   │   ├── registry.py        # 注册表
│   │   └── builtin.py         # 内置工具
│   │
│   ├── agent/                 # Agent 主循环
│   │   └── __init__.py        # Agent 类
│   │
│   ├── workspace/             # 工作区管理
│   │   └── __init__.py        # Workspace 类
│   │
│   └── skills/                # 技能系统
│       └── __init__.py        # SkillsLoader 类
│
└── tests/                     # 测试文件
    └── test_basic.py          # 基础测试

```

## 核心模块说明

### 1. 配置系统 (`agent_lab/config/`)

| 文件 | 类 | 职责 |
|------|-----|------|
| `schema.py` | `Config`, `ProviderConfig`, etc. | Pydantic 数据模型 |
| `loader.py` | - | 配置文件 I/O |

**关键接口：**
```python
load_config(config_path: Path) -> Config
save_config(config: Config, config_path: Path) -> None
```

### 2. LLM 提供商 (`agent_lab/providers/`)

| 文件 | 类 | 职责 |
|------|-----|------|
| `base.py` | `LLMProvider`, `LLMResponse`, `ToolCall` | 抽象基类 |
| `openai_compat.py` | `OpenAICompatProvider` | OpenAI 兼容实现 |
| `anthropic_compat.py` | `AnthropicCompatProvider` | Anthropic 实现 |
| `factory.py` | `create_provider()` | 工厂模式 |

**关键接口：**
```python
async def chat(
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    tool_choice: str | dict | None = None,
  enable_think_mode: bool = False,
  enable_streaming_mode: bool = False,
) -> LLMResponse
```

### 3. 工具系统 (`agent_lab/tools/`)

| 文件 | 类 | 职责 |
|------|-----|------|
| `base.py` | `Tool` | 工具抽象基类 |
| `registry.py` | `ToolRegistry` | 工具注册和管理 |
| `builtin.py` | `ReadFileTool`, etc. | 内置工具 |

**关键接口：**
```python
class Tool(ABC):
    @property
    def name(self) -> str: ...
    async def execute(self, **kwargs) -> Any: ...

class ToolRegistry:
    def register(self, tool: Tool) -> None
    async def execute(self, name: str, params: dict) -> Any
```

### 4. Agent 循环 (`agent_lab/agent/`)

| 文件 | 类 | 职责 |
|------|-----|------|
| `__init__.py` | `Agent` | 主 Agent 类 |

**关键接口：**
```python
async def run(
    message: str,
    history: list[dict] | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    tool_choice: str | dict | None = None,
    enable_think_mode: bool | None = None,
    enable_streaming_mode: bool | None = None,
    session_id: str = "default",  # NEW: session identifier for memory context
) -> tuple[str, list[dict]]
```

### 5. 工作区管理 (`agent_lab/workspace/`)

| 文件 | 类 | 职责 |
|------|-----|------|
| `__init__.py` | `Workspace` | 工作区初始化 |

### 6. 技能系统 (`agent_lab/skills/`)

| 文件 | 类 | 职责 |
|------|-----|------|
| `__init__.py` | `SkillsLoader` | 技能加载 |

### 7. 会话管理 (`agent_lab/session.py`)

| 类 | 职责 |
|-----|------|
| `Session` | 持久化对话历史 |

### 8. 上下文构建 (`agent_lab/context.py`)

| 类 | 职责 |
|-----|------|
| `ContextBuilder` | 构建 LLM 提示 |

### 9. CLI 入口 (`agent_lab/cli.py`)

| 功能 | 说明 |
|------|------|
| `init` | 初始化工作区 |
| `config` | 显示配置 |
| `chat` | 与 Agent 聊天 |
| `chat -w` | 指定本次会话 workspace 路径 |
| `tools-list` | 列出工具 |
| `skills-list` | 列出技能 |
| `api` | 启动 OpenAI 兼容 API 服务 |
| `service` | 管理 memory 后台服务（run/once/start/stop） |

### 11. Memory 系统 (`agent_lab/memory/`)

| 文件 | 类/函数 | 职责 |
|------|---------|------|
| `__init__.py` | `MemoryManager` | 四层记忆管理、session-local short_term、任务队列、后台处理 |
| `__init__.py` | `MemoryTask` | 记忆整理任务结构（包含session_id） |
| `__init__.py` | `_register_workspace()` | 注册workspace到全局registry供service发现 |

### 12. 记忆提示词配置 (`config/memory_organizer_prompt.md`)

| 文件 | 职责 |
|------|------|
| `memory_organizer_prompt.md` | 配置记忆整理/长期判断/用户与 agent 信息判断/短期压缩策略提示词 |

### 10. API 服务 (`agent_lab/api/`)

| 文件 | 类/函数 | 职责 |
|------|---------|------|
| `server.py` | `create_app()` | 创建 FastAPI 应用并暴露 OpenAI 兼容端点 |
| `__init__.py` | - | API 模块导出 |

## 类关系图

```
LLMProvider (ABC)
├── OpenAICompatProvider
└── AnthropicCompatProvider

Tool (ABC)
├── ReadFileTool
├── WriteFileTool
└── ListDirTool

CLI
├── Config (via ConfigLoader)
├── Agent
│   ├── Provider (Factory.create_provider)
│   ├── ToolRegistry
│   └── ContextBuilder
└── Session

FastAPI API
├── create_app()
├── Agent
│   ├── Provider (Factory.create_provider)
│   └── ToolRegistry
└── OpenAI-compatible HTTP response

Memory Service
├── enqueue from Agent/API
├── process queue in background
└── rewrite memory files by merge policy
```

## 配置文件格式

**位置：** `~/.agent-lab/config.json`

```json
{
  "agents": {
    "defaults": {
      "model": "gpt-4o",
      "provider": "auto",
      "max_tokens": 4096,
      "temperature": 0.7,
      "max_iterations": 20,
      "enable_think_mode": false,
      "enable_streaming_mode": false,
      "workspace": "~/.agent-lab/workspace"
    }
  },
  "providers": {
    "openai": {
      "api_key": "sk-...",
      "api_base": null,
      "extra_headers": null
    },
    "anthropic": {
      "api_key": "sk-ant-...",
      "api_base": null,
      "extra_headers": null
    },
    "custom": {
      "api_key": "",
      "api_base": "http://localhost:8000/v1",
      "extra_headers": null
    }
  },
  "tools": {
    "enable_read_file": true,
    "enable_write_file": true,
    "enable_list_dir": true
  }
}
```

## 工作区结构

```
~/.agent-lab/
├── config.json                    # 全局配置
├── state/                         # 全局状态
│   └── memory_workspaces.json     # 注册的workspace供service发现
│
└── workspace/
    ├── prompts/                  # 系统提示词
    ├── identity/                 # Agent 标识
    ├── profile/                  # 用户画像
    ├── skills/                   # 技能库（用户可添加）
    │   ├── skill1/
    │   │   └── SKILL.md
    │   └── skill2/
    │       └── SKILL.md
    ├── memories/                 # 四层记忆文件
    │   ├── agent_identity.md              # 跨session共享
    │   ├── user.md                        # 跨session共享
    │   ├── long_term.md                   # 跨session共享
    │   └── short_term/                    # 目录：session-local隔离
    │       ├── short_term_default.md
    │       ├── short_term_session_1.md
    │       └── short_term_{session_id}.md
    ├── state/                    # 运行状态与 memory 队列
    │   ├── memory_tasks/        # 待处理记忆任务
    │   ├── memory_tasks_done/   # 已完成任务存档
    │   └── memory_tasks_failed/ # 失败任务存档
    ├── log/                      # LLM 交互日志
    └── sessions/                 # 对话历史（session-local）
        ├── default.json
        └── other-session.json
```

**说明：**
- `short_term/` 是目录，每个session独立一个文件
- `user.md`、`agent_identity.md`、`long_term.md` 在workspace级别共享
- `memory_workspaces.json` 在全局 `~/.agent-lab/state/` 下，供memory service自动发现所有workspace

## 依赖关系

```
┌─────────────────────────────────────┐
│         CLI Entry Point             │
│       (agent_lab/cli.py)           │
└─────────────────────────────────────┘
           ↓
    ┌──────────────────────────┐
    │   Configuration Loader   │
    │   (config/loader.py)    │
    └──────────────────────────┘
           ↓
    ┌──────────────────────────────────┐
    │   Agent Initialization           │
    │   (agent/__init__.py)           │
    ├──────────────────────────────────┤
    │   ├→ Provider Factory            │
    │   │   (providers/factory.py)    │
    │   ├→ Tool Registry              │
    │   │   (tools/registry.py)       │
    │   ├→ Context Builder            │
    │   │   (context.py)              │
    │   └→ Session Manager            │
    │       (session.py)              │
    └──────────────────────────────────┘
```

## 扩展点总结

| 扩展类型 | 位置 | 步骤 |
|---------|------|------|
| 新工具 | 继承 `Tool` | `registry.register(MyTool())` |
| 新提供商 | 继承 `LLMProvider` | `register in factory.py` |
| 新命令 | 编辑 `cli.py` | `@app.command()` |
| 自定义技能 | 添加 SKILL.md | 放到 `workspace/skills/` |

## 生命周期

### 初始化阶段
1. 用户运行 `agent-lab init`
2. 创建 `~/.agent-lab/config.json`
3. 创建 `~/.agent-lab/workspace/` 及子目录

### 运行阶段
1. CLI 解析命令
2. 加载配置
3. 创建 Provider（基于配置）
4. 初始化 ToolRegistry
5. 创建 Agent 实例
6. 执行用户请求并 enqueue memory 任务
7. 由 `agent-lab service` 后台处理 memory 压缩与分层写回

### 会话阶段
1. 加载会话历史（如存在）
2. 构建消息列表
3. 运行 Agent 循环
4. 保存新消息到会话
5. 返回结果给用户

