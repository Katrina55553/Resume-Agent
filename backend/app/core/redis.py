"""Redis 连接模块

提供 Redis 连接池和便捷方法。
"""

import redis.asyncio as redis
from typing import Optional

from app.core.config import settings


# Redis 连接池
redis_pool: Optional[redis.ConnectionPool] = None
redis_client: Optional[redis.Redis] = None


async def init_redis() -> None:
    """初始化 Redis 连接池"""
    global redis_pool, redis_client

    redis_pool = redis.ConnectionPool.from_url(
        settings.REDIS_URL,
        max_connections=20,
        decode_responses=True,
    )
    redis_client = redis.Redis(connection_pool=redis_pool)

    # 测试连接
    await redis_client.ping()


async def close_redis() -> None:
    """关闭 Redis 连接"""
    global redis_client, redis_pool

    if redis_client:
        await redis_client.close()
        redis_client = None

    if redis_pool:
        await redis_pool.disconnect()
        redis_pool = None


def get_redis() -> redis.Redis:
    """获取 Redis 客户端（依赖注入用）"""
    if redis_client is None:
        raise RuntimeError("Redis 未初始化，请先调用 init_redis()")
    return redis_client


async def cache_get(key: str) -> Optional[str]:
    """从缓存获取值"""
    client = get_redis()
    return await client.get(key)


async def cache_set(key: str, value: str, expire: int = 3600) -> None:
    """设置缓存值"""
    client = get_redis()
    await client.setex(key, expire, value)


async def cache_delete(key: str) -> None:
    """删除缓存"""
    client = get_redis()
    await client.delete(key)
