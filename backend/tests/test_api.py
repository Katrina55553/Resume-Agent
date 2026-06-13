"""API 路由测试

测试 FastAPI 端点。
"""

import pytest


class TestHealthCheck:
    """健康检查测试"""

    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


@pytest.mark.skip(reason="需要数据库连接，跳过集成测试")
class TestSessionsAPI:
    """会话 API 测试"""

    def test_create_session_placeholder(self, client):
        """测试创建会话（占位）"""
        files = {"file": ("test.pdf", b"fake content", "application/pdf")}
        response = client.post("/api/sessions", files=files)
        assert response.status_code == 200

    def test_get_session_status_placeholder(self, client):
        """测试获取会话状态（占位）"""
        response = client.get("/api/sessions/test-id/status")
        assert response.status_code == 200


@pytest.mark.skip(reason="需要数据库连接，跳过集成测试")
class TestDiagnoseAPI:
    """诊断 API 测试"""

    def test_start_diagnose_placeholder(self, client):
        """测试启动诊断（占位）"""
        response = client.post("/api/diagnose/test-id")
        assert response.status_code == 200

    def test_get_diagnose_result_placeholder(self, client):
        """测试获取诊断结果（占位）"""
        response = client.get("/api/diagnose/test-id/result")
        assert response.status_code == 200
        data = response.json()
        assert "score" in data
