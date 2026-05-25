"""测试配置

提供测试夹具和配置。
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch


@pytest.fixture
def client():
    """创建测试客户端

    Mock 掉数据库和 Redis 连接。
    """
    with patch("app.core.database.init_db", new_callable=AsyncMock):
        with patch("app.core.database.close_db", new_callable=AsyncMock):
            with patch("app.core.redis.init_redis", new_callable=AsyncMock):
                with patch("app.core.redis.close_redis", new_callable=AsyncMock):
                    from app.main import app
                    with TestClient(app) as c:
                        yield c
