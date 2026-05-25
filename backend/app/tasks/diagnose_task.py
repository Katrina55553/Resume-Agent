"""简历诊断异步任务

使用 Celery 处理简历诊断，识别存疑点。
"""

import json
import time
import uuid
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DBSession

from app.tasks.celery_app import celery_app
from app.core.config import settings
from app.models.session import Session, SessionStatus

# 延迟创建同步引擎
_sync_engine = None


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "")
        _sync_engine = create_engine(sync_db_url, echo=False)
    return _sync_engine


def _mock_diagnose(parsed_data: dict) -> dict:
    """模拟 LLM 诊断（后续替换为真实 Claude API 调用）

    根据解析结果生成存疑点、整体评估、改进建议。
    """
    # 模拟从简历中识别存疑点
    doubt_points = [
        {
            "id": str(uuid.uuid4())[:8],
            "priority": "high",
            "source_text": "日均处理10万+订单",
            "reason": "10万是峰值还是日均？需验证数据真实性和个人贡献度",
            "probe_questions": [
                "10万是日均还是峰值？你在其中负责哪个模块？",
                "涉及哪些表操作？有事务吗？",
                "库存扣减有并发问题吗？怎么处理的？",
            ],
        },
        {
            "id": str(uuid.uuid4())[:8],
            "priority": "medium",
            "source_text": "优化慢查询，响应时间降低40%",
            "reason": "缺乏具体优化手段和衡量标准，需验证技术深度",
            "probe_questions": [
                "具体优化了哪些查询？用了什么手段？",
                "40% 是怎么衡量的？有监控数据吗？",
            ],
        },
        {
            "id": str(uuid.uuid4())[:8],
            "priority": "medium",
            "source_text": "使用微服务架构重构单体订单系统",
            "reason": "项目描述过于通用，缺乏设计决策和权衡说明",
            "probe_questions": [
                "为什么选择微服务而不是模块化单体？",
                "服务怎么拆分的？边界在哪？",
                "拆分过程中遇到最大的挑战是什么？",
            ],
        },
        {
            "id": str(uuid.uuid4())[:8],
            "priority": "low",
            "source_text": "Redis, Docker, Kubernetes",
            "reason": "技术栈列举但未体现深度使用经验",
            "probe_questions": [
                "Redis 在项目中具体怎么用的？缓存策略是什么？",
            ],
        },
    ]

    return {
        "overall": {
            "completeness": 78,
            "tech_depth": "medium",
            "match_level": "high",
            "doubt_count": len(doubt_points),
        },
        "doubt_points": doubt_points,
        "suggestions": [
            "量化数据需要更精确，建议加入具体指标和衡量方式",
            "项目描述加入'为什么做这个设计'，体现架构思考",
            "Redis 经验可以展开写缓存策略和踩坑经历",
            "建议补充系统可观测性相关经验（日志、监控、告警）",
        ],
    }


@celery_app.task(
    bind=True,
    name="app.tasks.diagnose_task.diagnose_resume",
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,
)
def diagnose_resume(self, session_id: str) -> dict:
    """诊断简历

    流程：读取解析结果 → LLM 识别存疑点 → 保存诊断结果
    """
    try:
        # 更新进度
        engine = _get_sync_engine()

        with DBSession(engine) as db:
            session = db.get(Session, session_id)
            if not session:
                return {"session_id": session_id, "status": "error", "message": "会话不存在"}

            session.progress = 0.2
            session.updated_at = datetime.utcnow()
            db.commit()

            # 获取解析结果
            parsed_data = json.loads(session.parsed_content) if session.parsed_content else {}

        time.sleep(0.5)

        # 模拟 LLM 诊断
        with DBSession(engine) as db:
            session = db.get(Session, session_id)
            session.progress = 0.5
            db.commit()

        time.sleep(1.0)

        diagnose_result = _mock_diagnose(parsed_data)

        # 保存诊断结果
        with DBSession(engine) as db:
            session = db.get(Session, session_id)
            session.progress = 0.9

            # 将诊断结果追加到 parsed_content 中
            existing = json.loads(session.parsed_content) if session.parsed_content else {}
            existing["diagnose_result"] = diagnose_result
            session.parsed_content = json.dumps(existing, ensure_ascii=False)

            session.status = SessionStatus.DIAGNOSED
            session.progress = 1.0
            session.diagnosed_at = datetime.utcnow()
            session.updated_at = datetime.utcnow()
            db.commit()

        return {
            "session_id": session_id,
            "status": "diagnosed",
            "result": diagnose_result,
        }

    except Exception as exc:
        try:
            with DBSession(_get_sync_engine()) as db:
                session = db.get(Session, session_id)
                if session:
                    session.status = SessionStatus.FAILED
                    session.parse_error = f"诊断失败: {exc}"
                    db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)
