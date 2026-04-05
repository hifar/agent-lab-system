# 架构文档

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

#### 5. Workspace 系统（`workspace/`）

**职责：** 管理文件系统布局

**目录结构：**
```
~/.agent-lab/
├── config.json              # 全局配置
└── workspace/
    ├── skills/              # 技能库
    ├── memories/            # 记忆存储
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
- `tools-list` - 列出工具
- `skills-list` - 列出技能

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
   - 流式输出
   - 提示缓存

2. **未来改进：**
   - 支持工具的并发执行
   - 智能历史穴刻减
   - 支持更多内置工具
   - 可视化 Agent 状态

