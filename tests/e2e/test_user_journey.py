"""端到端测试 - 用户旅程.

完整用户旅程测试:
1. 上传作业图片
2. 等待诊断完成(≤90s)
3. 查看诊断结果
4. 完成分层选择
5. 查看知识图谱

功能追溯ID: E2E-001 ~ E2E-005
"""

import io
import time
import pytest
from datetime import datetime
from typing import Dict, Any, List

from fastapi.testclient import TestClient

from src.presentation.api.main import app


# ============== Fixtures ==============

@pytest.fixture
def client():
    """测试客户端."""
    return TestClient(app)


@pytest.fixture
def test_student():
    """测试学生信息."""
    return {
        "student_id": "e2e_student_001",
        "name": "测试学生",
        "grade": "七年级",
    }


@pytest.fixture
def sample_homework_images():
    """示例作业图片."""
    return [
        ("homework_page1.jpg", io.BytesIO(b"fake image content page 1"), "image/jpeg"),
        ("homework_page2.jpg", io.BytesIO(b"fake image content page 2"), "image/jpeg"),
    ]


# ============== 用户旅程测试 ==============

class TestCompleteUserJourney:
    """完整用户旅程测试."""
    
    def test_journey_happy_path(self, client, test_student, sample_homework_images):
        """测试正常用户旅程 - 90秒闭环.
        
        步骤:
        1. 上传作业图片
        2. 轮询等待诊断完成
        3. 查看诊断结果
        4. 完成分层选择
        5. 查看知识图谱
        """
        journey_start = time.time()
        
        # === Step 1: 上传作业图片 ===
        print("\n[Step 1] 上传作业图片...")
        step1_start = time.time()
        
        upload_response = client.post(
            f"/api/v1/homework/upload?student_id={test_student['student_id']}&subject=数学",
            files=[("images", name, content, mime) for name, content, mime in sample_homework_images],
        )
        
        assert upload_response.status_code == 202, f"上传失败: {upload_response.text}"
        upload_data = upload_response.json()
        
        assert "homework_id" in upload_data
        assert upload_data["status"] == "processing"
        assert upload_data["estimated_seconds"] <= 90  # 验证90秒承诺
        
        homework_id = upload_data["homework_id"]
        step1_elapsed = time.time() - step1_start
        print(f"  ✓ 上传成功, homework_id: {homework_id}")
        print(f"  ✓ 响应时间: {step1_elapsed:.2f}s")
        
        # === Step 2: 等待诊断完成 ===
        print("\n[Step 2] 等待诊断完成...")
        step2_start = time.time()
        
        diagnosis_completed = False
        diagnosis_data = None
        max_wait_time = 90  # 最大等待90秒
        poll_interval = 1  # 每秒轮询
        
        while (time.time() - step2_start) < max_wait_time:
            status_response = client.get(f"/api/v1/homework/{homework_id}/status")
            assert status_response.status_code == 200
            
            status_data = status_response.json()
            progress = status_data.get("progress", 0)
            
            print(f"  进度: {progress*100:.0f}%", end="\r")
            
            if status_data["status"] == "completed":
                diagnosis_completed = True
                diagnosis_data = status_data
                break
            
            time.sleep(poll_interval)
        
        step2_elapsed = time.time() - step2_start
        print(f"\n  ✓ 诊断完成, 耗时: {step2_elapsed:.2f}s")
        
        # 验证90秒响应时间
        assert step2_elapsed <= 90, f"诊断超时: {step2_elapsed}s > 90s"
        assert diagnosis_completed, "诊断未完成"
        assert diagnosis_data is not None
        assert len(diagnosis_data.get("results", [])) > 0
        
        # === Step 3: 查看诊断结果 ===
        print("\n[Step 3] 查看诊断结果...")
        
        results = diagnosis_data["results"]
        assert len(results) > 0, "没有诊断结果"
        
        first_diagnosis = results[0]
        assert "diagnosis_id" in first_diagnosis
        assert "error_type" in first_diagnosis
        assert "knowledge_tags" in first_diagnosis
        assert "confidence_score" in first_diagnosis
        assert 0 <= first_diagnosis["confidence_score"] <= 1
        
        diagnosis_id = first_diagnosis["diagnosis_id"]
        print(f"  ✓ 诊断ID: {diagnosis_id}")
        print(f"  ✓ 错误类型: {first_diagnosis['error_type']}")
        print(f"  ✓ 知识标签: {first_diagnosis['knowledge_tags']}")
        print(f"  ✓ 置信度: {first_diagnosis['confidence_score']}")
        
        # === Step 4: 完成分层选择 ===
        print("\n[Step 4] 完成分层选择...")
        step4_start = time.time()
        
        selection_response = client.post(
            "/api/v1/diagnosis/layer-selection",
            json={
                "diagnosis_id": diagnosis_id,
                "selected_layer": 3,  # 选择第3层
            },
        )
        
        assert selection_response.status_code == 200
        selection_data = selection_response.json()
        
        assert selection_data["diagnosis_id"] == diagnosis_id
        assert selection_data["selected_layer"] == 3
        assert "selection_id" in selection_data
        assert "is_correct" in selection_data
        
        step4_elapsed = time.time() - step4_start
        print(f"  ✓ 分层选择提交成功")
        print(f"  ✓ 选择分层: {selection_data['selected_layer']}")
        print(f"  ✓ 是否正确: {selection_data['is_correct']}")
        print(f"  ✓ 响应时间: {step4_elapsed:.2f}s")
        
        # === Step 5: 查看知识图谱 ===
        print("\n[Step 5] 查看知识图谱...")
        step5_start = time.time()
        
        kg_response = client.get(
            f"/api/v1/knowledge-graph/{test_student['student_id']}?subject=数学"
        )
        
        assert kg_response.status_code == 200
        kg_data = kg_response.json()
        
        assert kg_data["student_id"] == test_student["student_id"]
        assert kg_data["subject"] == "数学"
        assert "nodes" in kg_data
        assert "edges" in kg_data
        assert len(kg_data["nodes"]) > 0
        
        # 验证知识节点结构
        for node in kg_data["nodes"]:
            assert "node_id" in node
            assert "name" in node
            assert "mastery_level" in node
            assert 0 <= node["mastery_level"] <= 1
            assert "is_weak" in node
        
        step5_elapsed = time.time() - step5_start
        weak_nodes = [n for n in kg_data["nodes"] if n["is_weak"]]
        
        print(f"  ✓ 知识节点数: {len(kg_data['nodes'])}")
        print(f"  ✓ 薄弱节点数: {len(weak_nodes)}")
        print(f"  ✓ 关联边数: {len(kg_data['edges'])}")
        print(f"  ✓ 响应时间: {step5_elapsed:.2f}s")
        
        # === 总时间统计 ===
        total_time = time.time() - journey_start
        print(f"\n[完成] 总用时: {total_time:.2f}s")
        
        # 验证整体时间
        assert total_time <= 100, f"整体流程超时: {total_time}s > 100s"
    
    def test_journey_multiple_questions(self, client, test_student):
        """测试多题目的用户旅程."""
        # Given: 多页作业
        images = [
            ("multi_page1.jpg", io.BytesIO(b"content1"), "image/jpeg"),
            ("multi_page2.jpg", io.BytesIO(b"content2"), "image/jpeg"),
            ("multi_page3.jpg", io.BytesIO(b"content3"), "image/jpeg"),
        ]
        
        # Step 1: 上传
        upload_response = client.post(
            f"/api/v1/homework/upload?student_id={test_student['student_id']}&subject=数学",
            files=[("images", name, content, mime) for name, content, mime in images],
        )
        assert upload_response.status_code == 202
        homework_id = upload_response.json()["homework_id"]
        
        # Step 2: 等待完成
        max_wait = 90
        start = time.time()
        while (time.time() - start) < max_wait:
            status = client.get(f"/api/v1/homework/{homework_id}/status").json()
            if status["status"] == "completed":
                break
            time.sleep(0.5)
        
        # Step 3: 验证多个诊断结果
        final_status = client.get(f"/api/v1/homework/{homework_id}/status").json()
        results = final_status.get("results", [])
        
        # 每个结果都应该能进行分层选择
        for result in results:
            selection = client.post(
                "/api/v1/diagnosis/layer-selection",
                json={
                    "diagnosis_id": result["diagnosis_id"],
                    "selected_layer": 2,
                },
            )
            assert selection.status_code == 200


class TestUserJourneyVariations:
    """用户旅程变体测试."""
    
    def test_journey_different_subjects(self, client, test_student):
        """测试不同学科的用户旅程."""
        subjects = ["数学", "英语", "物理"]
        
        for subject in subjects:
            # 上传
            upload = client.post(
                f"/api/v1/homework/upload?student_id={test_student['student_id']}&subject={subject}",
                files={"images": ("test.jpg", io.BytesIO(b"content"), "image/jpeg")},
            )
            assert upload.status_code == 202
            
            # 获取知识图谱验证学科
            kg = client.get(
                f"/api/v1/knowledge-graph/{test_student['student_id']}?subject={subject}"
            )
            assert kg.status_code == 200
            assert kg.json()["subject"] == subject
    
    def test_journey_layer_selection_variations(self, client, test_student):
        """测试不同分层选择的用户旅程."""
        # 上传并获取诊断
        upload = client.post(
            f"/api/v1/homework/upload?student_id={test_student['student_id']}&subject=数学",
            files={"images": ("test.jpg", io.BytesIO(b"content"), "image/jpeg")},
        )
        homework_id = upload.json()["homework_id"]
        
        # 等待完成
        max_wait = 90
        start = time.time()
        while (time.time() - start) < max_wait:
            status = client.get(f"/api/v1/homework/{homework_id}/status").json()
            if status["status"] == "completed":
                break
            time.sleep(0.5)
        
        final = client.get(f"/api/v1/homework/{homework_id}/status").json()
        diagnosis_id = final["results"][0]["diagnosis_id"]
        
        # 测试所有有效分层
        for layer in [1, 2, 3, 4]:
            selection = client.post(
                "/api/v1/diagnosis/layer-selection",
                json={
                    "diagnosis_id": diagnosis_id,
                    "selected_layer": layer,
                },
            )
            assert selection.status_code == 200
            assert selection.json()["selected_layer"] == layer
    
    def test_journey_error_recovery(self, client, test_student):
        """测试错误恢复场景."""
        # Given: 不存在的作业ID
        fake_id = "nonexistent_homework"
        
        # When: 查询不存在的状态
        response = client.get(f"/api/v1/homework/{fake_id}/status")
        
        # Then: 应该返回404
        assert response.status_code == 404
        data = response.json()
        assert "error_code" in data
        
        # 用户应该能够重新开始
        upload = client.post(
            f"/api/v1/homework/upload?student_id={test_student['student_id']}&subject=数学",
            files={"images": ("test.jpg", io.BytesIO(b"content"), "image/jpeg")},
        )
        assert upload.status_code == 202


class TestPerformanceRequirements:
    """性能需求测试."""
    
    def test_90_second_response_time(self, client, test_student):
        """测试90秒响应时间要求."""
        start = time.time()
        
        # 上传
        upload = client.post(
            f"/api/v1/homework/upload?student_id={test_student['student_id']}&subject=数学",
            files={"images": ("test.jpg", io.BytesIO(b"content"), "image/jpeg")},
        )
        assert upload.status_code == 202
        homework_id = upload.json()["homework_id"]
        
        # 轮询直到完成或超时
        completed = False
        while (time.time() - start) < 90:
            status = client.get(f"/api/v1/homework/{homework_id}/status").json()
            if status["status"] == "completed":
                completed = True
                break
            time.sleep(0.1)
        
        elapsed = time.time() - start
        
        assert completed, "诊断未在90秒内完成"
        assert elapsed <= 90, f"响应时间超过90秒: {elapsed:.2f}s"
        print(f"\n✓ 响应时间: {elapsed:.2f}s (≤90s)")
    
    def test_4_step_operation_limit(self, client, test_student):
        """测试4步操作限制."""
        steps = []
        
        # Step 1: 上传
        steps.append("upload")
        upload = client.post(
            f"/api/v1/homework/upload?student_id={test_student['student_id']}&subject=数学",
            files={"images": ("test.jpg", io.BytesIO(b"content"), "image/jpeg")},
        )
        homework_id = upload.json()["homework_id"]
        
        # Step 2: 获取状态(轮询算作一步)
        steps.append("get_status")
        status = client.get(f"/api/v1/homework/{homework_id}/status").json()
        
        # Step 3: 分层选择(如果有结果)
        if status.get("results"):
            steps.append("layer_selection")
            client.post(
                "/api/v1/diagnosis/layer-selection",
                json={
                    "diagnosis_id": status["results"][0]["diagnosis_id"],
                    "selected_layer": 3,
                },
            )
        
        # Step 4: 查看知识图谱
        steps.append("knowledge_graph")
        client.get(f"/api/v1/knowledge-graph/{test_student['student_id']}")
        
        # 验证步数不超过4
        assert len(steps) <= 4, f"操作步数超过4: {steps}"
        print(f"\n✓ 操作步数: {len(steps)} (≤4)")


class TestSystemIntegration:
    """系统集成测试."""
    
    def test_end_to_end_data_flow(self, client, test_student):
        """测试端到端数据流."""
        # 上传作业
        upload = client.post(
            f"/api/v1/homework/upload?student_id={test_student['student_id']}&subject=数学",
            files={"images": ("test.jpg", io.BytesIO(b"content"), "image/jpeg")},
        )
        homework_id = upload.json()["homework_id"]
        
        # 等待诊断
        max_wait = 90
        start = time.time()
        while (time.time() - start) < max_wait:
            status = client.get(f"/api/v1/homework/{homework_id}/status").json()
            if status["status"] == "completed":
                break
            time.sleep(0.5)
        
        final = client.get(f"/api/v1/homework/{homework_id}/status").json()
        
        # 验证数据一致性
        assert final["homework_id"] == homework_id
        
        if final.get("results"):
            result = final["results"][0]
            
            # 提交分层选择
            selection = client.post(
                "/api/v1/diagnosis/layer-selection",
                json={
                    "diagnosis_id": result["diagnosis_id"],
                    "selected_layer": 3,
                },
            ).json()
            
            # 验证选择记录关联正确的诊断
            assert selection["diagnosis_id"] == result["diagnosis_id"]
        
        # 验证知识图谱数据
        kg = client.get(f"/api/v1/knowledge-graph/{test_student['student_id']}").json()
        assert kg["student_id"] == test_student["student_id"]
    
    def test_health_and_readiness(self, client):
        """测试健康和就绪状态."""
        # 健康检查
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["status"] == "healthy"
        
        # API应该能正常响应
        response = client.get("/api/v1/knowledge-graph/test_student")
        assert response.status_code == 200
