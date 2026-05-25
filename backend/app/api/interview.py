"""面试路由

处理面试会话管理。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List

from app.core.database import get_db

router = APIRouter()


@router.post("/interview/{session_id}/start")
async def start_interview(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """启动模拟面试

    Args:
        session_id: 会话 ID
        db: 数据库会话

    Returns:
        面试会话信息
    """
    # TODO: 初始化 Agent 状态，生成第一个问题
    return {
        "session_id": session_id,
        "interview_id": "placeholder-interview-id",
        "status": "started",
        "first_question": "请简单介绍一下你自己",
    }


@router.post("/interview/{interview_id}/answer")
async def submit_answer(
    interview_id: str,
    answer: Dict[str, str],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """提交面试回答

    Args:
        interview_id: 面试 ID
        answer: 用户回答
        db: 数据库会话

    Returns:
        下一个问题或面试结束信息
    """
    # TODO: 将回答传递给 Agent，获取下一个问题
    return {
        "interview_id": interview_id,
        "status": "answering",
        "next_question": "placeholder-next-question",
        "progress": 0.3,
    }


@router.get("/interview/{interview_id}/history")
async def get_interview_history(
    interview_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """获取面试历史

    Args:
        interview_id: 面试 ID
        db: 数据库会话

    Returns:
        问答历史列表
    """
    # TODO: 从数据库获取面试历史
    return [
        {"role": "assistant", "content": "请简单介绍一下你自己"},
        {"role": "user", "content": "我是..."},
    ]
