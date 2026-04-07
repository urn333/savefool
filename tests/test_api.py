"""API测试.

测试Web API层功能。
"""

import pytest
from fastapi.testclient import TestClient

from src.presentation.api.main import create_app


@pytest.fixture
def client():
    """创建测试客户端."""
    app = create_app()
    return TestClient(app)


class TestHealthCheck:
    """健康检查测试."""
    
    def test_health_check(self, client):
        """测试健康检查端点."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["code"] == 0
        assert data["message"] == "success"
        assert "data" in data
        assert data["data"]["status"] == "healthy"


class TestHomeworkAPI:
    """作业API测试."""
    
    def test_upload_homework_validation(self, client):
        """测试作业上传验证."""
        # 缺少必需参数 - 返回400或422都可以
        response = client.post("/api/v1/homework")
        assert response.status_code in [400, 422]
    
    def test_get_homework_not_found(self, client):
        """测试获取不存在的作业."""
        response = client.get("/api/v1/homework/hw_nonexistent")
        assert response.status_code == 404
        
        data = response.json()
        assert data["code"] == 130001


class TestDiagnosisAPI:
    """诊断API测试."""
    
    def test_get_diagnosis_options(self, client):
        """测试获取诊断选项."""
        response = client.get("/api/v1/diagnosis/q_test/options")
        assert response.status_code == 200
        
        data = response.json()
        assert data["code"] == 0
        assert "options" in data["data"]
    
    def test_get_diagnosis_not_found(self, client):
        """测试获取不存在的诊断."""
        response = client.get("/api/v1/diagnosis/dia_nonexistent")
        assert response.status_code == 404


class TestVariantAPI:
    """变形题API测试."""
    
    def test_generate_variants(self, client):
        """测试生成变形题."""
        response = client.post(
            "/api/v1/variant",
            json={
                "question_id": "q_test",
                "difficulty": "same",
                "count": 3,
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["code"] == 0
        assert "variant_set_id" in data["data"]
        assert "variants" in data["data"]


class TestStatisticsAPI:
    """统计API测试."""
    
    def test_get_knowledge_graph(self, client):
        """测试获取知识图谱."""
        response = client.get(
            "/api/v1/statistics/knowledge-graph?student_id=stu_test&subject=math"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["code"] == 0
        assert "graph" in data["data"]
    
    def test_get_weak_points(self, client):
        """测试获取薄弱点."""
        response = client.get(
            "/api/v1/statistics/weak-points?student_id=stu_test&limit=5"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["code"] == 0
        assert "weaknesses" in data["data"]
    
    def test_get_trends(self, client):
        """测试获取趋势."""
        response = client.get(
            "/api/v1/statistics/trends?student_id=stu_test&metric=accuracy&period=month"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["code"] == 0
        assert "trend" in data["data"]


class TestWebPages:
    """Web页面测试."""
    
    def test_root_page(self, client):
        """测试根路径."""
        response = client.get("/")
        assert response.status_code == 200
        assert "AI助教系统" in response.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
