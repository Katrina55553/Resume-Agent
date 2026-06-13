"""Agent 状态定义

定义 LangGraph 状态机使用的 TypedDict。
"""

from operator import add
from typing import Annotated, TypedDict


class AgentState(TypedDict):
    """Agent 状态

    用于 LangGraph 状态机流转的数据结构。
    """
    # 会话信息
    session_id: str
    interview_id: str

    # 简历数据
    resume_text: str | None
    resume_summary: str | None
    doubt_points: list[dict]

    # 面试状态
    phase: str  # InterviewPhase value
    question_count: int
    follow_up_count: int
    error_count: int
    total_tokens: int

    # 当前问题和回答
    current_question: str | None
    current_answer: str | None

    # 消息历史（使用 Annotated 支持 reducer）
    messages: Annotated[list[dict], add]

    # 评估结果
    current_evaluation: dict | None
    should_switch_topic: bool
    force_end: bool

    # 最终报告
    report: dict | None
