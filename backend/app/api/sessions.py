"""会话管理路由

处理简历上传和会话状态查询。
"""

import os
import uuid as uuid_lib
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any

from app.core.database import get_db
from app.core.config import settings
from app.models.session import Session, SessionStatus
from app.utils.security.file_upload import validate_upload_file
from app.utils.security.masking import mask_phone, mask_email, mask_name
from app.tasks.parse_task import parse_resume

router = APIRouter()

# 上传文件存储目录
UPLOAD_DIR = Path("uploads")


@router.post("/sessions")
async def create_session(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """创建会话并上传简历

    流程：四重校验 → 保存文件 → 创建 DB 记录 → 触发 Celery 异步解析
    """
    # 1. 文件四重校验（扩展名/MIME/魔数/大小）
    await validate_upload_file(file)

    # 2. 生成会话 ID，随机重命名文件防碰撞
    session_id = uuid_lib.uuid4()
    ext = Path(file.filename).suffix.lower()
    safe_filename = f"{session_id}{ext}"

    # 二级目录分散存储：uploads/ab/abcd1234-.../resume.pdf
    sub_dir = UPLOAD_DIR / str(session_id)[:2]
    sub_dir.mkdir(parents=True, exist_ok=True)
    file_path = sub_dir / safe_filename

    # 3. 保存文件到磁盘
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # 4. 创建数据库记录
    session = Session(
        id=session_id,
        status=SessionStatus.UPLOADED,
        original_filename=file.filename,
        file_path=str(file_path),
        file_size=f"{len(content) / 1024:.1f}KB",
        mime_type=file.content_type,
        progress=0.0,
    )
    db.add(session)
    await db.flush()

    # 5. 触发 Celery 异步解析任务
    task = parse_resume.delay(str(session_id), str(file_path))

    # 更新状态为解析中
    session.status = SessionStatus.PARSING
    await db.flush()

    return {
        "code": 0,
        "message": "简历已上传，正在解析",
        "data": {
            "session_id": str(session_id),
            "task_id": task.id,
            "status": "parsing",
        },
    }


@router.get("/sessions/{session_id}/status")
async def get_session_status(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """查询会话解析进度

    前端轮询此接口，直到 status 变为 parsed 或 failed。
    """
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail={
            "code": 1002,
            "message": "会话不存在",
        })

    data = {
        "session_id": str(session.id),
        "status": session.status.value,
        "progress": session.progress,
    }

    # 解析完成时附带结果摘要
    if session.status == SessionStatus.PARSED:
        data["parsed_at"] = session.parsed_at.isoformat() if session.parsed_at else None

    if session.status == SessionStatus.FAILED:
        data["error"] = session.parse_error

    return {
        "code": 0,
        "message": "success",
        "data": data,
    }


@router.get("/sessions/{session_id}/parse")
async def get_parse_result(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """获取简历解析结果

    解析完成后返回结构化数据，供前端展示和用户修正。
    """
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail={
            "code": 1002,
            "message": "会话不存在",
        })

    if session.status not in (SessionStatus.PARSED, SessionStatus.DIAGNOSING, SessionStatus.DIAGNOSED, SessionStatus.INTERVIEWING, SessionStatus.COMPLETED):
        raise HTTPException(status_code=400, detail={
            "code": 1003,
            "message": f"解析尚未完成，当前状态: {session.status.value}",
        })

    import json
    parsed_data = json.loads(session.parsed_content) if session.parsed_content else {}

    # 脱敏敏感字段（安全网：防止解析器遗漏）
    if parsed_data.get("phone"):
        parsed_data["phone"] = mask_phone(str(parsed_data["phone"]))
    if parsed_data.get("email"):
        parsed_data["email"] = mask_email(str(parsed_data["email"]))
    if parsed_data.get("name"):
        parsed_data["name"] = mask_name(str(parsed_data["name"]))

    return {
        "code": 0,
        "message": "success",
        "data": {
            "session_id": str(session.id),
            "status": session.status.value,
            "parsed_data": parsed_data,
        },
    }


@router.put("/sessions/{session_id}/parse")
async def update_parse_result(
    session_id: str,
    body: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """用户修正解析结果

    前端内联编辑后提交修正，更新 parsed_content。
    """
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail={
            "code": 1002,
            "message": "会话不存在",
        })

    if session.status != SessionStatus.PARSED:
        raise HTTPException(status_code=400, detail={
            "code": 1003,
            "message": f"仅在解析完成状态可修正，当前状态: {session.status.value}",
        })

    import json
    session.parsed_content = json.dumps(body.get("parsed_data", {}), ensure_ascii=False)
    session.updated_at = datetime.utcnow()
    await db.flush()

    return {
        "code": 0,
        "message": "解析结果已更新",
        "data": {
            "session_id": str(session.id),
            "status": session.status.value,
        },
    }
