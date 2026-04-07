"""性能测试.

测试范围:
- 90秒响应时间验证
- 并发用户测试
- 数据库查询性能

功能追溯ID: PERF-001 ~ PERF-003
"""

import asyncio
import time
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Any
import statistics

from fastapi.testclient import TestClient

from src.presentation.api.main import app


# ============== Fixtures ==============

@pytest.fixture
def client():
    """测试客户端."""
    return TestClient(app)


@pytest.fixture
def performance_stats():
    """性能统计收集器."""
    return {
        "response_times": [],
        "errors": [],
        "start_time": None,
        "end_time": None,
    }


# ============== 90秒响应时间测试 ==============

class TestNinetySecondResponseTime:
    """90秒响应时间测试."""
    
    def test_diagnosis_completes_within_90_seconds(self, client):
        """测试诊断在90秒内完成."""
        import io
        
        # Given: 一份作业
        student_id = "perf_student_001"
        
        # When: 上传并开始计时
        start_time = time.time()
        
        upload = client.post(
            f"/api/v1/homework/upload?student_id={student_id}&subject=数学",
            files={"images": ("test.jpg", io.BytesIO(b"content"), "image/jpeg")},
        )
        assert upload.status_code == 202
        homework_id = upload.json()["homework_id"]
        
        # 轮询直到完成
        completed = False
        max_wait = 90
        
        while (time.time() - start_time) < max_wait:
            status = client.get(f"/api/v1/homework/{homework_id}/status").json()
            if status["status"] == "completed":
                completed = True
                break
            time.sleep(0.1)
        
        elapsed = time.time() - start_time
        
        # Then: 应该在90秒内完成
        assert completed, f"诊断未在90秒内完成"
        assert elapsed <= 90, f"响应时间 {elapsed:.2f}s 超过90秒限制"
        
        print(f"\n✓ 诊断完成时间: {elapsed:.2f}s (≤90s)")
    
    def test_api_endpoint_response_times(self, client):
        """测试各端点响应时间."""
        import io
        
        endpoints = [
            ("GET", "/api/v1/health", None),
            ("GET", "/api/v1/knowledge-graph/perf_student", None),
        ]
        
        results = []
        
        for method, url, data in endpoints:
            times = []
            
            # 测试10次取平均
            for _ in range(10):
                start = time.time()
                if method == "GET":
                    response = client.get(url)
                else:
                    response = client.post(url, json=data)
                elapsed = time.time() - start
                
                assert response.status_code == 200
                times.append(elapsed)
            
            avg_time = statistics.mean(times)
            max_time = max(times)
            
            results.append({
                "endpoint": f"{method} {url}",
                "avg_time": avg_time,
                "max_time": max_time,
            })
            
            # 验证平均响应时间小于100ms
            assert avg_time < 0.1, f"{url} 平均响应时间 {avg_time*1000:.0f}ms > 100ms"
        
        # 打印结果
        print("\n端点响应时间:")
        for r in results:
            print(f"  {r['endpoint']}: avg={r['avg_time']*1000:.1f}ms, max={r['max_time']*1000:.1f}ms")


# ============== 并发用户测试 ==============

class TestConcurrentUsers:
    """并发用户测试."""
    
    def test_10_concurrent_uploads(self, client):
        """测试10个并发上传."""
        import io
        
        def upload_task(i):
            start = time.time()
            try:
                response = client.post(
                    f"/api/v1/homework/upload?student_id=concurrent_user_{i}&subject=数学",
                    files={"images": ("test.jpg", io.BytesIO(b"content"), "image/jpeg")},
                )
                elapsed = time.time() - start
                return {
                    "success": response.status_code == 202,
                    "status": response.status_code,
                    "time": elapsed,
                    "user": i,
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "time": time.time() - start,
                    "user": i,
                }
        
        # 执行10个并发请求
        start = time.time()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(upload_task, i) for i in range(10)]
            results = [f.result() for f in as_completed(futures)]
        
        total_time = time.time() - start
        
        # 验证所有请求成功
        success_count = sum(1 for r in results if r["success"])
        assert success_count == 10, f"只有 {success_count}/10 个请求成功"
        
        # 验证总时间合理
        assert total_time < 10, f"并发处理时间 {total_time:.2f}s 过长"
        
        # 打印统计
        times = [r["time"] for r in results]
        print(f"\n10并发上传统计:")
        print(f"  成功率: {success_count}/10")
        print(f"  总时间: {total_time:.2f}s")
        print(f"  平均响应: {statistics.mean(times):.2f}s")
        print(f"  最大响应: {max(times):.2f}s")
    
    def test_50_concurrent_health_checks(self, client):
        """测试50个并发健康检查."""
        def check_health(i):
            start = time.time()
            try:
                response = client.get("/api/v1/health")
                elapsed = time.time() - start
                return {
                    "success": response.status_code == 200,
                    "time": elapsed,
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "time": time.time() - start,
                }
        
        # 执行50个并发请求
        start = time.time()
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(check_health, i) for i in range(50)]
            results = [f.result() for f in as_completed(futures)]
        
        total_time = time.time() - start
        
        # 验证
        success_count = sum(1 for r in results if r["success"])
        assert success_count == 50, f"只有 {success_count}/50 个请求成功"
        assert total_time < 5, f"50并发处理时间 {total_time:.2f}s 过长"
        
        times = [r["time"] for r in results]
        print(f"\n50并发健康检查:")
        print(f"  成功率: {success_count}/50")
        print(f"  总时间: {total_time:.2f}s")
        print(f"  平均响应: {statistics.mean(times)*1000:.1f}ms")
        print(f"  最大响应: {max(times)*1000:.1f}ms")
    
    @pytest.mark.asyncio
    async def test_100_concurrent_requests(self, client):
        """测试100个异步并发请求."""
        async def make_request(i):
            loop = asyncio.get_event_loop()
            start = time.time()
            try:
                response = await loop.run_in_executor(
                    None, client.get, "/api/v1/health"
                )
                elapsed = time.time() - start
                return {
                    "success": response.status_code == 200,
                    "time": elapsed,
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "time": time.time() - start,
                }
        
        # 执行100个并发请求
        start = time.time()
        tasks = [make_request(i) for i in range(100)]
        results = await asyncio.gather(*tasks)
        
        total_time = time.time() - start
        
        # 验证
        success_count = sum(1 for r in results if r["success"])
        assert success_count == 100, f"只有 {success_count}/100 个请求成功"
        assert total_time < 10, f"100并发处理时间 {total_time:.2f}s 过长"
        
        times = [r["time"] for r in results]
        print(f"\n100并发请求:")
        print(f"  成功率: {success_count}/100")
        print(f"  总时间: {total_time:.2f}s")
        print(f"  平均响应: {statistics.mean(times)*1000:.1f}ms")


# ============== 数据库查询性能测试 ==============

class TestDatabaseQueryPerformance:
    """数据库查询性能测试."""
    
    def test_simple_query_performance(self, client):
        """测试简单查询性能."""
        # 测试健康检查(简单查询)
        times = []
        
        for _ in range(100):
            start = time.time()
            response = client.get("/api/v1/health")
            elapsed = time.time() - start
            
            assert response.status_code == 200
            times.append(elapsed)
        
        avg_time = statistics.mean(times)
        p95_time = sorted(times)[int(len(times) * 0.95)]
        
        # 验证性能
        assert avg_time < 0.01, f"平均查询时间 {avg_time*1000:.1f}ms > 10ms"
        assert p95_time < 0.05, f"P95查询时间 {p95_time*1000:.1f}ms > 50ms"
        
        print(f"\n简单查询性能:")
        print(f"  平均: {avg_time*1000:.1f}ms")
        print(f"  P95: {p95_time*1000:.1f}ms")
    
    def test_knowledge_graph_query_performance(self, client):
        """测试知识图谱查询性能."""
        times = []
        
        for i in range(50):
            start = time.time()
            response = client.get(f"/api/v1/knowledge-graph/student_{i}")
            elapsed = time.time() - start
            
            assert response.status_code == 200
            times.append(elapsed)
        
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        # 验证性能
        assert avg_time < 0.1, f"平均查询时间 {avg_time*1000:.1f}ms > 100ms"
        
        print(f"\n知识图谱查询性能:")
        print(f"  平均: {avg_time*1000:.1f}ms")
        print(f"  最大: {max_time*1000:.1f}ms")


# ============== 负载测试 ==============

class TestLoadTesting:
    """负载测试."""
    
    def test_sustained_load_1_minute(self, client):
        """测试1分钟持续负载."""
        import io
        
        start_time = time.time()
        duration = 60  # 1分钟
        request_count = 0
        success_count = 0
        error_count = 0
        response_times = []
        
        while (time.time() - start_time) < duration:
            req_start = time.time()
            try:
                response = client.get("/api/v1/health")
                if response.status_code == 200:
                    success_count += 1
                else:
                    error_count += 1
            except Exception:
                error_count += 1
            
            response_times.append(time.time() - req_start)
            request_count += 1
            
            # 控制请求频率
            time.sleep(0.01)
        
        # 统计
        total_time = time.time() - start_time
        rps = request_count / total_time
        success_rate = success_count / request_count if request_count > 0 else 0
        
        # 验证
        assert success_rate > 0.99, f"成功率 {success_rate*100:.1f}% < 99%"
        assert error_count < 10, f"错误数 {error_count} 过多"
        
        print(f"\n1分钟持续负载测试:")
        print(f"  总请求: {request_count}")
        print(f"  成功: {success_count}")
        print(f"  失败: {error_count}")
        print(f"  RPS: {rps:.1f}")
        print(f"  成功率: {success_rate*100:.2f}%")
        print(f"  平均响应: {statistics.mean(response_times)*1000:.1f}ms")
    
    def test_burst_load_handling(self, client):
        """测试突发负载处理."""
        import io
        
        def burst_request(i):
            try:
                response = client.get("/api/v1/health")
                return response.status_code == 200
            except Exception:
                return False
        
        # 突发100个请求
        start = time.time()
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(burst_request, i) for i in range(100)]
            results = [f.result() for f in as_completed(futures)]
        
        elapsed = time.time() - start
        success_count = sum(results)
        
        # 验证系统能够处理突发负载
        assert success_count >= 95, f"突发负载下只有 {success_count}/100 成功"
        assert elapsed < 5, f"突发负载处理时间 {elapsed:.2f}s 过长"
        
        print(f"\n突发负载测试:")
        print(f"  成功: {success_count}/100")
        print(f"  处理时间: {elapsed:.2f}s")


# ============== 内存和稳定性测试 ==============

class TestStability:
    """稳定性测试."""
    
    def test_api_stability_multiple_requests(self, client):
        """测试API多次请求的稳定性."""
        errors = []
        response_times = []
        
        for i in range(200):
            start = time.time()
            try:
                response = client.get("/api/v1/health")
                if response.status_code != 200:
                    errors.append(f"Request {i}: status {response.status_code}")
            except Exception as e:
                errors.append(f"Request {i}: {str(e)}")
            
            response_times.append(time.time() - start)
        
        # 验证稳定性
        assert len(errors) == 0, f"出现 {len(errors)} 个错误: {errors[:5]}"
        
        # 验证响应时间稳定
        avg_time = statistics.mean(response_times)
        std_dev = statistics.stdev(response_times) if len(response_times) > 1 else 0
        
        assert std_dev / avg_time < 0.5 if avg_time > 0 else True, "响应时间波动过大"
        
        print(f"\n稳定性测试:")
        print(f"  总请求: 200")
        print(f"  错误: {len(errors)}")
        print(f"  平均响应: {avg_time*1000:.1f}ms")
        print(f"  标准差: {std_dev*1000:.1f}ms")


# ============== 性能基准测试 ==============

class TestPerformanceBenchmark:
    """性能基准测试."""
    
    def test_throughput_benchmark(self, client):
        """测试吞吐量基准."""
        import io
        
        # 测量10秒内的吞吐量
        start = time.time()
        duration = 10
        count = 0
        
        while (time.time() - start) < duration:
            response = client.get("/api/v1/health")
            if response.status_code == 200:
                count += 1
        
        actual_duration = time.time() - start
        throughput = count / actual_duration
        
        print(f"\n吞吐量基准:")
        print(f"  请求数: {count}")
        print(f"  时间: {actual_duration:.2f}s")
        print(f"  吞吐量: {throughput:.1f} req/s")
        
        # 基准: 至少50 req/s
        assert throughput > 50, f"吞吐量 {throughput:.1f} req/s < 50 req/s"
    
    def test_latency_percentiles(self, client):
        """测试延迟百分位."""
        times = []
        
        for _ in range(1000):
            start = time.time()
            response = client.get("/api/v1/health")
            times.append(time.time() - start)
            assert response.status_code == 200
        
        times.sort()
        
        p50 = times[int(len(times) * 0.50)]
        p95 = times[int(len(times) * 0.95)]
        p99 = times[int(len(times) * 0.99)]
        
        print(f"\n延迟百分位:")
        print(f"  P50: {p50*1000:.1f}ms")
        print(f"  P95: {p95*1000:.1f}ms")
        print(f"  P99: {p99*1000:.1f}ms")
        
        # 基准
        assert p50 < 0.01, f"P50 {p50*1000:.1f}ms > 10ms"
        assert p95 < 0.05, f"P95 {p95*1000:.1f}ms > 50ms"
        assert p99 < 0.1, f"P99 {p99*1000:.1f}ms > 100ms"
