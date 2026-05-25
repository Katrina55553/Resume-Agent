"""诊断路由

处理简历诊断请求。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.core.database import get_db
from app.models.diagnose import DiagnoseResult

router = APIRouter()


@router.post("/diagnose/{session_id}")
async def start_diagnose(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """启动简历诊断

    Args:
        session_id: 会话 ID
        db: 数据库会话

    Returns:
        诊断任务 ID
    """
    # TODO: 检查简历解析状态，启动诊断流程
    return {
        "session_id": session_id,
        "diagnose_id": "placeholder-diagnose-id",
        "status": "started",
        "message": "诊断已启动...",
    }


@router.get("/diagnose/{session_id}/result")
async def get_diagnose_result(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> DiagnoseResult:
    """获取诊断结果

    Args:
        session_id: 会话 ID
        db: 数据库会话

    Returns:
        诊断结果
    """
    # TODO: 从数据库获取诊断结果
    return DiagnoseResult(
        session_id=session_id,
        score=75,
        strengths=["技术栈完整", "项目经验丰富"],
        weaknesses=["缺少量化指标", "排版可优化"],
        suggestions=["添加项目成果数据", "优化简历格式"],
    )
