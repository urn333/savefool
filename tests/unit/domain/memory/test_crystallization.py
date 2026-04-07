"""24小时结晶机制单元测试.

测试范围:
- 结晶条件判定
- 结晶执行器
- 调度器
- 数据压缩
- 监控

功能追溯ID: F-MEM-005, F-MEM-006
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.domain.memory.crystallization.conditions import (
    CrystallizationCheckResult,
    CrystallizationConditions,
)
from src.domain.memory.crystallization.executor import (
    CrystallizationContext,
    CrystallizationExecutor,
)
from src.domain.memory.crystallization.scheduler import (
    SchedulerConfig,
    SchedulerRunResult,
    CrystallizationScheduler,
)
from src.domain.memory.crystallization.compaction import (
    CompactionResult,
    CompressionConfig,
    MemoryCompaction,
)
from src.domain.memory.crystallization.monitor import (
    AlertRule,
    CrystallizationMetrics,
    CrystallizationMonitor,
)
from src.domain.memory.crystallization.jobs import CrystallizationJobManager
from src.domain.memory.meta_memory import CrystallizationResult
from src.infrastructure.db.cognitive_gap import CognitiveGap, GapEvidence
from src.infrastructure.db.enums import EvidenceType, GapStatus


class TestCrystallizationConditions:
    """测试结晶条件判定器."""
    
    @pytest.fixture
    def conditions(self):
        """创建条件判定器."""
        return CrystallizationConditions(observation_period_hours=24)
    
    @pytest.fixture
    def pending_gap(self):
        """创建待处理缺口."""
        gap = MagicMock(spec=CognitiveGap)
        gap.gap_id = "gap_001"
        gap.student_id = "student_001"
        gap.gap_type = "concept_gap"
        gap.status = GapStatus.PENDING.value
        gap.discovered_at = datetime.now() - timedelta(hours=25)  # 观察期已结束
        gap.occurrence_count = 1
        gap.related_knowledge = ["math_fraction"]
        return gap
    
    def test_check_observation_complete(self, conditions, pending_gap):
        """测试观察期检查."""
        # 观察期已结束
        assert conditions._is_observation_complete(pending_gap) is True
        
        # 观察期未结束
        pending_gap.discovered_at = datetime.now() - timedelta(hours=12)
        assert conditions._is_observation_complete(pending_gap) is False
    
    def test_check_repeat_error_condition(self, conditions, pending_gap):
        """测试重复错误条件."""
        # 条件不满足：只有初始诊断
        evidences = [EvidenceType.INITIAL_DIAGNOSIS]
        result = conditions._check_repeat_error(pending_gap, evidences)
        assert result.can_crystallize is False
        
        # 条件满足：有重复错误证据且出现次数>=2
        pending_gap.occurrence_count = 2
        evidences = [EvidenceType.INITIAL_DIAGNOSIS, EvidenceType.REPEAT_ERROR]
        result = conditions._check_repeat_error(pending_gap, evidences)
        assert result.can_crystallize is True
        assert "repeat_error" in result.reason
    
    def test_check_variant_failure_condition(self, conditions, pending_gap):
        """测试变形题失败条件."""
        # 条件不满足
        evidences = [EvidenceType.INITIAL_DIAGNOSIS]
        result = conditions._check_variant_failure(pending_gap, evidences)
        assert result.can_crystallize is False
        
        # 条件满足
        evidences = [EvidenceType.INITIAL_DIAGNOSIS, EvidenceType.VARIANT_FAILED]
        result = conditions._check_variant_failure(pending_gap, evidences)
        assert result.can_crystallize is True
        assert result.confidence == 0.9
    
    def test_check_cross_homework_condition(self, conditions, pending_gap):
        """测试跨作业共现条件."""
        # 条件不满足：出现次数<3
        pending_gap.occurrence_count = 2
        result = conditions._check_cross_homework(pending_gap)
        assert result.can_crystallize is False
        
        # 条件满足：出现次数>=3
        pending_gap.occurrence_count = 3
        result = conditions._check_cross_homework(pending_gap)
        assert result.can_crystallize is True
    
    def test_check_should_dismiss(self, conditions, pending_gap):
        """测试排除条件."""
        # 条件不满足：观察期未结束
        pending_gap.discovered_at = datetime.now() - timedelta(hours=12)
        evidences = [EvidenceType.INITIAL_DIAGNOSIS]
        result = conditions._check_should_dismiss(pending_gap, evidences)
        assert "not complete" in result.reason
        
        # 条件满足：观察期结束且只有初始诊断
        pending_gap.discovered_at = datetime.now() - timedelta(hours=25)
        result = conditions._check_should_dismiss(pending_gap, evidences)
        assert "should dismiss" in result.reason.lower()
    
    def test_check_crystallization_full_flow(self, conditions, pending_gap):
        """测试完整结晶检查流程."""
        # 状态不是pending
        pending_gap.status = GapStatus.CRYSTALLIZED.value
        result = conditions.check_crystallization(pending_gap, [])
        assert result.can_crystallize is False
        assert "not pending" in result.reason.lower()
        
        # 重置为pending
        pending_gap.status = GapStatus.PENDING.value
        
        # 观察期未结束
        pending_gap.discovered_at = datetime.now() - timedelta(hours=12)
        result = conditions.check_crystallization(pending_gap, [])
        assert result.can_crystallize is False
        assert "not complete" in result.reason.lower()
        
        # 观察期结束且有重复错误证据
        pending_gap.discovered_at = datetime.now() - timedelta(hours=25)
        pending_gap.occurrence_count = 2
        evidences = [EvidenceType.INITIAL_DIAGNOSIS, EvidenceType.REPEAT_ERROR]
        result = conditions.check_crystallization(pending_gap, evidences)
        assert result.can_crystallize is True
        assert result.confidence > 0


class TestCrystallizationExecutor:
    """测试结晶执行器."""
    
    @pytest.fixture
    def mock_repos(self):
        """创建mock Repository."""
        gap_repo = AsyncMock()
        evidence_repo = AsyncMock()
        profile_memory = AsyncMock()
        return gap_repo, evidence_repo, profile_memory
    
    @pytest.fixture
    def executor(self, mock_repos):
        """创建执行器."""
        gap_repo, evidence_repo, profile_memory = mock_repos
        return CrystallizationExecutor(
            gap_repo=gap_repo,
            evidence_repo=evidence_repo,
            profile_memory=profile_memory,
        )
    
    @pytest.fixture
    def pending_gap(self):
        """创建待处理缺口."""
        gap = MagicMock(spec=CognitiveGap)
        gap.gap_id = "gap_001"
        gap.student_id = "student_001"
        gap.gap_type = "concept_gap"
        gap.status = GapStatus.PENDING.value
        gap.discovered_at = datetime.now() - timedelta(hours=25)
        gap.occurrence_count = 2
        gap.related_knowledge = ["math_fraction"]
        gap.updated_at = datetime.now()
        return gap
    
    @pytest.mark.asyncio
    async def test_crystallize_success(self, executor, mock_repos, pending_gap):
        """测试成功结晶."""
        gap_repo, evidence_repo, profile_memory = mock_repos
        
        # 设置mock返回值
        gap_repo.get_by_id.return_value = pending_gap
        evidence_repo.find_many.return_value = [
            MagicMock(
                evidence_type=EvidenceType.REPEAT_ERROR.value,
                diagnosis_id="diag_001",
            ),
        ]
        
        result = await executor.crystallize("gap_001")
        
        assert result is not None
        assert result.success is True
        assert result.new_status == GapStatus.CRYSTALLIZED.value
        
        # 验证状态更新
        assert pending_gap.status == GapStatus.CRYSTALLIZED.value
        gap_repo.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_crystallize_not_found(self, executor, mock_repos):
        """测试缺口不存在."""
        gap_repo, _, _ = mock_repos
        gap_repo.get_by_id.return_value = None
        
        result = await executor.crystallize("gap_999")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_crystallize_conditions_not_met(self, executor, mock_repos, pending_gap):
        """测试条件不满足."""
        gap_repo, evidence_repo, _ = mock_repos
        
        pending_gap.discovered_at = datetime.now() - timedelta(hours=12)  # 观察期未结束
        gap_repo.get_by_id.return_value = pending_gap
        evidence_repo.find_many.return_value = [
            MagicMock(evidence_type=EvidenceType.INITIAL_DIAGNOSIS.value),
        ]
        
        result = await executor.crystallize("gap_001")
        
        assert result is not None
        assert result.success is False
        assert result.new_status == GapStatus.PENDING.value
    
    @pytest.mark.asyncio
    async def test_dismiss_success(self, executor, mock_repos, pending_gap):
        """测试成功排除."""
        gap_repo, _, _ = mock_repos
        gap_repo.get_by_id.return_value = pending_gap
        
        result = await executor.dismiss("gap_001", reason="Test dismissal")
        
        assert result is not None
        assert result.success is True
        assert result.new_status == GapStatus.DISMISSED.value
        assert "Test dismissal" in result.reason
    
    @pytest.mark.asyncio
    async def test_batch_crystallize(self, executor, mock_repos, pending_gap):
        """测试批量结晶."""
        gap_repo, evidence_repo, _ = mock_repos
        
        gap_repo.get_by_id.return_value = pending_gap
        evidence_repo.find_many.return_value = [
            MagicMock(evidence_type=EvidenceType.REPEAT_ERROR.value),
        ]
        
        results = await executor.batch_crystallize(["gap_001", "gap_002"])
        
        assert len(results) == 2
        assert all(r.success for r in results)


class TestCrystallizationScheduler:
    """测试结晶调度器."""
    
    @pytest.fixture
    def mock_repos(self):
        """创建mock Repository."""
        gap_repo = AsyncMock()
        evidence_repo = AsyncMock()
        return gap_repo, evidence_repo
    
    @pytest.fixture
    def scheduler(self, mock_repos):
        """创建调度器."""
        gap_repo, evidence_repo = mock_repos
        config = SchedulerConfig(
            batch_size=10,
            dry_run=False,
        )
        return CrystallizationScheduler(
            gap_repo=gap_repo,
            evidence_repo=evidence_repo,
            config=config,
        )
    
    def test_is_in_execution_window(self, scheduler):
        """测试执行窗口检查."""
        # 凌晨2点30分在窗口内
        test_time = datetime.now().replace(hour=2, minute=30)
        assert scheduler.is_in_execution_window(test_time) is True
        
        # 上午10点不在窗口内
        test_time = datetime.now().replace(hour=10, minute=0)
        assert scheduler.is_in_execution_window(test_time) is False
    
    def test_get_next_run_time(self, scheduler):
        """测试获取下次运行时间."""
        from_time = datetime.now().replace(hour=10, minute=0, second=0)
        
        next_run = scheduler.get_next_run_time(from_time)
        
        # 应该是明天的2-2:30之间
        assert next_run.hour == 2
        assert next_run >= from_time
        assert (next_run - from_time).days >= 0
    
    def test_sort_by_priority(self, scheduler):
        """测试优先级排序."""
        # 创建测试缺口
        gap1 = MagicMock(spec=CognitiveGap)
        gap1.discovered_at = datetime.now() - timedelta(hours=48)
        gap1.occurrence_count = 5
        
        gap2 = MagicMock(spec=CognitiveGap)
        gap2.discovered_at = datetime.now() - timedelta(hours=12)  # 观察期未结束
        gap2.occurrence_count = 2
        
        gap3 = MagicMock(spec=CognitiveGap)
        gap3.discovered_at = datetime.now() - timedelta(hours=25)
        gap3.occurrence_count = 10
        
        gaps = [gap1, gap2, gap3]
        sorted_gaps = scheduler._sort_by_priority(gaps)
        
        # gap3应该排在最前面(观察期结束+出现次数多)
        assert sorted_gaps[0] == gap3
    
    @pytest.mark.asyncio
    async def test_run_daily_crystallization_empty(self, scheduler, mock_repos):
        """测试无待处理缺口的情况."""
        gap_repo, _ = mock_repos
        gap_repo.find_many.return_value = []
        
        result = await scheduler.run_daily_crystallization()
        
        assert result.total_gaps == 0
        assert result.crystallized == 0
    
    @pytest.mark.asyncio
    async def test_run_daily_crystallization_with_gaps(self, scheduler, mock_repos):
        """测试有待处理缺口的情况."""
        gap_repo, evidence_repo = mock_repos
        
        # 创建测试缺口
        gap = MagicMock(spec=CognitiveGap)
        gap.gap_id = "gap_001"
        gap.student_id = "student_001"
        gap.status = GapStatus.PENDING.value
        gap.discovered_at = datetime.now() - timedelta(hours=25)
        gap.occurrence_count = 3
        gap.updated_at = datetime.now()
        
        gap_repo.find_many.return_value = [gap]
        gap_repo.get_by_id.return_value = gap
        evidence_repo.find_many.return_value = [
            MagicMock(evidence_type=EvidenceType.REPEAT_ERROR.value),
        ]
        
        result = await scheduler.run_daily_crystallization()
        
        assert result.total_gaps == 1
        # 由于条件满足，应该成功结晶
        assert result.crystallized + result.dismissed + result.skipped == 1


class TestMemoryCompaction:
    """测试数据压缩."""
    
    @pytest.fixture
    def mock_repos(self):
        """创建mock Repository."""
        homework_repo = AsyncMock()
        answer_repo = AsyncMock()
        trace_repo = AsyncMock()
        return homework_repo, answer_repo, trace_repo
    
    @pytest.fixture
    def compactor(self, mock_repos):
        """创建压缩器."""
        homework_repo, answer_repo, trace_repo = mock_repos
        config = CompressionConfig(dry_run=True)
        return MemoryCompaction(
            homework_repo=homework_repo,
            answer_repo=answer_repo,
            trace_repo=trace_repo,
            config=config,
        )
    
    @pytest.mark.asyncio
    async def test_run_compaction(self, compactor, mock_repos):
        """测试运行压缩."""
        homework_repo, _, _ = mock_repos
        homework_repo.find_many.return_value = []
        
        before_date = datetime.now() - timedelta(days=30)
        result = await compactor.run_compaction(before_date)
        
        assert result.compacted_count == 0
        assert result.errors == []
    
    def test_estimate_compression_ratio(self, compactor):
        """测试预估压缩比率."""
        before_date = datetime.now() - timedelta(days=30)
        
        ratios = compactor.estimate_compression_ratio(before_date)
        
        assert "episodic_estimate" in ratios
        assert "image_estimate" in ratios
        assert "overall_estimate" in ratios
        assert all(0 <= v <= 1 for v in ratios.values())


class TestCrystallizationMonitor:
    """测试结晶监控."""
    
    @pytest.fixture
    def mock_repos(self):
        """创建mock Repository."""
        gap_repo = AsyncMock()
        evidence_repo = AsyncMock()
        return gap_repo, evidence_repo
    
    @pytest.fixture
    def monitor(self, mock_repos):
        """创建监控器."""
        gap_repo, evidence_repo = mock_repos
        return CrystallizationMonitor(
            gap_repo=gap_repo,
            evidence_repo=evidence_repo,
        )
    
    @pytest.mark.asyncio
    async def test_collect_crystallization_metrics(self, monitor, mock_repos):
        """测试收集结晶指标."""
        gap_repo, evidence_repo = mock_repos
        
        gap_repo.find_many.return_value = [
            MagicMock(
                gap_id="gap_001",
                discovered_at=datetime.now() - timedelta(hours=25),
                occurrence_count=2,
            ),
        ]
        evidence_repo.find_many.return_value = [
            MagicMock(evidence_type=EvidenceType.REPEAT_ERROR.value),
        ]
        
        metrics = await monitor.collect_crystallization_metrics()
        
        assert metrics.total_pending == 1
        assert metrics.evidence_per_gap > 0
    
    @pytest.mark.asyncio
    async def test_check_alerts(self, monitor, mock_repos):
        """测试告警检查."""
        gap_repo, evidence_repo = mock_repos
        
        # 设置大量pending缺口触发告警
        gap_repo.find_many.return_value = [
            MagicMock(discovered_at=datetime.now() - timedelta(hours=i))
            for i in range(1500)  # 超过1000阈值
        ]
        evidence_repo.find_many.return_value = []
        
        alerts = await monitor.check_alerts()
        
        # 应该触发高pending gaps告警
        high_pending_alert = [a for a in alerts if a.rule_name == "high_pending_gaps"]
        assert len(high_pending_alert) > 0
    
    def test_alert_rule_check(self):
        """测试告警规则检查."""
        # 小于规则
        rule = AlertRule(
            name="test",
            metric="test_metric",
            threshold=0.5,
            operator="<",
            severity="warning",
            message_template="test",
        )
        assert rule.check(0.3) is True
        assert rule.check(0.7) is False
        
        # 大于规则
        rule.operator = ">"
        assert rule.check(0.7) is True
        assert rule.check(0.3) is False


class TestCrystallizationJobManager:
    """测试任务管理器."""
    
    @pytest.fixture
    def mock_scheduler(self):
        """创建mock调度器."""
        return AsyncMock()
    
    @pytest.fixture
    def job_manager(self, mock_scheduler):
        """创建任务管理器."""
        return CrystallizationJobManager(
            scheduler=mock_scheduler,
        )
    
    @pytest.mark.asyncio
    async def test_daily_crystallization_job(self, job_manager, mock_scheduler):
        """测试每日结晶任务."""
        mock_scheduler.run_daily_crystallization.return_value = SchedulerRunResult(
            run_id="test_run",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            total_gaps=10,
            crystallized=8,
            dismissed=1,
            failed=1,
            skipped=0,
            details=[],
        )
        
        result = await job_manager.daily_crystallization_job()
        
        assert result.total_gaps == 10
        assert result.crystallized == 8
        mock_scheduler.run_daily_crystallization.assert_called_once()
    
    def test_get_job_definitions(self, job_manager):
        """测试获取任务定义."""
        jobs = job_manager.get_job_definitions()
        
        assert "daily_crystallization" in jobs
        assert "weekly_compaction" in jobs
        assert "hourly_monitor" in jobs
        
        # 检查任务配置
        daily_job = jobs["daily_crystallization"]
        assert daily_job["schedule"]["hour"] == 2
        assert daily_job["schedule"]["minute"] == 0
    
    def test_get_cron_expressions(self, job_manager):
        """测试获取cron表达式."""
        crons = job_manager.get_cron_expressions()
        
        assert "daily_crystallization" in crons
        assert "weekly_compaction" in crons
        assert "hourly_monitor" in crons
        
        # 验证格式
        assert len(crons["daily_crystallization"].split()) == 5


class TestIntegrationFlow:
    """集成流程测试."""
    
    @pytest.mark.asyncio
    async def test_full_crystallization_flow(self):
        """测试完整结晶流程."""
        # 这个测试模拟完整的结晶流程:
        # 1. 创建pending gap
        # 2. 添加证据
        # 3. 执行结晶
        # 4. 验证状态更新
        
        # 创建mock
        gap_repo = AsyncMock()
        evidence_repo = AsyncMock()
        
        # 创建测试缺口
        gap = MagicMock(spec=CognitiveGap)
        gap.gap_id = "gap_test"
        gap.student_id = "student_test"
        gap.status = GapStatus.PENDING.value
        gap.gap_type = "concept_gap"
        gap.discovered_at = datetime.now() - timedelta(hours=25)
        gap.occurrence_count = 3
        gap.related_knowledge = ["math_fraction"]
        gap.updated_at = datetime.now()
        
        gap_repo.get_by_id.return_value = gap
        evidence_repo.find_many.return_value = [
            MagicMock(evidence_type=EvidenceType.INITIAL_DIAGNOSIS.value),
            MagicMock(evidence_type=EvidenceType.REPEAT_ERROR.value),
            MagicMock(evidence_type=EvidenceType.CROSS_HOMEWORK.value),
        ]
        
        # 创建执行器并执行
        executor = CrystallizationExecutor(
            gap_repo=gap_repo,
            evidence_repo=evidence_repo,
        )
        
        result = await executor.crystallize("gap_test")
        
        # 验证结果
        assert result is not None
        assert result.success is True
        assert result.new_status == GapStatus.CRYSTALLIZED.value
        assert result.feature_id is not None
        
        # 验证状态更新
        assert gap.status == GapStatus.CRYSTALLIZED.value
        assert gap.crystallized_at is not None
        gap_repo.update.assert_called_once()
