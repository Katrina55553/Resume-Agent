# Tool Calling 机制

## 技术原理

Tool Calling = 让 LLM **自己决定**要不要调用外部工具，而不是代码里写死。

传统方式（固定流程）：
```
代码: 先检索知识库 → 再生成问题 → 再评估
（不管需不需要，每次都检索）
```

Agent 方式（动态决策）：
```
LLM: "这个存疑点涉及 MySQL 索引，我需要查一下知识库"
   → 调用 search_knowledge_base("MySQL 索引")
   → 拿到参考内容
   → 生成更专业的问题

LLM: "这个回答提到了代码片段，我需要验证一下"
   → 调用 verify_code_snippet(code, "Python")
   → 拿到分析结果
   → 结合分析评估回答
```

## 项目中的 3 个工具

```python
# tools.py
TOOLS = [
    {
        "name": "search_knowledge_base",
        "description": "从面试题知识库中检索相关技术资料",
        "parameters": {"query": "检索关键词"}
    },
    {
        "name": "lookup_resume_field",
        "description": "查看候选人简历中的具体字段",
        "parameters": {"field": "work_experience|education|projects|skills"}
    },
    {
        "name": "verify_code_snippet",
        "description": "验证代码片段的正确性",
        "parameters": {"code": "代码", "language": "Python", "context": "背景"}
    }
]
```

## 调用流程

```
用户回答: "我用 B+树索引优化了查询"
    │
    ├─→ LLM 收到回答 + 工具定义
    │
    ├─→ LLM 判断: "需要验证 B+树索引的知识"
    │   → 返回 tool_call: search_knowledge_base({"query": "MySQL B+树索引"})
    │
    ├─→ 代码执行工具调用
    │   → 从知识库检索到 "B+树索引原理" 相关内容
    │
    ├─→ 工具结果返回给 LLM
    │
    └─→ LLM 结合工具结果生成追问:
        "你说的 B+树索引，是聚簇索引还是二级索引？什么情况下会回表？"
```

## 关键代码

### LLM 调用（带工具）

```python
# llm.py
def call_llm_with_tools(system_prompt, user_prompt, tools, task_type):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tools=tools,          # 传入工具定义
        tool_choice="auto",   # 让 LLM 自己决定要不要调
    )

    message = response.choices[0].message

    # 检查 LLM 是否要调用工具
    if message.tool_calls:
        # LLM 决定调用工具
        for tc in message.tool_calls:
            result = execute_tool(tc.function.name, json.loads(tc.function.arguments))
            # 把结果返回给 LLM
        ...
    else:
        # LLM 直接返回文本，不需要工具
        return message.content
```

### 工具执行

```python
# tools.py
def execute_tool(tool_name, tool_args, resume_data=None):
    if tool_name == "search_knowledge_base":
        return retrieve_context(tool_args["query"])  # RAG 检索
    elif tool_name == "lookup_resume_field":
        return resume_data.get(tool_args["field"])    # 查简历字段
    elif tool_name == "verify_code_snippet":
        return call_llm("代码审查专家", tool_args["code"])  # LLM 分析代码
```

### DeepSeek 兼容处理

DeepSeek 不完全支持 OpenAI 的结构化 tool_calls，会把工具调用输出为文本：

```
<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="search_knowledge_base">
</｜｜DSML｜｜invoke>
</｜｜DSML｜｜tool_calls>
```

需要从文本中解析：

```python
# llm.py - _parse_tool_calls_from_text
xml_pattern = r'name\s*=\s*["\'](\w+)["\']'
matches = re.findall(xml_pattern, content)
for func_name in matches:
    if func_name in known_tools:
        tool_calls.append({"name": func_name, "arguments": ...})
```

## 面试高频问题

### Q1: Tool Calling 和 Function Calling 有什么区别？

**A:** 没有本质区别，是同一种机制的不同叫法：
- OpenAI 叫 **Function Calling**
- Anthropic 叫 **Tool Use**
- 通用叫法 **Tool Calling**

都是：LLM 分析用户输入 → 决定调用哪个函数 → 返回函数名和参数 → 代码执行 → 结果返回 LLM。

### Q2: LLM 怎么决定要不要调用工具？

**A:** LLM 根据两个信息判断：
1. **系统提示**：告诉 LLM 有哪些工具可用、什么时候该用
2. **工具定义**：每个工具的 name、description、parameters

LLM 分析用户输入后，如果觉得需要外部信息来回答，就会返回 `tool_calls`。如果能直接回答，就返回文本。

这个决策是 LLM 自己做的，不是代码控制的。

### Q3: 如果工具调用失败了怎么办？

**A:** 两层保护：
1. 工具执行有 try-catch，失败返回错误信息字符串（不抛异常）
2. 工具结果返回给 LLM 时，LLM 会看到错误信息，可以换一种方式回答

```python
try:
    result = execute_tool(tc.function.name, args)
except Exception as e:
    result = f"工具执行失败: {e}"  # 返回错误信息，不崩溃
```

### Q4: 和直接在 prompt 里塞 RAG 结果有什么区别？

**A:**

| | 固定 RAG（之前） | Tool Calling（现在） |
|--|----------------|-------------------|
| 谁决定检索 | 代码硬编码，每次都检索 | LLM 自主决定，需要时才检索 |
| 检索时机 | 生成问题前 | 任何时候（提问、评估都能调） |
| 工具数量 | 只有知识库检索 | 3 个工具可选 |
| 灵活性 | 固定流程 | Agent 动态编排 |

Tool Calling 让 Agent 有**自主决策能力**，不是死板的流水线。

### Q5: Tool Calling 的延迟会不会很高？

**A:** 会比单次 LLM 调用高，因为可能需要 2-3 次 LLM 调用：
1. 第 1 次：LLM 分析 + 决定调用工具
2. 工具执行（很快，毫秒级）
3. 第 2 次：LLM 结合工具结果生成最终回答

但实际体验还好，因为：
- 知识库检索很快（内存列表或 ES 毫秒级）
- 流式推送让用户感知不到完整延迟
- 只有需要时才调用，不每次都走工具
