"""WebSocket 消息缓存模块

使用 Redis List 缓存面试消息，支持断线重连后补推。
消息格式：JSON 序列化的 {type, data, timestamp}
"""

import json
import logging
import time
from typing import Any

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

# Redis key 前缀
MSG_CACHE_PREFIX = "ws:msgs:"
MSG_CACHE_TTL = 3600  # 消息缓存 1 小时过期


def _cache_key(session_id: str) -> str:
    """生成 Redis key"""
    return f"{MSG_CACHE_PREFIX}{session_id}"


async def push_message(session_id: str, msg_type: str, data: dict) -> None:
    """将一条消息推入缓存队列

    Args:
        session_id: 面试会话 ID
        msg_type: 消息类型 (question/status/complete/error)
        data: 消息数据
    """
    try:
        client = get_redis()
        entry = json.dumps({
            "type": msg_type,
            "data": data,
            "timestamp": time.time(),
        }, ensure_ascii=False)
        key = _cache_key(session_id)
        await client.rpush(key, entry)
        await client.expire(key, MSG_CACHE_TTL)
    except Exception as e:
        logger.error(f"消息缓存写入失败: {e}")


async def get_pending_messages(session_id: str) -> list[dict[str, Any]]:
    """获取并清空所有待消费消息

    原子操作：读取 + 删除，防止重复消费。

    Returns:
        消息列表 [{"type": ..., "data": ..., "timestamp": ...}, ...]
    """
    try:
        client = get_redis()
        key = _cache_key(session_id)

        # 用 Lua 脚本原子执行 LRANGE + DEL
        script = """
        local msgs = redis.call('LRANGE', KEYS[1], 0, -1)
        if #msgs > 0 then
            redis.call('DEL', KEYS[1])
        end
        return msgs
        """
        raw_msgs = await client.eval(script, 1, key)

        messages = []
        for raw in raw_msgs:
            try:
                messages.append(json.loads(raw))
            except json.JSONDecodeError:
                continue

        if messages:
            logger.info(f"会话 {session_id} 补推 {len(messages)} 条缓存消息")

        return messages
    except Exception as e:
        logger.error(f"消息缓存读取失败: {e}")
        return []


async def clear_messages(session_id: str) -> None:
    """清空会话的缓存消息"""
    try:
        client = get_redis()
        await client.delete(_cache_key(session_id))
    except Exception as e:
        logger.error(f"消息缓存清理失败: {e}")
