"""简历解析模型

定义简历解析结果的 Pydantic 模型。
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class WorkExperience(BaseModel):
    """工作经历"""
    company: str = Field(..., description="公司名称")
    position: str = Field(..., description="职位")
    start_date: Optional[str] = Field(None, description="开始日期")
    end_date: Optional[str] = Field(None, description="结束日期")
    description: Optional[str] = Field(None, description="工作描述")
    achievements: list[str] = Field(default_factory=list, description="工作成就")


class Education(BaseModel):
    """教育经历"""
    school: str = Field(..., description="学校名称")
    degree: str = Field(..., description="学位")
    major: str = Field(..., description="专业")
    start_date: Optional[str] = Field(None, description="开始日期")
    end_date: Optional[str] = Field(None, description="结束日期")


class Project(BaseModel):
    """项目经历"""
    name: str = Field(..., description="项目名称")
    role: Optional[str] = Field(None, description="担任角色")
    description: Optional[str] = Field(None, description="项目描述")
    technologies: list[str] = Field(default_factory=list, description="技术栈")
    achievements: list[str] = Field(default_factory=list, description="项目成果")


class SkillCategory(BaseModel):
    """技能分类"""
    category: str = Field(..., description="技能类别")
    skills: list[str] = Field(..., description="技能列表")


class ResumeData(BaseModel):
    """简历解析结果"""
    name: Optional[str] = Field(None, description="姓名")
    phone: Optional[str] = Field(None, description="电话")
    email: Optional[str] = Field(None, description="邮箱")
    summary: Optional[str] = Field(None, description="个人简介")
    work_experience: list[WorkExperience] = Field(default_factory=list, description="工作经历")
    education: list[Education] = Field(default_factory=list, description="教育经历")
    projects: list[Project] = Field(default_factory=list, description="项目经历")
    skills: list[SkillCategory] = Field(default_factory=list, description="技能")
    certifications: list[str] = Field(default_factory=list, description="证书")
    parsed_at: datetime = Field(default_factory=datetime.utcnow, description="解析时间")
