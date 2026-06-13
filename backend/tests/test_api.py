"""API 路由测试

测试 FastAPI 端点。
"""

class TestHealthCheck:
    """健康检查测试"""

    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestSessionsAPI:
    """会话 API 测试"""

    def test_create_session_placeholder(self, client):
        """测试创建会话（占位）"""
        # 创建一个假的文件上传
        files = {"file": ("test.pdf", b"fake content", "application/pdf")}
        response = client.post("/api/sessions", files=files)
        # 由于是占位实现，应该返回 200
        assert response.status_code == 200

    def test_get_session_status_placeholder(self, client):
        """测试获取会话状态（占位）"""
        response = client.get("/api/sessions/test-id/status")
        assert response.status_code == 200


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
