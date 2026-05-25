"""面试状态模型

定义面试过程中的状态和消息模型。
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime
from enum import Enum


class InterviewPhase(str, Enum):
    """面试阶段"""
    INTRO = "intro"  # 自我介绍
    RESUME_DEEP_DIVE = "resume_deep_dive"  # 简历深挖
    TECHNICAL = "technical"  # 技术问题
    BEHAVIORAL = "behavioral"  # 行为问题
    CLOSING = "closing"  # 结束阶段


class MessageRole(str, Enum):
    """消息角色"""
    ASSISTANT = "assistant"
    USER = "user"
    SYSTEM = "system"


class InterviewMessage(BaseModel):
    """面试消息"""
    role: MessageRole = Field(..., description="消息角色")
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="消息时间")
    phase: Optional[InterviewPhase] = Field(None, description="面试阶段")
    metadata: Optional[dict] = Field(None, description="元数据")


class InterviewState(BaseModel):
    """面试状态"""
    interview_id: str = Field(..., description="面试 ID")
    session_id: str = Field(..., description="会话 ID")
    phase: InterviewPhase = Field(default=InterviewPhase.INTRO, description="当前阶段")
    question_count: int = Field(default=0, description="已问问题数")
    follow_up_count: int = Field(default=0, description="当前问题追问数")
    error_count: int = Field(default=0, description="错误次数")
    total_tokens: int = Field(default=0, description="已用 Token 数")
    messages: List[InterviewMessage] = Field(default_factory=list, description="消息历史")
    started_at: datetime = Field(default_factory=datetime.utcnow, description="开始时间")
    is_completed: bool = Field(default=False, description="是否完成")

    class Config:
        use_enum_values = True
