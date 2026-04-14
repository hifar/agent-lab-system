# 架构文档

## 增量更新（2026-04-07）

- 新增 `memory/` 模块，统一管理三层记忆：长期记忆、短期记忆、最近 4 组对话。
- 新增后台 memory service（CLI `service` 命令）用于异步整理与压缩记忆，不阻塞聊天主链路。
- 记忆更新策略改为“合并重写”而非追加：`user.md`、`agent_identity.md`、`long_term.md`、`short_term.md` 按规则覆盖写回。
- 记忆组织 LLM 输出解析增强：支持 fenced JSON（```json ... ```）与非标准文本提取，异常场景自动安全回退。
- 新增全链路 LLM 请求/响应日志写入 `workspace/log/`（JSONL + 可读日志）。

## 增量更新（2026-04-11）

- CLI 新增多 workspace 支持：`chat -w/--workspace` 可在单次会话覆盖 workspace 路径。
- `init -w` 与 `chat -w` 都支持显式指定路径，未指定时仍使用 `~/.agent-lab/workspace`（配置默认）。
- 记忆整理提示词抽离到 `config/memory_organizer_prompt.md`，支持直接配置与热调整。
- 新增文档 `doc/SYSTEM_PROMPT_INJECTION.md`，明确 system prompt 注入内容与顺序。
- API 新增多 workspace / session 支持：可通过 body、query、header 指定。
- API 新增 SSE 流式返回：`stream=true` 时返回 OpenAI-compatible chunk 流。

## 增量更新（2026-04-12 - 最新）

- **Memory系统大幅优化**：
  - Short-term memory 改为 session-local（`short_term_{session_id}.md`），避免跨session污染
  - User/Agent identity 改为无条件更新（积极学习），去掉 `should_update_*` 网关
  - Long-term memory 保持保守更新策略（仅记录通用规则）
  - 记忆整理提示词明确了四层职责划分
- API 鉴权功能：`api_auth` 与 `api_keys` 开关，支持 Bearer 和 X-API-Key
- 详见 [Memory Optimization Document](MEMORY_OPTIMIZATION_2026_04.md)

## 增量更新（2026-04-13）

- 新增 **Background Story** 注入能力：
    - CLI 支持 `chat -b/--background <dir>` 指定共享背景目录
    - API 支持 `background` 的 body/query/header 覆盖，优先级与 workspace 一致
    - 未指定 background 时不注入任何背景内容
- Background 目录支持多个 `.md` 文件（含子目录），全部注入 system prompt
- 注入顺序明确：background 位于 memory 之前

## 增量更新（2026-04-13 - Web UI）

- 新增轻量 Web 聊天入口：CLI `web` 命令（`agent-lab web --host --port --api-base`）。
- 新增 `agent_lab/web/` 模块，提供浏览器 UI 与 `/proxy/chat` 代理端点。
- Web 页面改为模板文件读取：`agent_lab/web/templates/index.html`，运行时注入默认参数。
- 前端不再依赖 `https://fonts.googleapis.com` 等远程字体资源，改为本地系统字体栈。
- Web 代理支持 SSE 转发和 OpenAI-compatible 非流式回退解析。

## 增量更新（2026-04-14 - Web UI 迭代）

- 聊天页改为 **session-centric** 结构：左侧 session 清单，支持新建、重命名、删除。
- `workspace` / `session` / `background` 绑定到会话创建阶段，已开始会话不再修改。
- 新增设置面板，集中保存 API 与推理参数到浏览器本地存储。
- 顶部新增 `Logs` 按钮，打开独立日志查看页面，不打断聊天页。
- 新增独立日志模板：`agent_lab/web/templates/logs.html`。
- 新增日志 API：文件列表、日志条目筛选、`request_id` 成对联动视图。

## 增量更新（2026-04-12）

- 配置新增 API 鉴权开关：`api_auth` 与 `api_keys`。
- 当 `api_auth=true` 时，`/v1/models` 与 `/v1/chat/completions` 需要有效 API Key。
- API Key 支持 `Authorization: Bearer <key>` 与 `X-API-Key` 两种传法。

## 系统设计

agent-lab 是一个精简的 Agent 系统，设计理念是"先可用、再增强"。

### 核心组件

#### 1. Configuration 系统（`config/`）

**职责：** 加载、验证、管理全局配置

**关键类：**
- `Config` - 根配置类（Pydantic BaseSettings）
- `ProviderConfig` - 单个提供商配置
- `AgentDefaults` - Agent 默认参数

**设计：**
- 基于 Pydantic v2，支持自动类型验证
- 环境变量自动覆盖
- `camelCase` 和 `snake_case` 都支持
- 支持 Agent 行为开关默认值：`enable_think_mode`、`enable_streaming_mode`
- 支持 API 访问控制：`api_auth`、`api_keys`

#### 2. LLM Provider 系统（`providers/`）

**职责：** 统一的 LLM 调用接口

**关键类：**
- `LLMProvider` - 抽象基类，定义 `chat()` 接口
- `OpenAICompatProvider` - OpenAI 兼容 API 实现
- `AnthropicCompatProvider` - Anthropic API 实现
- `create_provider()` - 工厂函数

**设计：**
- 异步优先（async/await）
- 消息格式规范化
- 统一的 tool_calls 解析
- 自动提供商检测

**支持的 API：**
- OpenAI 及其所有兼容实现
- Anthropic Claude 系列
- 本地 LLM（如 Ollama）- 通过 custom provider

#### 3. Tools 系统（`tools/`）

**职责：** 为 Agent 提供可调用的工具能力

**关键类：**
- `Tool` - 工具抽象基类
- `ToolRegistry` - 工具注册和管理
- `ReadFileTool`、`WriteFileTool`、`ListDirTool` - 内置工具

**设计：**
- JSON Schema 参数定义
- 异步执行（`async execute()`）
- 自动参数验证
- 安全的工作区隔离

**扩展点：**
```python
class MyTool(Tool):
    @property
    def name(self) -> str: ...
    @property
    def description(self) -> str: ...
    @property
    def parameters(self) -> dict: ...
    async def execute(self, **kwargs) -> Any: ...
```

#### 4. Agent 循环（`agent/`）

**职责：** 主控制循环，协调 LLM 和工具

**关键类：**
- `Agent` - 主 Agent 类

**流程：**
1. 接收用户消息
2. 构建消息列表（系统提示 + 历史 + 当前）
3. 调用 LLM
4. 解析响应
5. 如果有 tool_calls：
   - 执行每个工具
   - 收集结果
   - 回填消息列表
   - 返回步骤 3
6. 返回最终响应

**特征：**
- 可配置的最大迭代次数
- 自动系统提示构建
- 异步执行
- 自动注入 workspace 语义上下文（提示词、画像、background、记忆、策略、技能摘要）

#### 5. Workspace 系统（`workspace/`）

**职责：** 管理文件系统布局

**目录结构：**
```
~/.agent-lab/
├── config.json              # 全局配置
└── workspace/
    ├── prompts/             # 系统提示词
    ├── identity/            # Agent 标识
    ├── profile/             # 用户画像
    ├── skills/              # 技能库
    ├── memories/            # 记忆存储
    ├── state/               # 运行状态与策略
    └── sessions/            # 对话历史
```

**关键类：**
- `Workspace` - 初始化和管理工作区

#### 6. Skills 系统（`skills/`）

**职责：** 加载和管理技能

**关键类：**
- `SkillsLoader` - 扫描和加载技能

**技能格式：** Markdown 文件 (`SKILL.md`)

#### 7. Session 管理（`session.py`）

**职责：** 持久化对话历史

**关键类：**
- `Session` - 管理单个会话

**存储格式：** JSON

#### 8. Context 构建（`context.py`）

**职责：** 构建 LLM 调用的消息上下文

**关键类：**
- `ContextBuilder` - 构建系统提示和消息

#### 9. CLI 接口（`cli.py`）

**职责：** 命令行交互

**主要命令：**
- `init` - 初始化
- `config` - 配置管理
- `chat` - 聊天（单轮或多轮）
- `chat -w` - 指定本次会话 workspace（不修改全局配置）
- `tools-list` - 列出工具
- `skills-list` - 列出技能
- `api` - 启动 OpenAI 兼容 HTTP API

#### 10. API 服务（`api/server.py`）

**职责：** 对外暴露 OpenAI 兼容接口，让外部工具通过 HTTP 调用 agent

**关键接口：**
- `GET /health` - 健康检查
- `GET /v1/models` - 返回当前默认模型列表
- `POST /v1/chat/completions` - OpenAI Chat Completions 兼容接口

**设计：**
- 复用现有 `Agent` / `Provider` / `ToolRegistry` 逻辑
- 请求中最后一条 user 消息作为本轮输入
- 保留 OpenAI 兼容响应字段（`id` / `choices` / `usage`）
- 支持行为参数：`think_mode`、`streaming_mode`（兼容 `stream`）
- 支持运行时上下文参数：`workspace`、`background`、`session`、`session_mode`
- 参数解析优先级：body > query > header > 默认配置
- `stream=true` 时返回 `text/event-stream`，事件格式兼容 `chat.completion.chunk`

#### 12. Web UI 服务（`web/app.py`）

**职责：** 提供轻量浏览器聊天界面，并代理调用 OpenAI-compatible API。

**关键接口：**
- `GET /` - 返回前端聊天页面
- `POST /proxy/chat` - 代理调用上游 `/v1/chat/completions` 并向浏览器输出 SSE
- `GET /logs` - 返回日志查看页面
- `GET /logs/api/files` - 返回指定 workspace 的 JSONL 日志文件列表
- `GET /logs/api/entries` - 返回指定日志文件的筛选结果
- `GET /logs/api/request-pair` - 返回某个 `request_id` 对应的 request/response 配对记录

**设计：**
- 采用模板文件（`web/templates/index.html`）而非 Python 内嵌 HTML 字符串
- 运行时向模板注入默认配置（API base、默认模型等）
- 支持对上游流式响应进行增量转发，并兼容不同字段形态的文本提取
- 支持上游非流式响应回退为单次 `delta` + `done` 事件
- 聊天页采用会话列表 + 设置面板结构，浏览器本地持久化 session 元数据与设置
- 日志页针对 `workspace/log/*.jsonl` 提供按文件、时间、关键词、请求类型、记录类型的快速定位能力

#### 11. Memory 系统（`memory/`）

**职责：** 记忆分层、压缩、后台整理、上下文注入

**关键类：**
- `MemoryManager` - 记忆文件管理与任务队列处理
- `MemoryTask` - 记忆整理任务载荷

**核心设计：**
- 四层记忆（2026-04-12 优化）：
    - **短期层**（Session-local）：`memories/short_term/{session_id}.md` - 当前会话压缩摘要，各session隔离
    - **用户档案层**（跨session共享）：`memories/user.md` - 用户偏好、背景、身份、工作风格
    - **Agent身份层**（跨session共享）：`memories/agent_identity.md` - Agent能力范围、工作方式、约束边界
    - **长期层**（跨session共享）：`memories/long_term.md` - 通用规则、架构决策、重要常数
    - 运行层：最近 4 组对话（运行时窗口，不持久化为独立文件）
- 后台队列目录：`state/memory_tasks/`、`state/memory_tasks_done/`、`state/memory_tasks_failed/`
- 聊天主链路只负责 enqueue，整理逻辑在 service 或 `service once` 中异步处理
- 只有超过最近 4 组 user turn 的旧对话才会进入 memory 队列；不足 4 组时不会产生待整理任务
- 任意 workspace 发生 enqueue 时，都会注册到全局 workspace registry，供 memory service 自动发现
- `agent-lab service run` 默认扫描所有已注册 workspace 并处理各自队列；`-w` 仅作为可选过滤条件
- 写回策略（积极更新）：
    - **short_term**：完全覆盖写回（不合并其他session）- 保持session隔离
    - **user** / **agent_identity**：无条件更新（高更新率）- 积极学习用户/agent特性
    - **long_term**：仅在信息明确有持久价值时更新 - 保守策略

## 数据流

### 单轮聊天流程

```
User Input
    ↓
[CLI] 解析命令
    ↓
[Config] 加载配置
    ↓
[Provider] 创建提供商
    ↓
[Tools] 初始化工具
    ↓
[Agent] 运行循环
    ├→ [ContextBuilder] 构建消息
    ├→ [Provider.chat()] 调用 LLM
    ├→ 解析 tool_calls
    ├→ [Tools.execute()] 执行工具
    └→ 返回最终响应
    ↓
Output Response
```

### API 调用流程

```
External Client
    ↓
[FastAPI] /v1/chat/completions
    ↓
[Config] 加载配置
    ↓
[Provider Factory] 创建 provider
    ↓
[ToolRegistry] 初始化内置工具
    ↓
[Agent.run] 执行主循环
    ↓
OpenAI-compatible JSON Response
```

### Provider 交互

**请求流程：**
```python
messages = [{"role": "system", "content": "..."}, ...]
tools = [{"type": "function", "function": {...}}]
response = await provider.chat(messages, tools)
# LLMResponse: content + tool_calls
```

**工具调用格式：**
```python
ToolCall(
    id="call_xxx",
    name="read_file",
    arguments={"path": "test.txt"}
)
```

## 设计决策

### 1. 为什么使用异步？
- 工具执行经常涉及 I/O
- API 调用自然异步
- 支持未来的并发执行

### 2. 为什么统一 Tool 界面？
- 一致的参数验证流程
- 自动生成 OpenAI/Anthropic tool 定义
- 易于添加新工具

### 3. 为什么分离 Provider？
- 支持多个 LLM 的灵活性
- 独立测试每个 Provider
- 易于切换提供商

### 4. 为什么使用 Pydantic？
- 自动类型验证
- JSON 序列化支持
- 自动生成 JSON Schema

## 扩展点

### 添加新 Provider

```python
from agent_lab.providers import LLMProvider, LLMResponse

class MyLLMProvider(LLMProvider):
    async def chat(self, messages, tools=None, **kwargs) -> LLMResponse:
        # 实现
        pass
```

### 添加新 Tool

```python
from agent_lab.tools import Tool

class MyTool(Tool):
    # 实现抽象方法
    pass

# 注册
registry.register(MyTool())
```

### 自定义 System Prompt

```python
agent = Agent(
    provider=provider,
    tools=tools,
    workspace=Path.cwd(),
    system_prompt="Custom system prompt..."
)
```

## 性能特性

- **消息历史管理**：支持本地持久化会话
- **工具发现**：动态注册，O(1) 查找
- **生成效率**：避免不必要的 LLM 调用
- **异步执行**：I/O 不阻塞

## 安全特性

- **工作区隔离**：工具只能访问指定工作区
- **参数验证**：JSON Schema 强制验证
- **错误隔离**：工具异常不会 crash Agent

## 限制和已知问题

1. **暂未支持的功能：**
   - Channel 系统（仅 CLI）
   - Cron 任务调度
    - API 流式输出（`stream=true`）
   - 提示缓存
    - API 请求体直接注入自定义 tools

2. **未来改进：**
   - 支持工具的并发执行
   - 智能历史穴刻减
   - 支持更多内置工具
   - 可视化 Agent 状态

