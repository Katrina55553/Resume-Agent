"""会话管理路由

处理简历上传和会话状态查询。
"""

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.core.database import get_db

router = APIRouter()


@router.post("/sessions")
async def create_session(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """创建会话并上传简历

    Args:
        file: 上传的简历文件（PDF/DOCX）
        db: 数据库会话

    Returns:
        会话 ID 和初始状态
    """
    # TODO: 实现文件校验、存储、异步解析任务
    return {
        "session_id": "placeholder-session-id",
        "status": "uploaded",
        "message": "简历已上传，正在解析...",
    }


@router.get("/sessions/{session_id}/status")
async def get_session_status(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """查询会话解析进度

    Args:
        session_id: 会话 ID
        db: 数据库会话

    Returns:
        会话状态和解析进度
    """
    # TODO: 从数据库查询会话状态
    return {
        "session_id": session_id,
        "status": "parsing",
        "progress": 0.5,
        "message": "正在解析简历...",
    }
