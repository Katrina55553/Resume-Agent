"""诊断路由

处理简历诊断请求：触发诊断、查询诊断结果。
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any

from app.core.database import get_db
from app.models.session import Session, SessionStatus
from app.tasks.diagnose_task import diagnose_resume

router = APIRouter()


@router.post("/sessions/{session_id}/diagnose")
async def start_diagnose(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """触发简历诊断

    前提：简历已解析完成（status=parsed）
    流程：校验状态 → 触发 Celery 异步诊断
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
            "message": f"请先完成解析确认，当前状态: {session.status.value}",
        })

    # 更新状态为诊断中
    session.status = SessionStatus.DIAGNOSING
    session.progress = 0.0
    await db.flush()

    # 触发 Celery 异步诊断
    task = diagnose_resume.delay(session_id)

    return {
        "code": 0,
        "message": "诊断已启动",
        "data": {
            "session_id": session_id,
            "task_id": task.id,
            "status": "diagnosing",
        },
    }


@router.get("/sessions/{session_id}/diagnose")
async def get_diagnose_result(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """获取诊断结果

    诊断完成后返回：整体评估 + 存疑点列表 + 改进建议
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

    if session.status not in (
        SessionStatus.DIAGNOSED,
        SessionStatus.INTERVIEWING,
        SessionStatus.COMPLETED,
    ):
        # 诊断中，返回进度
        if session.status == SessionStatus.DIAGNOSING:
            return {
                "code": 0,
                "message": "诊断进行中",
                "data": {
                    "session_id": session_id,
                    "status": "diagnosing",
                    "progress": session.progress,
                },
            }
        raise HTTPException(status_code=400, detail={
            "code": 1003,
            "message": f"诊断尚未完成，当前状态: {session.status.value}",
        })

    # 从 parsed_content 中提取诊断结果（存储在同一个 session 记录中）
    parsed = json.loads(session.parsed_content) if session.parsed_content else {}
    diagnose_data = parsed.get("diagnose_result", {})

    return {
        "code": 0,
        "message": "success",
        "data": {
            "session_id": session_id,
            "status": "diagnosed",
            "result": diagnose_data,
        },
    }
