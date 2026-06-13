"""面试状态模型

定义面试过程中的 ORM 模型和 Pydantic 模型。
ORM 模型负责数据库持久化，Pydantic 模型负责 API 交互。
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

# ============================================================
# ORM 模型 —— 面试状态 & 消息持久化
# ============================================================


class InterviewStateORM(Base):
    """面试状态表

    每次面试会话对应一行记录，记录当前进度和各存疑点处理状态。
    """
    __tablename__ = "interview_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id"),
        unique=True,
        nullable=False,
        index=True,
    )
    # 当前正在讨论的存疑点索引
    current_point_index = Column(Integer, default=0)
    # 当前存疑点的追问轮次（从 1 开始）
    current_round = Column(Integer, default=1)
    # 各存疑点状态：{point_id: pending|active|resolved|skipped}
    point_states = Column(JSON, default=dict)
    # 对话摘要（可选，用于长对话压缩）
    messages_summary = Column(Text, nullable=True)
    # 面试是否已结束
    is_completed = Column(Boolean, default=False)
    # 最终报告（JSON 字符串，面试完成后写入）
    report_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return (
            f"<InterviewState session={self.session_id} "
            f"point={self.current_point_index} round={self.current_round}>"
        )


class InterviewMessageORM(Base):
    """面试消息表

    保存面试过程中的每一条消息（AI 提问 / 用户回答）。
    """
    __tablename__ = "interview_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id"),
        nullable=False,
        index=True,
    )
    # 关联的存疑点 ID（AI 提问时填写，用户回答时可选）
    point_id = Column(String(100), nullable=True)
    # 消息角色："assistant" | "user"
    role = Column(String(20), nullable=False)
    # 消息内容
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<InterviewMessage role={self.role} "
            f"point={self.point_id} session={self.session_id}>"
        )


# ============================================================
# Pydantic 模型 —— API 请求 / 响应
# ============================================================


class InterviewStartResponse(BaseModel):
    """开始面试的响应"""
    session_id: str
    interview_id: str
    status: str = "started"
    first_question: str
    point_id: str
    round: int = 1
    total_points: int
    point_list: list[dict | None] = None


class InterviewRespondRequest(BaseModel):
    """提交回答的请求"""
    content: str = Field(..., min_length=1, max_length=5000, description="用户回答内容")


class InterviewRespondResponse(BaseModel):
    """提交回答的响应"""
    session_id: str
    decision: Literal["follow_up", "next_point", "report"]
    question: str | None = None
    point_id: str | None = None
    round: int | None = None
    point_states: dict[str, str | None] = None
    progress: float = 0.0
    report: dict | None = None


class InterviewResumeResponse(BaseModel):
    """恢复面试的响应"""
    session_id: str
    current_point_index: int
    current_round: int
    point_states: dict[str, str]
    messages: list[dict]
    is_completed: bool
    report: dict | None = None
    total_points: int
    current_question: str | None = None
    current_point_id: str | None = None
    point_list: list[dict | None] = None


class WSIncomingMessage(BaseModel):
    """WebSocket 接收的消息"""
    type: Literal["answer", "skip", "rephrase", "start"]
    content: str | None = None


class WSOutgoingMessage(BaseModel):
    """WebSocket 发送的消息"""
    type: Literal["question", "status", "complete", "error"]
    content: str | None = None
    point_id: str | None = None
    round: int | None = None
    point_states: dict[str, str | None] = None
    progress: float | None = None
    report: dict | None = None
    error: str | None = None
