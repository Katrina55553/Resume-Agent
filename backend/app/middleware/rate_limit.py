"""限流和 Token 配额中间件

控制请求频率和 Token 使用量。
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Dict
import time

from app.core.config import settings
from app.core.redis import get_redis


class RateLimitMiddleware(BaseHTTPMiddleware):
    """限流中间件

    基于 Redis 的滑动窗口限流。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """处理请求

        Args:
            request: 请求对象
            call_next: 下一个中间件

        Returns:
            响应对象
        """
        # 获取用户标识（IP 或用户 ID）
        user_id = request.headers.get("X-User-ID", request.client.host if request.client else "unknown")

        # 检查限流
        is_limited = await self._check_rate_limit(user_id)
        if is_limited:
            raise HTTPException(
                status_code=429,
                detail="请求过于频繁，请稍后再试",
            )

        # 继续处理请求
        response = await call_next(request)
        return response

    async def _check_rate_limit(self, user_id: str) -> bool:
        """检查是否触发限流

        Args:
            user_id: 用户标识

        Returns:
            是否被限流
        """
        try:
            redis = get_redis()
            key = f"rate_limit:{user_id}"

            # 滑动窗口计数
            now = int(time.time())
            window = 60  # 1 分钟窗口

            # 使用 Redis 事务
            pipe = redis.pipeline()
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window)
            results = await pipe.execute()

            count = results[2]
            return count > settings.RATE_LIMIT_PER_MINUTE

        except Exception:
            # Redis 不可用时不限流
            return False


class TokenQuotaMiddleware(BaseHTTPMiddleware):
    """Token 配额中间件

    控制用户 Token 使用量。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """处理请求

        Args:
            request: 请求对象
            call_next: 下一个中间件

        Returns:
            响应对象
        """
        # 只对 API 请求检查配额
        if request.url.path.startswith("/api/"):
            user_id = request.headers.get("X-User-ID")
            if user_id:
                has_quota = await self._check_token_quota(user_id)
                if not has_quota:
                    raise HTTPException(
                        status_code=402,
                        detail="Token 配额已用完",
                    )

        response = await call_next(request)
        return response

    async def _check_token_quota(self, user_id: str) -> bool:
        """检查 Token 配额

        Args:
            user_id: 用户 ID

        Returns:
            是否有剩余配额
        """
        try:
            redis = get_redis()
            key = f"token_quota:{user_id}"

            # 获取已用 Token 数
            used = await redis.get(key)
            used = int(used) if used else 0

            return used < settings.TOKEN_QUOTA_PER_USER

        except Exception:
            # Redis 不可用时不限制
            return True
