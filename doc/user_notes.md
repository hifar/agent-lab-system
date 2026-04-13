**Agent ignore this file**

TODO：
1. streaming API ✔
2. API支持workspace 和session ✔
3. 记忆功能优化 ✔
4. web界面
5. Background功能


```
{
  "model": "qwen3.5-flash",
  "messages": [
    {
      "role": "user",
      "content": "介绍下星枢产品",
      "name": "string",
      "tool_call_id": "string",
      "tool_calls": [
        {
          "additionalProp1": {}
        }
      ]
    }
  ],
  "max_tokens": 1110,
  "temperature": 1,
  "think_mode": true,
  "streaming_mode": true,
  "stream": false
}
```


```
请实现memory 模块， 包括memory整理，抽取长期记忆，memory压缩，memory读取等逻辑放到memory模块中， cli 增加service 参数， 可启动agent-lab 服务， 服务在后台运行，用于处理memory整理， memory压缩等工作。 memory内容分为三层 1长期记忆：包括agent_identity.md agent自身信息， user.md  long_term.md 长期记忆， 永久保留的记忆。 2 短期记忆 short_term.md 短期记忆， 当前会话上下文压缩的内容.  3 当前上下文的最后四组对话内容 
记忆内容在后台service 中运行， 可通过会话后进行触发，是否作为长期记忆，以及上下文压缩的短期记忆， 均通过提交给llm进行判断。 cli 以及api的交互可以触发service的相关后台记忆整理操作。

user.md agent_identity.md long_term.md short_term.md 不是意味追加， 而是需要把原先的内容一起合并整理更新。 如果未涉及用户相关内容偏好， 以及agent的内容， 无需修改user和agent， 只有重要信息才需要放入long_term , 在对话请求llm的时候， 记忆信息要以system prompt 的方式一起放入上下文

```