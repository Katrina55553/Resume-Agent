"""LangGraph 状态机

定义面试流程的状态图。
"""

from typing import Any

from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.nodes.question import generate_question
from app.agent.nodes.collect import collect_answer
from app.agent.nodes.evaluate import evaluate_answer
from app.agent.nodes.report import generate_report
from app.agent.rules import should_force_switch


def should_continue(state: dict[str, Any]) -> str:
    """判断是否继续面试

    Args:
        state: Agent 状态

    Returns:
        下一个节点名称
    """
    # 检查是否强制结束
    if state.get("force_end"):
        return "generate_report"

    # 检查规则
    force_switch, reason = should_force_switch(
        follow_up_count=state.get("follow_up_count", 0),
        error_count=state.get("error_count", 0),
        total_tokens=state.get("total_tokens", 0),
        question_count=state.get("question_count", 0),
    )

    if force_switch:
        if "结束面试" in (reason or ""):
            return "generate_report"
        return "generate_question"

    # 根据评估结果决定
    if state.get("should_switch_topic"):
        return "generate_question"

    return "generate_question"


def create_interview_graph() -> StateGraph:
    """创建面试状态图

    Returns:
        编译后的状态图
    """
    # 创建状态图
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("generate_question", generate_question)
    graph.add_node("collect_answer", collect_answer)
    graph.add_node("evaluate_answer", evaluate_answer)
    graph.add_node("generate_report", generate_report)

    # 设置入口
    graph.set_entry_point("generate_question")

    # 添加边
    graph.add_edge("generate_question", "collect_answer")
    graph.add_edge("collect_answer", "evaluate_answer")

    # 条件边：根据评估结果决定下一步
    graph.add_conditional_edges(
        "evaluate_answer",
        should_continue,
        {
            "generate_question": "generate_question",
            "generate_report": "generate_report",
        },
    )

    # 报告生成后结束
    graph.add_edge("generate_report", END)

    return graph.compile()


# 全局状态图实例
interview_graph = create_interview_graph()
