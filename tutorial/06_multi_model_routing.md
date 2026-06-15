# 多模型路由

## 技术原理

不是所有 LLM 调用都需要最好的模型。根据任务复杂度选模型，省钱又快。

```
任务类型              复杂度    模型选择           原因
─────────────────────────────────────────────────────
生成面试问题           低       DeepSeek-Chat      创意性任务，轻量模型够用
回答评估               高       DeepSeek-Reasoner  需要推理判断可信度
最终报告               高       DeepSeek-Reasoner  需要综合分析
简历解析               中       DeepSeek-Chat      结构化提取
```

## 成本对比

| 模型 | 单价（每百万 token） | 用在哪 |
|------|---------------------|--------|
| DeepSeek-Chat | ¥1 | 问题生成、简历解析 |
| DeepSeek-Reasoner | ¥4 | 评估、报告 |

一次典型面试（10 次 LLM 调用）：
- **全用 Reasoner**：10 × ¥4 = ¥40
- **路由优化**：7 次 Chat(¥1) + 3 次 Reasoner(¥4) = ¥19
- **节省 52%**

## 关键代码

### 分类器

```python
# llm.py
_TASK_COMPLEXITY = {
    "question": "light",      # 生成问题 → 轻量
    "rephrase": "light",      # 换问法 → 轻量
    "parse": "medium",        # 简历解析 → 中等
    "diagnose": "medium",     # 诊断 → 中等
    "evaluate": "heavy",      # 评估 → 旗舰
    "report": "heavy",        # 报告 → 旗舰
}

def classify_task(task_type: str, context: dict = None) -> str:
    ctx = context or {}
    base = _TASK_COMPLEXITY.get(task_type, "medium")

    # 动态调整
    if task_type == "evaluate" and "answer_length" in ctx and ctx["answer_length"] < 50:
        return "medium"  # 回答很短，评估不需要旗舰模型

    if task_type == "question" and "current_round" in ctx and ctx["current_round"] >= 3:
        return "medium"  # 深度追问需要更好理解

    return base
```

**为什么不用 LLM 分类？** 用 LLM 来判断该用哪个 LLM，是鸡生蛋问题。规则足够准确，零延迟零成本。

### 模型池

```python
_MODEL_POOL = {
    "light": {
        "model": "deepseek-chat",
        "cost_per_1k": 0.001,
        "max_tokens": 2048,
    },
    "medium": {
        "model": "deepseek-chat",
        "cost_per_1k": 0.001,
        "max_tokens": 4096,
    },
    "heavy": {
        "model": "deepseek-reasoner",
        "cost_per_1k": 0.004,
        "max_tokens": 4096,
    },
}
```

### 路由调用

```python
def call_llm_routed(task_type, system_prompt, user_prompt, context=None):
    level = classify_task(task_type, context)
    pool = _MODEL_POOL[level]

    response = client.chat.completions.create(
        model=pool["model"],      # 根据等级选模型
        temperature=0.3 if level == "heavy" else 0.7,  # 旗舰模型更保守
        max_tokens=pool["max_tokens"],
        messages=[...],
    )

    # 记录成本
    cost = (usage.prompt_tokens + usage.completion_tokens) / 1000 * pool["cost_per_1k"]
    _cost_log.append({"task": task_type, "model": pool["model"], "cost": cost})

    return response.choices[0].message.content
```

### 各节点使用

```python
# question.py - 用轻量模型
content, tool_calls = call_llm_with_tools(
    system_prompt, user_prompt, tools,
    task_type="question",  # → light → deepseek-chat
)

# evaluate.py - 用旗舰模型
content, tool_calls = call_llm_with_tools(
    system_prompt, user_prompt, tools,
    task_type="evaluate",  # → heavy → deepseek-reasoner
)

# report.py - 用旗舰模型
result = call_llm_routed_json("report", system_prompt, user_prompt)
```

## 面试高频问题

### Q1: 分类器的准确率怎么保证？

**A:** 分类器是**规则驱动**，不是 ML 模型。准确率取决于规则设计：
- 任务类型映射：100% 准确（代码硬编码）
- 动态调整：基于 `answer_length`、`current_round` 等确定性指标

不需要"准确率"这个概念，因为规则是确定性的，相同输入一定产生相同输出。

### Q2: 如果 DeepSeek-Reasoner 挂了怎么办？

**A:** `call_llm_routed` 有 try-catch，失败时返回 None。调用方检测到 None 后降级：
- evaluate 降级到规则评分
- report 降级到规则报告

```python
try:
    result = call_llm_routed("evaluate", ...)
except Exception:
    result = _rule_score_answer(answer_text)  # 降级
```

### Q3: 同一个模型（deepseek-chat）分 light 和 medium 有什么意义？

**A:** 虽然模型相同，但配置不同：
- `light`: max_tokens=2048（限制输出长度，省 token）
- `medium`: max_tokens=4096（允许更长输出）

未来如果换模型（比如 light 用更便宜的模型），只需要改 `_MODEL_POOL` 配置，不用改业务代码。

### Q4: 成本统计怎么用？

**A:** `get_cost_summary()` 返回本次会话的成本明细：

```python
{
    "total_cost": 0.0267,      # 总成本
    "calls": 10,               # 调用次数
    "all_heavy_cost": 0.0816,  # 全用旗舰模型的成本
    "savings": 67,             # 节省百分比
    "by_level": {
        "light": {"calls": 5, "cost": 0.005},
        "heavy": {"calls": 3, "cost": 0.012},
    }
}
```

可以用来监控实际成本，优化路由策略。

### Q5: 和直接用一个模型比，延迟有差别吗？

**A:** 有差别，但不大：
- DeepSeek-Chat：响应快（1-3 秒）
- DeepSeek-Reasoner：响应慢（3-8 秒，有推理过程）

但路由策略是把 Reasoner 用在**真正需要推理的地方**（评估、报告），这些场景用户本来就能接受等几秒。问题生成用 Chat，反而更快。
