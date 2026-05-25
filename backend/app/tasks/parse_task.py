"""简历解析异步任务

使用 Celery 处理简历解析，通过 Redis 更新进度。
"""

import json
import time
import asyncio
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DBSession

from app.tasks.celery_app import celery_app
from app.core.config import settings
from app.models.session import Session, SessionStatus

# 延迟创建同步引擎（Celery worker 使用同步 DB 连接）
_sync_engine = None


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "")
        _sync_engine = create_engine(sync_db_url, echo=False)
    return _sync_engine


def _update_progress(session_id: str, progress: float, status: str = None):
    """同步更新数据库中的解析进度"""
    with DBSession(_get_sync_engine()) as db:
        session = db.get(Session, session_id)
        if session:
            session.progress = progress
            if status:
                session.status = status
            session.updated_at = datetime.utcnow()
            db.commit()


def _mock_parse_resume(file_path: str) -> dict:
    """模拟简历解析（后续替换为真实 LLM 调用）

    读取文件内容，返回模拟的结构化解析结果。
    """
    # 读取文件内容（纯文本部分）
    raw_text = ""
    try:
        if file_path.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read()
        else:
            # PDF/DOCX 暂时返回占位文本，后续集成解析库
            raw_text = f"[简历文件: {file_path}]"
    except Exception:
        raw_text = "[文件读取失败]"

    # 模拟 LLM 解析返回的结构化数据
    return {
        "name": "张三",
        "phone": "138****1234",
        "email": "zhangsan@example.com",
        "summary": "3年后端开发经验，熟悉 Python/Go 微服务架构",
        "work_experience": [
            {
                "company": "XX科技有限公司",
                "position": "后端开发工程师",
                "start_date": "2022-07",
                "end_date": "至今",
                "description": "负责订单系统核心模块开发",
                "achievements": [
                    "日均处理10万+订单",
                    "优化慢查询，响应时间降低40%",
                ],
            }
        ],
        "education": [
            {
                "school": "XX大学",
                "degree": "本科",
                "major": "计算机科学与技术",
                "start_date": "2018-09",
                "end_date": "2022-06",
            }
        ],
        "projects": [
            {
                "name": "订单系统重构",
                "role": "核心开发",
                "description": "使用微服务架构重构单体订单系统",
                "technologies": ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker"],
                "achievements": ["系统可用性从 99.5% 提升至 99.99%"],
            }
        ],
        "skills": [
            {"category": "编程语言", "skills": ["Python", "Go", "SQL"]},
            {"category": "框架", "skills": ["FastAPI", "Django", "Gin"]},
            {"category": "数据库", "skills": ["PostgreSQL", "MySQL", "Redis"]},
            {"category": "工具", "skills": ["Docker", "Kubernetes", "Git"]},
        ],
        "certifications": [],
        "raw_text": raw_text[:500],
    }


@celery_app.task(
    bind=True,
    name="app.tasks.parse_task.parse_resume",
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,
)
def parse_resume(self, session_id: str, file_path: str) -> dict:
    """解析简历文件

    流程：更新进度 10% → 读取文件 30% → LLM 解析 70% → 保存结果 100%
    """
    try:
        # 步骤1：开始解析
        _update_progress(session_id, 0.1, SessionStatus.PARSING)
        time.sleep(0.5)  # 模拟耗时

        # 步骤2：读取文件
        _update_progress(session_id, 0.3)
        time.sleep(0.5)

        # 步骤3：调用 LLM 解析（模拟）
        _update_progress(session_id, 0.5)
        parsed_data = _mock_parse_resume(file_path)
        time.sleep(1.0)

        # 步骤4：保存结果到数据库
        _update_progress(session_id, 0.8)

        with DBSession(_get_sync_engine()) as db:
            session = db.get(Session, session_id)
            if session:
                session.status = SessionStatus.PARSED
                session.progress = 1.0
                session.parsed_content = json.dumps(parsed_data, ensure_ascii=False)
                session.parsed_at = datetime.utcnow()
                session.updated_at = datetime.utcnow()
                db.commit()

        _update_progress(session_id, 1.0)

        return {
            "session_id": session_id,
            "status": "parsed",
            "parsed_data": parsed_data,
        }

    except Exception as exc:
        # 解析失败，记录错误
        try:
            with DBSession(_get_sync_engine()) as db:
                session = db.get(Session, session_id)
                if session:
                    session.status = SessionStatus.FAILED
                    session.parse_error = str(exc)
                    session.updated_at = datetime.utcnow()
                    db.commit()
        except Exception:
            pass

        # 重试
        raise self.retry(exc=exc)
