"""报告路由

查询面试评估报告。
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any

from app.core.database import get_db
from app.models.session import Session, SessionStatus
from app.models.interview import InterviewStateORM

router = APIRouter()


@router.get("/sessions/{session_id}/report")
async def get_report(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """获取面试评估报告

    从 InterviewStateORM 中读取 report 字段。
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

    # 获取面试状态
    intv_result = await db.execute(
        select(InterviewStateORM).where(InterviewStateORM.session_id == session_id)
    )
    interview = intv_result.scalar_one_or_none()

    if not interview:
        raise HTTPException(status_code=404, detail={
            "code": 1004,
            "message": "面试记录不存在",
        })

    if not interview.is_completed:
        return {
            "code": 0,
            "message": "面试尚未完成",
            "data": {
                "session_id": session_id,
                "status": "interviewing",
            },
        }

    report = {}
    if interview.report_json:
        try:
            report = json.loads(interview.report_json)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "code": 0,
        "message": "success",
        "data": {
            "session_id": session_id,
            "status": "completed",
            "report": report,
        },
    }
