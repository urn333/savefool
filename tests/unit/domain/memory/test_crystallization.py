"""24小时结晶机制单元测试. 功能追溯ID: F-MEM-005, F-MEM-006"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from src.domain.memory.crystallization.conditions import CrystallizationConditions, CrystallizationCheckResult
from src.domain.memory.crystallization.executor import CrystallizationExecutor, CrystallizationContext
from src.domain.memory.crystallization.scheduler import SchedulerConfig, SchedulerRunResult, CrystallizationScheduler
from src.domain.memory.crystallization.compaction import CompactionResult, CompressionConfig, MemoryCompaction
from src.domain.memory.crystallization.monitor import CrystallizationMetrics, CompactionMetrics, AlertRule, Alert, CrystallizationMonitor
from src.domain.memory.crystallization.jobs import CrystallizationJobManager
from src.domain.memory.meta_memory import CrystallizationResult
from src.infrastructure.db.enums import EvidenceType, GapStatus

class TestCrystallizationConditions:
    @pytest.fixture
    def conditions(self):
        return CrystallizationConditions(observation_period_hours=24)
    
    @pytest.fixture
    def pending_gap(self):
        gap = MagicMock()
        gap.status = GapStatus.PENDING.value
        # 使用固定的过去时间，避免测试执行时间影响
        gap.discovered_at = datetime(2024, 1, 1, 0, 0, 0)
        gap.occurrence_count = 1
        return gap
    
    def test_observation_complete(self, conditions, pending_gap):
        # 使用固定的过去时间
        pending_gap.discovered_at = datetime(2023, 1, 1, 0, 0, 0)  # 很久以前，观察期已完成
        assert conditions._is_observation_complete(pending_gap) is True
        pending_gap.discovered_at = datetime.now() + timedelta(hours=1)  # 未来时间，观察期未完成
        assert conditions._is_observation_complete(pending_gap) is False
    
    def test_repeat_error_condition(self, conditions, pending_gap):
        evidences = [EvidenceType.INITIAL_DIAGNOSIS]
        result = conditions._check_repeat_error(pending_gap, evidences)
        assert result.can_crystallize is False
        
        pending_gap.occurrence_count = 2
        evidences = [EvidenceType.INITIAL_DIAGNOSIS, EvidenceType.REPEAT_ERROR]
        result = conditions._check_repeat_error(pending_gap, evidences)
        assert result.can_crystallize is True
    
    def test_variant_failure_condition(self, conditions, pending_gap):
        evidences = [EvidenceType.VARIANT_FAILED]
        result = conditions._check_variant_failure(pending_gap, evidences)
        assert result.can_crystallize is True
        assert result.confidence == 0.9
    
    def test_cross_homework_condition(self, conditions, pending_gap):
        pending_gap.occurrence_count = 2
        result = conditions._check_cross_homework(pending_gap)
        assert result.can_crystallize is False
        
        pending_gap.occurrence_count = 3
        result = conditions._check_cross_homework(pending_gap)
        assert result.can_crystallize is True
    
    def test_full_flow(self, conditions, pending_gap):
        pending_gap.status = GapStatus.CRYSTALLIZED.value
        result = conditions.check_crystallization(pending_gap, [])
        assert result.can_crystallize is False
        
        pending_gap.status = GapStatus.PENDING.value
        pending_gap.discovered_at = datetime.now() + timedelta(hours=1)  # 未来，观察期未完成
        result = conditions.check_crystallization(pending_gap, [])
        assert result.can_crystallize is False
        
        pending_gap.discovered_at = datetime(2023, 1, 1, 0, 0, 0)  # 很久以前，观察期已完成
        pending_gap.occurrence_count = 2
        evidences = [EvidenceType.INITIAL_DIAGNOSIS, EvidenceType.REPEAT_ERROR]
        result = conditions.check_crystallization(pending_gap, evidences)
        assert result.can_crystallize is True

class TestCrystallizationExecutor:
    @pytest.fixture
    def mock_repos(self):
        return AsyncMock(), AsyncMock(), AsyncMock()
    
    @pytest.fixture
    def executor(self, mock_repos):
        gap_repo, evidence_repo, profile_memory = mock_repos
        return CrystallizationExecutor(gap_repo, evidence_repo, profile_memory)
    
    @pytest.fixture
    def pending_gap(self):
        gap = MagicMock()
        gap.gap_id = "gap_001"
        gap.student_id = "student_001"
        gap.status = GapStatus.PENDING.value
        gap.discovered_at = datetime(2023, 1, 1, 0, 0, 0)  # 很久以前，观察期已完成
        gap.occurrence_count = 2
        gap.gap_type = "concept_gap"
        return gap
    
    @pytest.mark.asyncio
    async def test_crystallize_success(self, executor, mock_repos, pending_gap):
        gap_repo, evidence_repo, _ = mock_repos
        gap_repo.get_by_id.return_value = pending_gap
        evidence_repo.find_many.return_value = [MagicMock(evidence_type=EvidenceType.REPEAT_ERROR.value)]
        
        result = await executor.crystallize("gap_001")
        assert result is not None
        assert result.success is True
        assert result.new_status == GapStatus.CRYSTALLIZED.value

class TestCrystallizationScheduler:
    @pytest.fixture
    def scheduler(self):
        gap_repo = AsyncMock()
        evidence_repo = AsyncMock()
        return CrystallizationScheduler(gap_repo, evidence_repo)
    
    def test_execution_window(self, scheduler):
        test_time = datetime.now().replace(hour=2, minute=30)
        assert scheduler.is_in_execution_window(test_time) is True
        test_time = datetime.now().replace(hour=10, minute=0)
        assert scheduler.is_in_execution_window(test_time) is False

class TestMemoryCompaction:
    @pytest.fixture
    def compactor(self):
        homework_repo = AsyncMock()
        answer_repo = AsyncMock()
        trace_repo = AsyncMock()
        config = CompressionConfig(dry_run=True)
        return MemoryCompaction(homework_repo, answer_repo, trace_repo, config)
    
    def test_estimate_compression(self, compactor):
        before_date = datetime.now() - timedelta(days=30)
        ratios = compactor.estimate_compression_ratio(before_date)
        assert "episodic_estimate" in ratios
        assert 0 <= ratios["overall_estimate"] <= 1

class TestCrystallizationMonitor:
    @pytest.fixture
    def monitor(self):
        gap_repo = AsyncMock()
        evidence_repo = AsyncMock()
        return CrystallizationMonitor(gap_repo, evidence_repo)
    
    def test_alert_rule(self):
        rule = AlertRule("test", "metric", 0.5, "<", "warning", "test message")
        assert rule.check(0.3) is True
        assert rule.check(0.7) is False
        rule.operator = ">"
        assert rule.check(0.7) is True
