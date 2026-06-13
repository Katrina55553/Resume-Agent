"""会话 ORM 模型

定义会话相关的数据库表结构。
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Float, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class SessionStatus(enum.StrEnum):
    """会话状态枚举"""
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    DIAGNOSING = "diagnosing"
    DIAGNOSED = "diagnosed"
    INTERVIEWING = "interviewing"
    COMPLETED = "completed"
    FAILED = "failed"


class Session(Base):
    """会话表"""
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(100), nullable=True, index=True)
    status = Column(Enum(SessionStatus), default=SessionStatus.UPLOADED)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(String(50), nullable=True)
    mime_type = Column(String(100), nullable=True)

    # 解析进度 0.0 ~ 1.0
    progress = Column(Float, default=0.0)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    parsed_at = Column(DateTime, nullable=True)
    diagnosed_at = Column(DateTime, nullable=True)

    # 解析结果（JSON 字符串）
    parsed_content = Column(Text, nullable=True)
    parse_error = Column(Text, nullable=True)

    def __repr__(self):
        return f"<Session {self.id} - {self.status}>"
