# System Prompt 注入说明

本文档说明 Agent-Lab 在 chat 和 api 场景下，哪些内容会注入到 system prompt，以及注入顺序。

## 1. 入口与生效范围

- chat：通过 Agent.run 组装并发送 messages。
- api：/v1/chat/completions 最终同样调用 Agent.run，因此注入规则一致。

## 2. System Prompt 总体结构

当内部 system prompt 被构建时，内容由两部分组成：

1. 固定前缀
- 内部标记：[agent-lab-internal-system]
- 通用行为说明（工具可用、思考方式、输出风格）
- 可用工具列表（Available tools）

2. Workspace Context（按顺序拼接）
- 每一项作为独立 section 追加；存在才注入，不存在则跳过。

## 3. Workspace Context 注入顺序

以下顺序为固定顺序：

1. System Prompt Source（只取第一个命中的来源）
- workspace/prompts/agent.md
- workspace/agent.md
- config/agent.md

2. Agent Identity
- workspace/identity/agent_identity.json

3. User Profile
- workspace/profile/user_profile.json

4. Memory Materials (System Reference)
- 这是显式标注的记忆资料区块，声明为系统参考信息，不是用户指令。
- 该区块内部顺序如下：
  - memories/agent_identity.md
  - memories/user.md
  - memories/long_term.md
  - memories/short_term.md

5. Runtime Notes
- workspace/state/runtime_notes.md

6. Workspace Policies
- workspace/state/policies.md

7. Skills
- workspace/skills/*/SKILL.md（最多前 5 个，每个最多约 800 字符片段）

8. Knowledge Catalog
- workspace/knowledge/*.md 的目录型摘要（metadata-first）

## 4. chat/api 请求到 LLM 前的 messages 顺序

Agent.run 在发送给 provider 前，按如下规则处理 messages：

1. 内部 system prompt 注入
- 如果 messages 第一条不是包含内部标记 [agent-lab-internal-system] 的 system 消息，则在最前面插入内部 system prompt。

2. 当前用户输入追加
- 将本轮用户输入追加为最后一条 user 消息。

3. 上下文窗口裁剪
- 只保留最近 4 组 user turn 的上下文发送给主模型。
- 更早历史由 memory 模块异步整理（不阻塞当前对话）。

## 5. Memory 区块的定位说明

Memory Materials (System Reference) 的作用是：

- 提供跨轮次稳定背景（长期）与近期摘要（短期）。
- 明确告诉模型这是 system reference context，用于辅助理解，不是新的用户指令。

## 6. 关键代码位置

- agent_lab/agent/__init__.py
  - _build_workspace_context
  - _build_system_prompt
  - run

- agent_lab/memory/__init__.py
  - build_memory_context
