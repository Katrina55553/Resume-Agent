"""WebSocket 消息缓存模块测试

覆盖 push_message / get_pending_messages / clear_messages，使用 AsyncMock 模拟 Redis。
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core import msg_cache


def _make_fake_redis():
    """构造一个 MagicMock Redis 客户端，所有方法都是 AsyncMock"""
    client = MagicMock()
    client.rpush = AsyncMock()
    client.expire = AsyncMock()
    client.eval = AsyncMock(return_value=[])
    client.delete = AsyncMock()
    return client


# ============================================================
# _cache_key
# ============================================================


class TestCacheKey:
    """Redis key 生成"""

    def test_key_format(self):
        key = msg_cache._cache_key("session-123")
        assert key == "ws:msgs:session-123"

    def test_prefix_constant(self):
        assert msg_cache.MSG_CACHE_PREFIX == "ws:msgs:"

    def test_ttl_is_one_hour(self):
        assert msg_cache.MSG_CACHE_TTL == 3600


# ============================================================
# push_message
# ============================================================


class TestPushMessage:
    """消息推入缓存"""

    @pytest.mark.asyncio
    async def test_pushes_json_to_redis_list(self):
        fake_redis = _make_fake_redis()
        with patch.object(msg_cache, "get_redis", return_value=fake_redis):
            await msg_cache.push_message(
                "sess-1", "question", {"content": "hello"},
            )

        fake_redis.rpush.assert_awaited_once()
        args = fake_redis.rpush.call_args.args
        assert args[0] == "ws:msgs:sess-1"

        # 验证序列化内容
        entry = json.loads(args[1])
        assert entry["type"] == "question"
        assert entry["data"] == {"content": "hello"}
        assert "timestamp" in entry

    @pytest.mark.asyncio
    async def test_sets_ttl_on_push(self):
        fake_redis = _make_fake_redis()
        with patch.object(msg_cache, "get_redis", return_value=fake_redis):
            await msg_cache.push_message("sess-1", "status", {"phase": "thinking"})

        fake_redis.expire.assert_awaited_once_with("ws:msgs:sess-1", 3600)

    @pytest.mark.asyncio
    async def test_swallows_exception(self):
        """Redis 异常不应抛出"""
        fake_redis = _make_fake_redis()
        fake_redis.rpush = AsyncMock(side_effect=RuntimeError("redis down"))
        with patch.object(msg_cache, "get_redis", return_value=fake_redis):
            # 不应抛异常
            await msg_cache.push_message("sess-1", "question", {})

    @pytest.mark.asyncio
    async def test_serializes_with_ensure_ascii_false(self):
        """中文消息应保留 UTF-8 字符"""
        fake_redis = _make_fake_redis()
        with patch.object(msg_cache, "get_redis", return_value=fake_redis):
            await msg_cache.push_message("sess-1", "question", {"content": "你好世界"})

        raw = fake_redis.rpush.call_args.args[1]
        assert "你好世界" in raw  # ensure_ascii=False 时中文字符原样保留


# ============================================================
# get_pending_messages
# ============================================================


class TestGetPendingMessages:
    """获取并清空待消费消息"""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_messages(self):
        fake_redis = _make_fake_redis()
        fake_redis.eval = AsyncMock(return_value=[])
        with patch.object(msg_cache, "get_redis", return_value=fake_redis):
            result = await msg_cache.get_pending_messages("sess-1")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_and_clears_messages(self):
        """读取消息后应清空（Lua 脚本 LRANGE + DEL）"""
        raw_msgs = [
            json.dumps({"type": "question", "data": {"content": "Q1"}, "timestamp": 1.0}),
            json.dumps({"type": "status", "data": {"phase": "thinking"}, "timestamp": 2.0}),
        ]
        fake_redis = _make_fake_redis()
        fake_redis.eval = AsyncMock(return_value=raw_msgs)

        with patch.object(msg_cache, "get_redis", return_value=fake_redis):
            result = await msg_cache.get_pending_messages("sess-1")

        assert len(result) == 2
        assert result[0]["type"] == "question"
        assert result[1]["type"] == "status"

        # 验证 Lua 脚本被调用，key 正确
        fake_redis.eval.assert_awaited_once()
        script_arg = fake_redis.eval.call_args.args[0]
        key_arg = fake_redis.eval.call_args.args[2]
        assert "LRANGE" in script_arg
        assert "DEL" in script_arg
        assert key_arg == "ws:msgs:sess-1"

    @pytest.mark.asyncio
    async def test_skips_invalid_json_entries(self):
        """损坏的 JSON 应被跳过，不抛异常"""
        raw_msgs = [
            "not a json",
            json.dumps({"type": "question", "data": {}, "timestamp": 1.0}),
        ]
        fake_redis = _make_fake_redis()
        fake_redis.eval = AsyncMock(return_value=raw_msgs)

        with patch.object(msg_cache, "get_redis", return_value=fake_redis):
            result = await msg_cache.get_pending_messages("sess-1")

        assert len(result) == 1
        assert result[0]["type"] == "question"

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self):
        """Redis 异常时返回空列表"""
        fake_redis = _make_fake_redis()
        fake_redis.eval = AsyncMock(side_effect=RuntimeError("redis down"))
        with patch.object(msg_cache, "get_redis", return_value=fake_redis):
            result = await msg_cache.get_pending_messages("sess-1")
        assert result == []


# ============================================================
# clear_messages
# ============================================================


class TestClearMessages:
    """清空缓存消息"""

    @pytest.mark.asyncio
    async def test_deletes_cache_key(self):
        fake_redis = _make_fake_redis()
        with patch.object(msg_cache, "get_redis", return_value=fake_redis):
            await msg_cache.clear_messages("sess-1")
        fake_redis.delete.assert_awaited_once_with("ws:msgs:sess-1")

    @pytest.mark.asyncio
    async def test_swallows_exception(self):
        fake_redis = _make_fake_redis()
        fake_redis.delete = AsyncMock(side_effect=RuntimeError("redis down"))
        with patch.object(msg_cache, "get_redis", return_value=fake_redis):
            # 不应抛异常
            await msg_cache.clear_messages("sess-1")
