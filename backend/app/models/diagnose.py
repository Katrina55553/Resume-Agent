"""诊断 Pydantic 模型

定义简历诊断相关的数据模型。
匹配设计文档中的存疑点结构：priority(high/medium/low), source_text, reason, probe_questions
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Optional
from datetime import datetime


class DoubtPoint(BaseModel):
    """存疑点"""
    id: str = Field(..., description="存疑点 ID")
    priority: Literal["high", "medium", "low"] = Field(..., description="优先级")
    source_text: str = Field(..., description="简历原文引用")
    reason: str = Field(..., description="存疑原因")
    probe_questions: List[str] = Field(default_factory=list, description="建议追问问题")

    @field_validator("probe_questions")
    @classmethod
    def check_questions(cls, v: List[str]) -> List[str]:
        if not v or len(v) == 0:
            raise ValueError("probe_questions 不能为空")
        if len(v) > 5:
            raise ValueError("最多 5 个追问问题")
        return v

    @field_validator("source_text")
    @classmethod
    def check_source(cls, v: str) -> str:
        if len(v) < 5:
            raise ValueError("原文引用过短")
        dangerous = ["忽略", "系统提示", "system prompt"]
        for kw in dangerous:
            if kw.lower() in v.lower():
                raise ValueError(f"疑似注入内容: {kw}")
        return v


class OverallAssessment(BaseModel):
    """整体评估"""
    completeness: int = Field(..., ge=0, le=100, description="简历完整度 0-100")
    tech_depth: Literal["low", "medium", "high"] = Field(..., description="技术亮点")
    match_level: Literal["low", "medium", "high"] = Field(..., description="经验匹配度")
    doubt_count: int = Field(..., description="存疑点数量")


class DiagnoseResult(BaseModel):
    """诊断结果"""
    session_id: str = Field(..., description="会话 ID")
    overall: OverallAssessment = Field(..., description="整体评估")
    doubt_points: List[DoubtPoint] = Field(default_factory=list, description="存疑点列表")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")
    diagnosed_at: datetime = Field(default_factory=datetime.utcnow, description="诊断时间")

    @field_validator("doubt_points")
    @classmethod
    def validate_points(cls, v: List[DoubtPoint]) -> List[DoubtPoint]:
        seen = set()
        for p in v:
            if p.source_text in seen:
                raise ValueError(f"重复引用: {p.source_text[:50]}")
            seen.add(p.source_text)
        return v
