# LangGraph 状态机编排面试流程

## 技术原理

LangGraph 是 LangChain 团队出的状态机框架，用**图（Graph）**描述 Agent 的执行流程。核心概念：

```
State（状态）→ Node（节点）→ Edge（边）→ Conditional Edge（条件边）
```

- **State**: 一个 TypedDict，存放所有上下文（消息、存疑点、评估结果等）
- **Node**: 一个函数，接收 State，返回 State 的更新
- **Edge**: 节点之间的连线
- **Conditional Edge**: 根据条件走不同分支

## 项目中的状态机

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
              ┌────►│  question   │◄────┐
              │     └──────┬──────┘     │
              │            │            │
              │     ┌──────▼──────┐     │
              │     │  collect    │     │
              │     └──────┬──────┘     │
              │            │            │
              │     ┌──────▼──────┐     │
              │     │  evaluate   │     │
              │     └──────┬──────┘     │
              │            │            │
              │     ┌──────▼──────┐     │
              │     │  决策分支    │     │
              │     └──┬───┬───┬──┘     │
              │        │   │   │        │
              │   follow_up │  report   │
              │        │   │   │        │
              └────────┘   │   ▼        │
                    next_point  report   │
                           │   生成报告   │
                           └─────────────┘
```

## 关键代码

### State 定义

```python
# backend/app/agent/state.py
class AgentState(TypedDict):
    doubt_points: list[dict]        # 存疑点列表
    current_point_index: int        # 当前存疑点索引
    current_round: int              # 当前追问轮次
    point_states: dict              # 各存疑点状态
    messages: list[dict]            # 对话历史
    current_question: str           # 当前问题
    current_answer: str             # 用户回答
    current_evaluation: dict        # 当前评估结果
    decision: str                   # 决策：follow_up/next_point/report
    evaluations: list[dict]         # 所有评估历史
```

### 节点函数

```python
# question.py - 生成问题
async def generate_question(state: dict) -> dict:
    doubt_point = state["doubt_points"][state["current_point_index"]]
    question = llm_generate(doubt_point, state["messages"])
    return {"current_question": question, "messages": [question_msg]}

# collect.py - 收集回答
async def collect_answer(state: dict) -> dict:
    answer = state["current_answer"]
    return {"messages": [{"role": "user", "content": answer}]}

# evaluate.py - 评估回答
async def evaluate_answer(state: dict) -> dict:
    score, feedback = llm_evaluate(state)
    decision = "follow_up" if score < 75 else "next_point"
    return {"current_evaluation": {...}, "decision": decision}
```

### 条件分支

```python
# graph.py
def route_after_evaluate(state: dict) -> str:
    if state.get("is_completed"):
        return "report"
    if state["decision"] == "next_point":
        return "next_point"
    return "follow_up"

graph.add_conditional_edges("evaluate", route_after_evaluate, {
    "follow_up": "question",     # 继续追问
    "next_point": "question",    # 切换存疑点，生成新问题
    "report": "report",          # 生成报告
})
```

## 三层防死循环

| 层 | 机制 | 实现 |
|----|------|------|
| 第 1 层 | 单点最多 3 轮追问 | `current_round >= MAX_FOLLOW_UP` → 强制切换 |
| 第 2 层 | 用户可主动跳过 | 前端发 `skip` → 后端标记 `skipped` → 切换下一个 |
| 第 3 层 | 异常降级 | LLM 调用失败 → 降级到规则评分，流程不中断 |

```python
# rules.py
class InterviewRules:
    MAX_FOLLOW_UP: int = 3      # 单点最多追问
    MAX_ERROR_COUNT: int = 3    # 连续异常熔断
    MAX_QUESTIONS: int = 20     # 总问题上限
```

## 面试高频问题

### Q1: 为什么用 LangGraph 而不是自己写 if-else？

**A:** LangGraph 的优势：
1. **可视化**：图结构天然可画成流程图，方便理解和调试
2. **状态管理**：自动管理 State 的传递和合并
3. **可扩展**：加新节点只需定义函数 + 连边，不影响已有逻辑
4. **生态**：和 LangChain 工具链无缝集成

如果只是 `question → evaluate → next` 的简单循环，自己写确实够了。但当逻辑复杂到有多个分支、工具调用、异常处理时，LangGraph 的图结构比嵌套 if-else 清晰得多。

### Q2: 状态机的状态存在哪里？断电了怎么办？

**A:** 状态存在两个地方：
1. **内存**：当前请求的 State dict，请求结束就没了
2. **数据库**：`interview_states` 表存 checkpoint（当前存疑点、轮次、进度），`interview_messages` 表存完整对话历史

断电恢复：从数据库加载 checkpoint → 重建 State → 从断点继续。

### Q3: 条件分支的决策逻辑是什么？

**A:** `evaluate` 节点返回一个 `decision` 字段：

```python
if current_round >= 3 or score >= 75:
    # 追问轮次到上限 或 回答质量够好 → 切换下一个存疑点
    decision = "next_point"
elif all_points_done:
    decision = "report"
else:
    # 回答不够好，继续追问
    decision = "follow_up"
```

### Q4: 如果 LLM 在 evaluate 阶段崩溃了怎么办？

**A:** 三层保护：
1. `call_llm_routed` 内部有 try-catch，失败返回 None
2. `evaluate_answer` 检测到 LLM 返回 None 时，降级到规则评分（按回答长度打分）
3. 规则评分也失败时，返回默认分数 60，流程继续

```python
if llm_result:
    score = llm_result.get("score", 60)
else:
    score, feedback = _rule_score_answer(answer_text, current_round)  # 降级
```

### Q5: 怎么保证面试不会无限进行？

**A:** 四重限制：
1. 每个存疑点最多 3 轮追问
2. 存疑点总数有限（3-6 个）
3. 用户可以随时跳过或结束
4. `MAX_QUESTIONS = 20` 全局上限

最坏情况：6 个存疑点 × 3 轮 = 18 个问题，加上跳过的情况也不会超过 20。
