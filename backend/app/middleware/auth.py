"""用户身份提取中间件

从请求中提取和验证用户身份。
"""

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from app.core.config import settings

# HTTP Bearer 认证方案
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """获取当前用户

    从 JWT Token 或请求头中提取用户身份。

    Args:
        credentials: HTTP Bearer 认证信息

    Returns:
        用户 ID 或 None
    """
    if credentials is None:
        return None

    # TODO: 实现 JWT Token 验证
    # 1. 解析 Token
    # 2. 验证签名
    # 3. 提取用户 ID
    return "placeholder-user-id"


async def require_user(
    user: Optional[str] = Depends(get_current_user),
) -> str:
    """要求用户登录

    Args:
        user: 用户 ID

    Returns:
        用户 ID

    Raises:
        HTTPException: 未登录时抛出 401
    """
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="请先登录",
        )
    return user
