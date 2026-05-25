"""诊断 Pydantic 模型

定义简历诊断相关的数据模型。
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime


class DoubtPoint(BaseModel):
    """简历疑点"""
    category: str = Field(..., description="疑点类别：gap/overclaim/vague/inconsistency")
    description: str = Field(..., description="疑点描述")
    severity: int = Field(..., ge=1, le=5, description="严重程度 1-5")
    related_section: Optional[str] = Field(None, description="相关简历部分")
    suggested_question: Optional[str] = Field(None, description="建议追问问题")

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """校验疑点类别"""
        allowed_categories = ["gap", "overclaim", "vague", "inconsistency", "other"]
        if v not in allowed_categories:
            raise ValueError(f"疑点类别必须是 {allowed_categories} 之一")
        return v


class DiagnoseResult(BaseModel):
    """诊断结果"""
    session_id: str = Field(..., description="会话 ID")
    score: int = Field(..., ge=0, le=100, description="简历评分 0-100")
    strengths: List[str] = Field(default_factory=list, description="简历亮点")
    weaknesses: List[str] = Field(default_factory=list, description="简历不足")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")
    doubt_points: List[DoubtPoint] = Field(default_factory=list, description="疑点列表")
    interview_topics: List[str] = Field(default_factory=list, description="建议面试主题")
    diagnosed_at: datetime = Field(default_factory=datetime.utcnow, description="诊断时间")

    @field_validator("score")
    @classmethod
    def validate_score(cls, v: int) -> int:
        """校验分数范围"""
        if not 0 <= v <= 100:
            raise ValueError("分数必须在 0-100 之间")
        return v
