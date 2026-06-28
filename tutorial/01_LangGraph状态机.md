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
    # 会话信息
    session_id: str
    interview_id: str

    # 简历数据
    resume_text: str | None
    resume_summary: str | None
    doubt_points: list[dict]        # 存疑点列表

    # 面试状态
    phase: str                      # InterviewPhase value
    question_count: int             # 已问问题总数
    follow_up_count: int            # 当前问题追问次数
    error_count: int                # 连续错误次数
    total_tokens: int               # 累计 token

    # 当前问题和回答
    current_question: str | None
    current_answer: str | None

    # 消息历史（使用 Annotated 支持 reducer，自动合并）
    messages: Annotated[list[dict], add]

    # 评估结果
    current_evaluation: dict | None
    should_switch_topic: bool       # 是否切换存疑点
    force_end: bool                 # 是否强制结束

    # 最终报告
    report: dict | None
```

> **注意**：实际运行时 `ws.py` / `mcp/server.py` 加载状态会额外补充 `current_point_index`、`current_round`、`point_states`、`decision`、`evaluations`、`resume_data` 等字段（从 DB checkpoint 恢复）。`AgentState` TypedDict 是 LangGraph 编译时的最小集合，运行时 state 是个动态 dict。

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

# evaluate.py - 评估回答并返回 decision
async def evaluate_answer(state: dict) -> dict:
    score, feedback = llm_evaluate(state)
    # 返回 decision 字段供 ws.py/mcp 分支处理
    if current_round >= MAX_FOLLOW_UP or score >= 75:
        if next_index >= len(doubt_points):
            return {"current_evaluation": {...}, "decision": "report",
                    "is_completed": True}
        return {"current_evaluation": {...}, "decision": "next_point",
                "current_point_index": next_index, "current_round": 1}
    return {"current_evaluation": {...}, "decision": "follow_up",
            "current_round": current_round + 1}
```

### 条件分支

`graph.py` 的条件边只走两条出路——继续问 或 生成报告。具体的 follow_up / next_point 区分在 `evaluate_answer` 内部决定，并通过 `decision` 字段透传给上层（`ws.py` / `mcp/server.py`）：

```python
# graph.py
def should_continue(state: dict) -> str:
    # 1. 强制结束 → 直接生成报告
    if state.get("force_end"):
        return "generate_report"

    # 2. 规则熔断（追问超限 / 错误超限 / token 超限 / 问题数超限）
    force_switch, reason = should_force_switch(...)
    if force_switch:
        return "generate_report" if "结束面试" in reason else "generate_question"

    # 3. 评估结果决定
    if state.get("should_switch_topic"):
        return "generate_question"
    return "generate_question"

# 条件边只有两个目标
graph.add_conditional_edges("evaluate_answer", should_continue, {
    "generate_question": "generate_question",  # 追问或切换下一个
    "generate_report": "generate_report",      # 生成最终报告
})
```

> **关键点**：graph 层只关心"继续 or 结束"，`evaluate_answer` 返回的 `decision` 字段（follow_up / next_point / report）是给上层业务代码用的——`ws.py` 收到 decision=report 时调 `generate_report`，收到 follow_up/next_point 时调 `generate_question` 流式生成下一个问题。

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

**A:** `evaluate_answer` 节点返回一个 `decision` 字段，分三种情况：

```python
# evaluate.py 实际逻辑
if current_round >= MAX_FOLLOW_UP or score >= 75:
    # 追问轮次到上限(3) 或 回答质量够好(≥75) → 当前点 resolved
    point_states[current_point_id] = "resolved"
    next_index = point_index + 1
    if next_index >= len(doubt_points):
        # 所有点都问完 → 生成报告
        decision = "report"
    else:
        # 切换到下一个存疑点
        decision = "next_point"
        point_states[next_point_id] = "active"
else:
    # 回答不够好，继续追问
    decision = "follow_up"
    current_round += 1
```

> graph.py 的 `should_continue` 不读 `decision`，它读 `force_end` 和 `should_switch_topic`。`decision` 是给 `ws.py` / `mcp/server.py` 用的——它们据此决定调 `generate_report` 还是 `generate_question`。

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
