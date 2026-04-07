"""并行协调器测试.

测试并行任务协调功能:
- 并行调用测试
- 超时控制测试
- 部分失败处理测试
- 结果收集测试

使用Mock测试，不依赖真实API调用。
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch

from src.domain.engines.parallel_coordinator import (
    ParallelCoordinator,
    CoordinatorConfig,
    ModelTaskResult,
)
from src.domain.engines.model_schedulers import (
    ModelAScheduler,
    ModelBScheduler,
    ModelCScheduler,
    SchedulerConfig,
    ParsedProblem,
)
from src.domain.models.arbitration import ModelResult
from src.domain.models.diagnosis import ErrorType


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def coordinator_config():
    """协调器配置."""
    return CoordinatorConfig(
        timeout=5.0,
        max_concurrent=3,
        continue_on_error=True,
    )


@pytest.fixture
def sample_problem():
    """示例题目."""
    return ParsedProblem(
        content="解方程: 2x + 5 = 15",
        student_answer="5",
        subject="math",
    )


@pytest.fixture
def mock_scheduler_a():
    """Mock模型A调度器."""
    scheduler = Mock(spec=ModelAScheduler)
    scheduler.config = SchedulerConfig(
        model_id="model_a",
        model_name="gpt-4",
        weight=0.4,
    )
    return scheduler


@pytest.fixture
def mock_scheduler_b():
    """Mock模型B调度器."""
    scheduler = Mock(spec=ModelBScheduler)
    scheduler.config = SchedulerConfig(
        model_id="model_b",
        model_name="deepseek-math",
        weight=0.4,
    )
    return scheduler


@pytest.fixture
def mock_scheduler_c():
    """Mock模型C调度器."""
    scheduler = Mock(spec=ModelCScheduler)
    scheduler.config = SchedulerConfig(
        model_id="model_c",
        model_name="llama-3-70b",
        weight=0.2,
    )
    return scheduler


@pytest.fixture
def sample_model_result_a():
    """示例模型A结果."""
    return ModelResult(
        model_id="model_a",
        is_correct=True,
        error_type=None,
        concept_scores={"concept_0": 1.0},
        confidence=0.92,
        diagnosis={"analysis": "正确"},
        latency_ms=1200.0,
    )


@pytest.fixture
def sample_model_result_b():
    """示例模型B结果."""
    return ModelResult(
        model_id="model_b",
        is_correct=True,
        error_type=None,
        concept_scores={"logic": 0.95},
        confidence=0.94,
        diagnosis={"steps": []},
        latency_ms=1500.0,
    )


@pytest.fixture
def sample_model_result_c():
    """示例模型C结果."""
    return ModelResult(
        model_id="model_c",
        is_correct=True,
        error_type=None,
        concept_scores={},
        confidence=0.87,
        diagnosis={"concept_map": {}},
        latency_ms=1800.0,
    )


# =============================================================================
# Parallel Execution Tests
# =============================================================================

class TestParallelExecution:
    """并行执行测试类."""
    
    @pytest.mark.asyncio
    async def test_execute_parallel_all_success(
        self,
        coordinator_config,
        sample_problem,
        mock_scheduler_a,
        mock_scheduler_b,
        mock_scheduler_c,
        sample_model_result_a,
        sample_model_result_b,
        sample_model_result_c,
    ):
        """测试所有模型并行执行成功.
        
        Given: 三个模型调度器
        When: 并行执行
        Then: 返回所有模型的成功结果
        """
        # Given: 配置Mock返回成功结果
        mock_scheduler_a.schedule = AsyncMock(return_value=sample_model_result_a)
        mock_scheduler_b.schedule = AsyncMock(return_value=sample_model_result_b)
        mock_scheduler_c.schedule = AsyncMock(return_value=sample_model_result_c)
        
        schedulers = [mock_scheduler_a, mock_scheduler_b, mock_scheduler_c]
        
        # When: 并行执行
        coordinator = ParallelCoordinator(coordinator_config)
        results = await coordinator.execute_parallel(schedulers, sample_problem)
        
        # Then: 验证结果
        assert len(results) == 3
        assert results["model_a"].success is True
        assert results["model_b"].success is True
        assert results["model_c"].success is True
        assert results["model_a"].result == sample_model_result_a
        assert results["model_b"].result == sample_model_result_b
        assert results["model_c"].result == sample_model_result_c
    
    @pytest.mark.asyncio
    async def test_execute_parallel_concurrent_execution(
        self,
        coordinator_config,
        sample_problem,
        mock_scheduler_a,
        mock_scheduler_b,
        mock_scheduler_c,
    ):
        """测试模型真正并行执行.
        
        Given: 三个耗时不同的模型
        When: 并行执行
        Then: 总耗时接近最慢的模型，而不是累加
        """
        # Given: 配置不同耗时的异步任务
        async def slow_schedule(*args):
            await asyncio.sleep(0.1)
            return ModelResult(
                model_id="model_a",
                is_correct=True,
                confidence=0.9,
                latency_ms=100.0,
            )
        
        async def fast_schedule(*args):
            await asyncio.sleep(0.01)
            return ModelResult(
                model_id="model_b",
                is_correct=True,
                confidence=0.9,
                latency_ms=10.0,
            )
        
        async def medium_schedule(*args):
            await asyncio.sleep(0.05)
            return ModelResult(
                model_id="model_c",
                is_correct=True,
                confidence=0.9,
                latency_ms=50.0,
            )
        
        mock_scheduler_a.schedule = slow_schedule
        mock_scheduler_b.schedule = fast_schedule
        mock_scheduler_c.schedule = medium_schedule
        
        schedulers = [mock_scheduler_a, mock_scheduler_b, mock_scheduler_c]
        
        # When: 并行执行并计时
        coordinator = ParallelCoordinator(coordinator_config)
        start_time = asyncio.get_event_loop().time()
        results = await coordinator.execute_parallel(schedulers, sample_problem)
        elapsed_time = asyncio.get_event_loop().time() - start_time
        
        # Then: 验证并行执行（总时间应小于累加时间0.16秒，但大于最慢的单次0.1秒）
        assert elapsed_time < 0.15  # 并行应小于累加时间
        assert elapsed_time >= 0.1  # 但必须等待最慢的任务
        assert len(results) == 3
    
    @pytest.mark.asyncio
    async def test_execute_parallel_with_images(
        self,
        coordinator_config,
        mock_scheduler_a,
        mock_scheduler_b,
        sample_model_result_a,
        sample_model_result_b,
    ):
        """测试带图片的并行执行.
        
        Given: 题目包含图片
        When: 并行执行
        Then: 将图片传递给每个调度器
        """
        # Given: 配置Mock
        mock_scheduler_a.schedule = AsyncMock(return_value=sample_model_result_a)
        mock_scheduler_b.schedule = AsyncMock(return_value=sample_model_result_b)
        
        problem = ParsedProblem(content="[图片题目]", student_answer="5")
        images = ["base64_image_1", "base64_image_2"]
        schedulers = [mock_scheduler_a, mock_scheduler_b]
        
        # When: 并行执行
        coordinator = ParallelCoordinator(coordinator_config)
        results = await coordinator.execute_parallel(schedulers, problem, images)
        
        # Then: 验证图片被传递
        mock_scheduler_a.schedule.assert_called_once_with(problem, images)
        mock_scheduler_b.schedule.assert_called_once_with(problem, images)


# =============================================================================
# Timeout Control Tests
# =============================================================================

class TestTimeoutControl:
    """超时控制测试类."""
    
    @pytest.mark.asyncio
    async def test_timeout_single_model(
        self,
        sample_problem,
        mock_scheduler_a,
    ):
        """测试单模型超时.
        
        Given: 配置1秒超时，模型执行2秒
        When: 执行并行任务
        Then: 超时的模型返回失败结果
        """
        # Given: 配置超时和慢速模型
        config = CoordinatorConfig(timeout=0.1)
        
        async def slow_schedule(*args):
            await asyncio.sleep(0.2)  # 超过超时时间
            return ModelResult(model_id="model_a", is_correct=True, confidence=0.9)
        
        mock_scheduler_a.schedule = slow_schedule
        
        # When: 执行
        coordinator = ParallelCoordinator(config)
        results = await coordinator.execute_parallel([mock_scheduler_a], sample_problem)
        
        # Then: 验证超时结果
        assert results["model_a"].success is False
        assert "timeout" in results["model_a"].error.lower()
        assert results["model_a"].latency_ms == 100.0  # 超时配置的值
    
    @pytest.mark.asyncio
    async def test_timeout_partial_models(
        self,
        sample_problem,
        mock_scheduler_a,
        mock_scheduler_b,
        mock_scheduler_c,
        sample_model_result_a,
    ):
        """测试部分模型超时.
        
        Given: 三个模型中两个超时
        When: 执行并行任务
        Then: 一个成功，两个超时失败
        """
        # Given: 一个快模型，两个慢模型
        config = CoordinatorConfig(timeout=0.1)
        
        async def fast_schedule(*args):
            return sample_model_result_a
        
        async def slow_schedule(*args):
            await asyncio.sleep(0.2)
            return ModelResult(model_id="model_b", is_correct=True, confidence=0.9)
        
        mock_scheduler_a.schedule = fast_schedule
        mock_scheduler_b.schedule = slow_schedule
        mock_scheduler_c.schedule = slow_schedule
        
        # When: 执行
        coordinator = ParallelCoordinator(config)
        results = await coordinator.execute_parallel(
            [mock_scheduler_a, mock_scheduler_b, mock_scheduler_c],
            sample_problem
        )
        
        # Then: 验证结果
        assert results["model_a"].success is True
        assert results["model_b"].success is False
        assert results["model_c"].success is False
    
    @pytest.mark.asyncio
    async def test_timeout_all_models(
        self,
        sample_problem,
        mock_scheduler_a,
        mock_scheduler_b,
    ):
        """测试所有模型超时.
        
        Given: 所有模型都超时
        When: 执行并行任务
        Then: 所有模型返回超时失败
        """
        # Given: 配置短超时和慢速模型
        config = CoordinatorConfig(timeout=0.05)
        
        async def slow_schedule(*args):
            await asyncio.sleep(0.1)
            return ModelResult(model_id="model_x", is_correct=True, confidence=0.9)
        
        mock_scheduler_a.schedule = slow_schedule
        mock_scheduler_b.schedule = slow_schedule
        
        # When: 执行
        coordinator = ParallelCoordinator(config)
        results = await coordinator.execute_parallel(
            [mock_scheduler_a, mock_scheduler_b],
            sample_problem
        )
        
        # Then: 验证所有超时
        assert all(r.success is False for r in results.values())
        assert all("timeout" in r.error.lower() for r in results.values())


# =============================================================================
# Partial Failure Tests
# =============================================================================

class TestPartialFailure:
    """部分失败处理测试类."""
    
    @pytest.mark.asyncio
    async def test_single_model_failure(
        self,
        coordinator_config,
        sample_problem,
        mock_scheduler_a,
        mock_scheduler_b,
        mock_scheduler_c,
        sample_model_result_a,
        sample_model_result_c,
    ):
        """测试单模型失败.
        
        Given: 三个模型中一个抛出异常
        When: 执行并行任务
        Then: 成功模型返回结果，失败模型返回错误
        """
        # Given: 配置一个失败的模型
        mock_scheduler_a.schedule = AsyncMock(return_value=sample_model_result_a)
        mock_scheduler_b.schedule = AsyncMock(side_effect=Exception("API Error"))
        mock_scheduler_c.schedule = AsyncMock(return_value=sample_model_result_c)
        
        schedulers = [mock_scheduler_a, mock_scheduler_b, mock_scheduler_c]
        
        # When: 执行
        coordinator = ParallelCoordinator(coordinator_config)
        results = await coordinator.execute_parallel(schedulers, sample_problem)
        
        # Then: 验证部分失败处理
        assert results["model_a"].success is True
        assert results["model_b"].success is False
        assert results["model_c"].success is True
        assert "API Error" in results["model_b"].error
    
    @pytest.mark.asyncio
    async def test_two_models_failure(
        self,
        coordinator_config,
        sample_problem,
        mock_scheduler_a,
        mock_scheduler_b,
        mock_scheduler_c,
        sample_model_result_b,
    ):
        """测试两模型失败.
        
        Given: 三个模型中两个抛出异常
        When: 执行并行任务
        Then: 仅一个成功，两个返回错误
        """
        # Given: 配置两个失败的模型
        mock_scheduler_a.schedule = AsyncMock(side_effect=Exception("Network Error"))
        mock_scheduler_b.schedule = AsyncMock(return_value=sample_model_result_b)
        mock_scheduler_c.schedule = AsyncMock(side_effect=Exception("Timeout"))
        
        schedulers = [mock_scheduler_a, mock_scheduler_b, mock_scheduler_c]
        
        # When: 执行
        coordinator = ParallelCoordinator(coordinator_config)
        results = await coordinator.execute_parallel(schedulers, sample_problem)
        
        # Then: 验证结果
        assert results["model_a"].success is False
        assert results["model_b"].success is True
        assert results["model_c"].success is False
        assert results["model_b"].result == sample_model_result_b
    
    @pytest.mark.asyncio
    async def test_all_models_failure(
        self,
        coordinator_config,
        sample_problem,
        mock_scheduler_a,
        mock_scheduler_b,
        mock_scheduler_c,
    ):
        """测试所有模型失败.
        
        Given: 所有模型都抛出异常
        When: 执行并行任务
        Then: 所有模型返回失败
        """
        # Given: 配置所有模型失败
        mock_scheduler_a.schedule = AsyncMock(side_effect=Exception("Error A"))
        mock_scheduler_b.schedule = AsyncMock(side_effect=Exception("Error B"))
        mock_scheduler_c.schedule = AsyncMock(side_effect=Exception("Error C"))
        
        schedulers = [mock_scheduler_a, mock_scheduler_b, mock_scheduler_c]
        
        # When: 执行
        coordinator = ParallelCoordinator(coordinator_config)
        results = await coordinator.execute_parallel(schedulers, sample_problem)
        
        # Then: 验证全部失败
        assert all(r.success is False for r in results.values())
        # 错误消息包含原始错误和执行上下文
        assert "Error A" in results["model_a"].error
        assert "Error B" in results["model_b"].error
        assert "Error C" in results["model_c"].error
    
    @pytest.mark.asyncio
    async def test_continue_on_error_disabled(
        self,
        sample_problem,
        mock_scheduler_a,
        mock_scheduler_b,
    ):
        """测试关闭错误继续选项.
        
        Given: continue_on_error=False
        When: 一个模型失败
        Then: 其他模型结果不受影响
        """
        # Given: 配置关闭错误继续
        config = CoordinatorConfig(continue_on_error=False)
        
        mock_scheduler_a.schedule = AsyncMock(side_effect=Exception("Error"))
        mock_scheduler_b.schedule = AsyncMock(return_value=ModelResult(
            model_id="model_b", is_correct=True, confidence=0.9
        ))
        
        # When: 执行
        coordinator = ParallelCoordinator(config)
        results = await coordinator.execute_parallel(
            [mock_scheduler_a, mock_scheduler_b],
            sample_problem
        )
        
        # Then: 验证结果收集不受continue_on_error影响
        # 注意：当前实现中continue_on_error主要影响日志行为
        # 所有结果都会被收集
        assert len(results) == 2


# =============================================================================
# Result Collection Tests
# =============================================================================

class TestResultCollection:
    """结果收集测试类."""
    
    def test_get_successful_results(self, coordinator_config):
        """测试获取成功结果.
        
        Given: 混合成功和失败的模型结果
        When: 调用get_successful_results
        Then: 仅返回成功的结果
        """
        # Given: 混合结果
        task_results = {
            "model_a": ModelTaskResult(
                model_id="model_a",
                success=True,
                result=ModelResult(model_id="model_a", is_correct=True, confidence=0.9),
            ),
            "model_b": ModelTaskResult(
                model_id="model_b",
                success=False,
                error="Timeout",
            ),
            "model_c": ModelTaskResult(
                model_id="model_c",
                success=True,
                result=ModelResult(model_id="model_c", is_correct=False, confidence=0.8),
            ),
        }
        
        # When: 获取成功结果
        coordinator = ParallelCoordinator(coordinator_config)
        successful = coordinator.get_successful_results(task_results)
        
        # Then: 验证只返回成功的
        assert len(successful) == 2
        assert all(r.model_id in ["model_a", "model_c"] for r in successful)
    
    def test_get_successful_results_all_success(self, coordinator_config):
        """测试所有结果都成功.
        
        Given: 所有模型都成功
        When: 调用get_successful_results
        Then: 返回所有结果
        """
        # Given: 全部成功
        task_results = {
            "model_a": ModelTaskResult(
                model_id="model_a",
                success=True,
                result=ModelResult(model_id="model_a", is_correct=True, confidence=0.9),
            ),
            "model_b": ModelTaskResult(
                model_id="model_b",
                success=True,
                result=ModelResult(model_id="model_b", is_correct=True, confidence=0.8),
            ),
        }
        
        # When: 获取成功结果
        coordinator = ParallelCoordinator(coordinator_config)
        successful = coordinator.get_successful_results(task_results)
        
        # Then: 验证返回所有
        assert len(successful) == 2
    
    def test_get_successful_results_all_failure(self, coordinator_config):
        """测试所有结果都失败.
        
        Given: 所有模型都失败
        When: 调用get_successful_results
        Then: 返回空列表
        """
        # Given: 全部失败
        task_results = {
            "model_a": ModelTaskResult(
                model_id="model_a",
                success=False,
                error="Error A",
            ),
            "model_b": ModelTaskResult(
                model_id="model_b",
                success=False,
                error="Error B",
            ),
        }
        
        # When: 获取成功结果
        coordinator = ParallelCoordinator(coordinator_config)
        successful = coordinator.get_successful_results(task_results)
        
        # Then: 验证返回空列表
        assert len(successful) == 0
    
    def test_get_failed_models(self, coordinator_config):
        """测试获取失败模型列表.
        
        Given: 混合成功和失败的模型结果
        When: 调用get_failed_models
        Then: 返回失败的模型ID列表
        """
        # Given: 混合结果
        task_results = {
            "model_a": ModelTaskResult(
                model_id="model_a",
                success=True,
                result=ModelResult(model_id="model_a", is_correct=True, confidence=0.9),
            ),
            "model_b": ModelTaskResult(
                model_id="model_b",
                success=False,
                error="Timeout",
            ),
            "model_c": ModelTaskResult(
                model_id="model_c",
                success=False,
                error="API Error",
            ),
        }
        
        # When: 获取失败模型
        coordinator = ParallelCoordinator(coordinator_config)
        failed = coordinator.get_failed_models(task_results)
        
        # Then: 验证返回失败的模型ID
        assert len(failed) == 2
        assert "model_b" in failed
        assert "model_c" in failed
        assert "model_a" not in failed
    
    @pytest.mark.asyncio
    async def test_execute_with_fallback(
        self,
        coordinator_config,
        sample_problem,
        mock_scheduler_a,
        mock_scheduler_b,
        sample_model_result_a,
    ):
        """测试带最小成功数的执行.
        
        Given: 需要至少2个模型成功
        When: 只有一个模型成功
        Then: 返回结果并记录警告
        """
        # Given: 只有一个成功
        mock_scheduler_a.schedule = AsyncMock(return_value=sample_model_result_a)
        mock_scheduler_b.schedule = AsyncMock(side_effect=Exception("Error"))
        
        # When: 执行（要求最少2个成功）
        coordinator = ParallelCoordinator(coordinator_config)
        results = await coordinator.execute_with_fallback(
            [mock_scheduler_a, mock_scheduler_b],
            sample_problem,
            min_success=2,
        )
        
        # Then: 验证返回结果
        assert len(results) == 2
        assert results["model_a"].success is True
        assert results["model_b"].success is False


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """边界情况测试类."""
    
    @pytest.mark.asyncio
    async def test_empty_scheduler_list(self, coordinator_config, sample_problem):
        """测试空调度器列表.
        
        Given: 空调度器列表
        When: 执行并行任务
        Then: 返回空结果
        """
        # When: 执行空列表
        coordinator = ParallelCoordinator(coordinator_config)
        results = await coordinator.execute_parallel([], sample_problem)
        
        # Then: 返回空字典
        assert results == {}
    
    @pytest.mark.asyncio
    async def test_single_scheduler(self, coordinator_config, sample_problem, mock_scheduler_a):
        """测试单调度器.
        
        Given: 只有一个调度器
        When: 执行并行任务
        Then: 返回单个结果
        """
        # Given: 单调度器
        mock_scheduler_a.schedule = AsyncMock(return_value=ModelResult(
            model_id="model_a", is_correct=True, confidence=0.9
        ))
        
        # When: 执行
        coordinator = ParallelCoordinator(coordinator_config)
        results = await coordinator.execute_parallel([mock_scheduler_a], sample_problem)
        
        # Then: 验证单个结果
        assert len(results) == 1
        assert results["model_a"].success is True
