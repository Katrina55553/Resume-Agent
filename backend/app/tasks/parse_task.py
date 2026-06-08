"""简历解析异步任务

使用 Celery 处理简历解析。
1. 提取文件文本（PDF/DOCX/TXT）
2. 调用 LLM 结构化解析（无 API key 时用简单规则）
"""

import json
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DBSession

from app.tasks.celery_app import celery_app
from app.core.config import settings
from app.core.llm import call_llm_json
from app.models.session import Session, SessionStatus
from app.utils.security.masking import mask_phone, mask_email, mask_id_card

# 延迟创建同步引擎
_sync_engine = None


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "")
        _sync_engine = create_engine(sync_db_url, echo=False)
    return _sync_engine


def _update_progress(session_id: str, progress: float, status: str = None):
    """更新数据库中的解析进度"""
    with DBSession(_get_sync_engine()) as db:
        session = db.get(Session, session_id)
        if session:
            session.progress = progress
            if status:
                session.status = status
            session.updated_at = datetime.utcnow()
            db.commit()


# ── 文本提取 ──────────────────────────────────────────────

def _extract_text_pdf(file_path: str) -> str:
    """用 pdfplumber 提取 PDF 文本"""
    import pdfplumber
    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def _extract_text_docx(file_path: str) -> str:
    """用 python-docx 提取 Word 文本"""
    from docx import Document
    doc = Document(file_path)
    return "\n".join(para.text for para in doc.paragraphs if para.text.strip())


def _extract_text(file_path: str) -> str:
    """根据文件类型提取文本"""
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return _extract_text_pdf(file_path)
    elif ext in (".docx", ".doc"):
        return _extract_text_docx(file_path)
    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return ""


# ── LLM 结构化解析 ────────────────────────────────────────

def _mask_raw_text(text: str) -> str:
    """脱敏简历原文中的手机号、邮箱、身份证号（发送给 LLM 前调用）"""
    # 手机号：13812345678 → 138****5678
    text = re.sub(
        r"(1[3-9]\d)\d{4}(\d{4})",
        lambda m: m.group(1) + "****" + m.group(2),
        text,
    )
    # 邮箱：zhangsan@example.com → z***n@example.com
    def _mask_email_match(m):
        local, domain = m.group(1), m.group(2)
        if len(local) <= 2:
            masked = "*" * len(local)
        else:
            masked = local[0] + "***" + local[-1]
        return f"{masked}@{domain}"
    text = re.sub(r"([\w.+-]+)@([\w-]+\.[\w.-]+)", _mask_email_match, text)
    # 身份证号
    text = re.sub(
        r"(\d{4})\d{10}(\d{4})",
        lambda m: m.group(1) + "**********" + m.group(2),
        text,
    )
    return text


def _llm_parse(raw_text: str) -> dict:
    """调用 LLM API 进行结构化解析"""
    masked_text = _mask_raw_text(raw_text[:4000])

    result = call_llm_json(
        system_prompt="你是简历解析专家。只返回 JSON，不要其他文字。",
        user_prompt=f"""请从以下简历原文中提取结构化信息。

要求：
- 字段：name, phone, email, summary, work_experience(数组), education(数组), projects(数组), skills(数组), certifications(数组)
- work_experience 每项：company, position, start_date, end_date, description, achievements(数组)
- education 每项：school, degree, major, start_date, end_date
- projects 每项：name, role, description, technologies(数组), achievements(数组)
- skills 每项：category, skills(数组)
- 手机号已脱敏，保持原样即可
- 如某字段信息缺失用 null 或空数组

简历原文：
{masked_text}""",
    )
    if result:
        return result
    raise ValueError("LLM 返回内容无法解析为 JSON")


def _rule_based_parse(raw_text: str) -> dict:
    """简单规则解析（无 API key 时的降级方案）

    用正则从简历原文中提取基本信息。
    """
    lines = raw_text.strip().split("\n")
    first_line = lines[0].strip() if lines else ""

    # 尝试提取姓名（第一行通常是姓名）
    name = first_line if len(first_line) <= 10 and not any(c.isdigit() for c in first_line) else None

    # 提取手机号
    phone_match = re.search(r"1[3-9]\d{9}", raw_text)
    phone = None
    if phone_match:
        p = phone_match.group()
        phone = p[:3] + "****" + p[7:]

    # 提取邮箱
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", raw_text)
    email = email_match.group() if email_match else None

    # 提取技能关键词（常见技术栈）
    tech_keywords = [
        "Python", "Java", "Go", "JavaScript", "TypeScript", "C++", "Rust",
        "React", "Vue", "Angular", "Node.js", "Django", "Flask", "FastAPI", "Spring",
        "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
        "Docker", "Kubernetes", "K8s", "AWS", "Linux", "Git",
        "HTML", "CSS", "Tailwind", "Webpack", "Vite",
        "Kafka", "RabbitMQ", "Nginx", "GraphQL", "gRPC",
    ]
    found_skills = [kw for kw in tech_keywords if re.search(rf"\b{re.escape(kw)}\b", raw_text, re.IGNORECASE)]

    # 按段落拆分简历
    sections = re.split(r"\n\s*\n", raw_text)

    work_experience = []
    education = []
    projects = []

    for section in sections:
        s = section.strip()
        if not s:
            continue
        # 简单启发：包含"公司"或"实习"或"工程师"的段落 → 工作经历
        if any(kw in s for kw in ["公司", "实习", "工程师", "开发", "在职", "至今"]):
            work_experience.append({
                "company": s.split("\n")[0][:30] if "\n" in s else s[:30],
                "position": "",
                "start_date": None,
                "end_date": None,
                "description": s[:200],
                "achievements": [],
            })
        # 包含"大学"或"学院"或"学历" → 教育经历
        elif any(kw in s for kw in ["大学", "学院", "本科", "硕士", "博士", "学历"]):
            education.append({
                "school": s.split("\n")[0][:30],
                "degree": "",
                "major": "",
                "start_date": None,
                "end_date": None,
            })
        # 包含"项目" → 项目经历
        elif "项目" in s:
            projects.append({
                "name": s.split("\n")[0][:30],
                "role": None,
                "description": s[:200],
                "technologies": [],
                "achievements": [],
            })

    skills = [{"category": "技术栈", "skills": found_skills}] if found_skills else []

    return {
        "name": name,
        "phone": phone,
        "email": email,
        "summary": raw_text[:200] if raw_text else None,
        "work_experience": work_experience,
        "education": education,
        "projects": projects,
        "skills": skills,
        "certifications": [],
        "raw_text": raw_text[:2000],
    }


def _parse_resume(file_path: str) -> dict:
    """解析简历：提取文本 → LLM/规则解析"""
    raw_text = _extract_text(file_path)
    if not raw_text.strip():
        raise ValueError("文件内容为空或无法提取文本")

    # 有 API key 用 LLM，否则用规则
    if settings.LLM_API_KEY:
        try:
            result = _llm_parse(raw_text)
        except Exception:
            result = _rule_based_parse(raw_text)
    else:
        result = _rule_based_parse(raw_text)

    # raw_text 脱敏后存储（保护用户隐私）
    result["raw_text"] = _mask_raw_text(raw_text[:2000])
    return result


# ── Celery 任务 ───────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.tasks.parse_task.parse_resume",
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,
)
def parse_resume(self, session_id: str, file_path: str) -> dict:
    """解析简历文件"""
    try:
        _update_progress(session_id, 0.1, SessionStatus.PARSING)
        time.sleep(0.3)

        # 提取文本 + 解析
        _update_progress(session_id, 0.3)
        parsed_data = _parse_resume(file_path)

        _update_progress(session_id, 0.7)

        # 保存结果
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

        return {"session_id": session_id, "status": "parsed"}

    except Exception as exc:
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
        raise self.retry(exc=exc)
