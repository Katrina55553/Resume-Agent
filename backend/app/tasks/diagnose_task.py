"""简历诊断异步任务

使用 Celery 处理简历诊断，识别存疑点。
LLM 可用时调用 DeepSeek，否则降级到规则诊断。
"""

import json
import uuid
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DBSession

from app.core.config import settings
from app.core.llm import call_llm_json, is_llm_available
from app.models.session import Session, SessionStatus
from app.tasks.celery_app import celery_app

# 延迟创建同步引擎
_sync_engine = None


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "")
        _sync_engine = create_engine(sync_db_url, echo=False)
    return _sync_engine


# ---------- LLM 诊断 ----------

_DIAGNOSE_SYSTEM_PROMPT = """你是资深简历顾问和面试官。请分析以下简历的结构化数据，找出面试中需要重点验证的存疑点。

存疑点类型：
- 数据夸大（如"日均百万订单"需要验证真实性）
- 技术深度不足（列了技术栈但没体现实际使用经验）
- 描述模糊（"优化了性能"但没说怎么优化、效果如何）
- 逻辑矛盾（时间线重叠、职位与职责不匹配）
- 缺乏量化（只说"负责"但没有成果数据）

返回 JSON 格式：
{
  "overall": {
    "completeness": 0-100（简历完整度评分）,
    "tech_depth": "low"|"medium"|"high",
    "match_level": "low"|"medium"|"high",
    "doubt_count": 存疑点数量
  },
  "doubt_points": [
    {
      "id": "简短唯一ID",
      "priority": "high"|"medium"|"low",
      "source_text": "简历中的原文引用",
      "reason": "为什么这是存疑点",
      "probe_questions": ["面试中应该问的问题1", "问题2", "问题3"]
    }
  ],
  "suggestions": ["改进建议1", "建议2", "建议3"]
}

要求：
- 只返回 JSON，不要其他文字
- 存疑点 3-6 个，按优先级排序
- probe_questions 每个存疑点 2-3 个，问题要具体、可验证
- suggestions 3-5 条，针对简历改进"""


def _llm_diagnose(parsed_data: dict) -> dict:
    """调用 LLM 进行简历诊断"""
    # 只取关键字段，控制 token 量
    resume_summary = {
        "name": parsed_data.get("name"),
        "summary": parsed_data.get("summary"),
        "work_experience": parsed_data.get("work_experience", []),
        "education": parsed_data.get("education", []),
        "projects": parsed_data.get("projects", []),
        "skills": parsed_data.get("skills", []),
    }
    user_prompt = f"简历结构化数据：\n{json.dumps(resume_summary, ensure_ascii=False, indent=2)}"

    result = call_llm_json(_DIAGNOSE_SYSTEM_PROMPT, user_prompt)
    if result and "doubt_points" in result:
        # 确保每个存疑点有 id
        for point in result["doubt_points"]:
            if "id" not in point:
                point["id"] = str(uuid.uuid4())[:8]
        return result
    return None


# ---------- 规则诊断（降级方案）----------

def _rule_diagnose(parsed_data: dict) -> dict:
    """基于规则的诊断（LLM 不可用时的降级方案）"""
    doubt_points = []

    # 检查工作经历
    for exp in parsed_data.get("work_experience", []):
        desc = exp.get("description", "")
        achievements = exp.get("achievements", [])
        company = exp.get("company", "未知公司")

        # 没有量化数据的成就
        if achievements:
            for ach in achievements:
                if any(c.isdigit() for c in ach) and any(
                    kw in ach for kw in ["万", "千", "%", "倍", "提升", "降低", "优化"]
                ):
                    doubt_points.append({
                        "id": str(uuid.uuid4())[:8],
                        "priority": "high",
                        "source_text": ach,
                        "reason": "包含量化数据，需验证真实性和个人贡献度",
                        "probe_questions": [
                            f"能详细说说「{ach[:30]}」这个成果吗？具体是怎么做到的？",
                            "这个数据是怎么衡量的？有监控或报表支撑吗？",
                            "你在其中具体负责哪个部分？",
                        ],
                    })

        # 描述过于模糊
        if desc and len(desc) > 10 and not any(
            kw in desc for kw in ["负责", "参与", "主导", "开发", "设计", "优化"]
        ):
            doubt_points.append({
                "id": str(uuid.uuid4())[:8],
                "priority": "medium",
                "source_text": f"{company}: {desc[:50]}",
                "reason": "工作描述较模糊，缺乏具体职责说明",
                "probe_questions": [
                    f"在{company}你的具体职责是什么？",
                    "能举一个你主导的项目或任务吗？",
                ],
            })

    # 检查项目经历
    for proj in parsed_data.get("projects", []):
        techs = proj.get("technologies", [])
        desc = proj.get("description", "")
        name = proj.get("name", "未知项目")

        if techs and len(techs) > 3:
            doubt_points.append({
                "id": str(uuid.uuid4())[:8],
                "priority": "medium",
                "source_text": f"{name}: {', '.join(techs[:5])}",
                "reason": "技术栈列举较多，需验证实际使用深度",
                "probe_questions": [
                    f"在{ name}项目中，你最精通哪个技术？能说说踩过什么坑吗？",
                    "这些技术中哪些是你独立选型的？选型依据是什么？",
                ],
            })

    # 检查技能
    for skill_group in parsed_data.get("skills", []):
        skills = skill_group.get("skills", [])
        if len(skills) > 8:
            doubt_points.append({
                "id": str(uuid.uuid4())[:8],
                "priority": "low",
                "source_text": f"技能: {', '.join(skills[:8])}...",
                "reason": "技能列举较多，需区分熟练程度",
                "probe_questions": [
                    "这些技能中哪些是你日常使用的？哪些只是了解？",
                ],
            })

    # 如果没有识别出存疑点，添加一个通用的
    if not doubt_points:
        doubt_points.append({
            "id": str(uuid.uuid4())[:8],
            "priority": "low",
            "source_text": parsed_data.get("summary", "")[:50] or "简历整体",
            "reason": "简历信息较少，需要在面试中深入了解",
            "probe_questions": [
                "能详细介绍一下你最近的一个项目吗？",
                "你在团队中通常扮演什么角色？",
            ],
        })

    return {
        "overall": {
            "completeness": 70,
            "tech_depth": "medium",
            "match_level": "medium",
            "doubt_count": len(doubt_points),
        },
        "doubt_points": doubt_points,
        "suggestions": [
            "建议在简历中加入更多量化数据",
            "项目描述应体现具体的技术方案和成果",
            "技能列表建议标注熟练程度",
        ],
    }


# ---------- Celery 任务 ----------

@celery_app.task(
    bind=True,
    name="app.tasks.diagnose_task.diagnose_resume",
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,
)
def diagnose_resume(self, session_id: str) -> dict:
    """诊断简历"""
    try:
        engine = _get_sync_engine()

        with DBSession(engine) as db:
            session = db.get(Session, session_id)
            if not session:
                return {"session_id": session_id, "status": "error", "message": "会话不存在"}

            session.progress = 0.2
            session.updated_at = datetime.utcnow()
            db.commit()

            parsed_data = json.loads(session.parsed_content) if session.parsed_content else {}

        # LLM 诊断，失败降级到规则
        if is_llm_available():
            diagnose_result = _llm_diagnose(parsed_data)
            if diagnose_result is None:
                diagnose_result = _rule_diagnose(parsed_data)
        else:
            diagnose_result = _rule_diagnose(parsed_data)

        # 保存诊断结果
        with DBSession(engine) as db:
            session = db.get(Session, session_id)
            session.progress = 0.9

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
        raise self.retry(exc=exc) from exc
