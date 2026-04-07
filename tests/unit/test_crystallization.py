"""24小时结晶机制单元测试.

测试范围:
- 结晶条件判定
- 结晶执行
- 数据压缩
- 调度器
- 监控

功能追溯ID: F-MEM-004, F-MEM-005, F-MEM-006
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.domain.memory.crystallization.conditions import (
    CrystallizationConditions,
    CrystallizationTrigger,
)
from src.domain.memory.crystallization.executor import (
    CrystallizationExecutor,
    CrystallizationRecord,
)
from src.domain.memory.crystallization.scheduler import CrystallizationScheduler
from src.domain.memory.crystallization.compaction import (
    MemoryCompaction,
    EpisodicCompression,
    ImageArchiveRecord,
)
from src.domain.memory.crystallization.monitor import (
    CrystallizationMonitor,
    CrystallizationAlert,
    AlertLevel,
)
from src.infrastructure.db.enums import EvidenceType, GapStatus


# ============== Fixtures ==============

@pytest.fixture
def conditions():
    """结晶条件判定器."""
    return CrystallizationConditions()


@pytest.fixture
def executor():
    """结晶执行器."""
    return CrystallizationExecutor()


@pytest.fixture
def scheduler():
    """结晶调度器."""
    return CrystallizationScheduler()


@pytest.fixture
def compaction():
    """记忆压缩器."""
    return MemoryCompaction()


@pytest.fixture
def monitor():
    """结晶监控器."""
    return CrystallizationMonitor()


@pytest.fixture
def sample_gap_data():
    """示例缺口数据."""
    return {
        "gap_id": "gap_001",
        "student_id": "stu_001",
        "gap_type": "concept_gap",
        "status": "pending",
        "discovered_at": (datetime.now() - timedelta(hours=25)).isoformat(),
        "occurrence_count": 2,
        "related_knowledge": ["k_001", "k_002"],
    }


@pytest.fixture
def sample_evidences():
    """示例证据列表."""
    base_time = datetime.now() - timedelta(hours=25)
    return [
        {
            "evidence_id": "ev_001",
            "gap_id": "gap_001",
            "evidence_type": EvidenceType.INITIAL_DIAGNOSIS.value,
            "recorded_at": base_time.isoformat(),
            "diagnosis_id": "diag_001",
        },
        {
            "evidence_id": "ev_002",
            "gap_id": "gap_001",
            "evidence_type": EvidenceType.REPEAT_ERROR.value,
            "recorded_at": (base_time + timedelta(hours=2)).isoformat(),
            "diagnosis_id": "diag_002",
            "homework_id": "hw_002",
        },
    ]


# ============== 结晶条件判定测试 ==============

class TestCrystallizationConditions:
    """结晶条件判定测试类."""
    
    def test_repeat_error_24h_triggered(self, conditions, sample_gap_data):
        """测试24小时内重复错误触发结晶."""
        # Given: 24小时内的重复错误证据
        current_time = datetime.now()
        evidences = [
            {
                "evidence_id": "ev_001",
                "evidence_type": EvidenceType.INITIAL_DIAGNOSIS.value,
                "recorded_at": (current_time - timedelta(hours=20)).isoformat(),
            },
            {
                "evidence_id": "ev_002",
                "evidence_type": EvidenceType.REPEAT_ERROR.value,
                "recorded_at": (current_time - timedelta(hours=2)).isoformat(),
            },
        ]
        
        # When: 检查条件
        result = conditions.check_all_conditions(sample_gap_data, evidences, current_time)
        
        # Then: 应该触发结晶
        assert result["should_crystallize"] is True
        assert result["conditions"]["repeat_error_24h"] is True
        assert CrystallizationTrigger.REPEAT_ERROR_24H.value in result["triggered"]
    
    def test_repeat_error_outside_24h_not_triggered(self, conditions, sample_gap_data):
        """测试24小时外的重复错误不触发结晶."""
        # Given: 24小时外的重复错误证据
        current_time = datetime.now()
        evidences = [
            {
                "evidence_id": "ev_001",
                "evidence_type": EvidenceType.REPEAT_ERROR.value,
                "recorded_at": (current_time - timedelta(hours=30)).isoformat(),
            },
        ]
        
        # When: 检查条件
        result = conditions.check_all_conditions(sample_gap_data, evidences, current_time)
        
        # Then: 不应该因重复错误触发
        assert result["conditions"]["repeat_error_24h"] is False
    
    def test_variant_failed_triggered(self, conditions, sample_gap_data):
        """测试变形题失败触发结晶."""
        # Given: 变形题失败证据
        evidences = [
            {
                "evidence_id": "ev_001",
                "evidence_type": EvidenceType.VARIANT_FAILED.value,
                "recorded_at": datetime.now().isoformat(),
            },
        ]
        
        # When: 检查条件
        result = conditions.check_all_conditions(sample_gap_data, evidences)
        
        # Then: 应该触发结晶
        assert result["should_crystallize"] is True
        assert result["conditions"]["variant_failed"] is True
        assert CrystallizationTrigger.VARIANT_FAILED.value in result["triggered"]
    
    def test_cross_homework_3_triggered(self, conditions, sample_gap_data):
        """测试跨3次作业触发结晶."""
        # Given: 跨3次作业的证据
        evidences = [
            {
                "evidence_id": "ev_001",
                "evidence_type": EvidenceType.CROSS_HOMEWORK.value,
                "homework_id": "hw_001",
            },
            {
                "evidence_id": "ev_002",
                "evidence_type": EvidenceType.CROSS_HOMEWORK.value,
                "homework_id": "hw_002",
            },
            {
                "evidence_id": "ev_003",
                "evidence_type": EvidenceType.CROSS_HOMEWORK.value,
                "homework_id": "hw_003",
            },
        ]
        
        # When: 检查条件
        result = conditions.check_all_conditions(sample_gap_data, evidences)
        
        # Then: 应该触发结晶
        assert result["should_crystallize"] is True
        assert result["conditions"]["cross_homework_3"] is True
    
    def test_cross_homework_2_not_triggered(self, conditions, sample_gap_data):
        """测试跨2次作业不触发结晶."""
        # Given: 仅跨2次作业的证据
        evidences = [
            {
                "evidence_id": "ev_001",
                "evidence_type": EvidenceType.CROSS_HOMEWORK.value,
                "homework_id": "hw_001",
            },
            {
                "evidence_id": "ev_002",
                "evidence_type": EvidenceType.CROSS_HOMEWORK.value,
                "homework_id": "hw_002",
            },
        ]
        
        # When: 检查条件
        result = conditions.check_all_conditions(sample_gap_data, evidences)
        
        # Then: 不应该触发
        assert result["conditions"]["cross_homework_3"] is False
    
    def test_observation_expired_dismissed(self, conditions, sample_gap_data):
        """测试观察期满无证据触发排除."""
        # Given: 观察期满但无新证据
        current_time = datetime.now()
        gap_data = {
            **sample_gap_data,
            "discovered_at": (current_time - timedelta(hours=25)).isoformat(),
        }
        evidences = [
            {
                "evidence_id": "ev_001",
                "evidence_type": EvidenceType.INITIAL_DIAGNOSIS.value,
                "recorded_at": (current_time - timedelta(hours=25)).isoformat(),
            },
        ]
        
        # When: 检查条件
        result = conditions.check_all_conditions(gap_data, evidences, current_time)
        
        # Then: 应该触发排除
        assert result["should_dismiss"] is True
        assert result["conditions"]["observation_expired"] is True
    
    def test_with_new_evidence_not_dismissed(self, conditions, sample_gap_data):
        """测试有新证据时不触发排除."""
        # Given: 观察期内有新证据
        current_time = datetime.now()
        gap_data = {
            **sample_gap_data,
            "discovered_at": (current_time - timedelta(hours=25)).isoformat(),
        }
        evidences = [
            {
                "evidence_id": "ev_001",
                "evidence_type": EvidenceType.INITIAL_DIAGNOSIS.value,
                "recorded_at": (current_time - timedelta(hours=25)).isoformat(),
            },
            {
                "evidence_id": "ev_002",
                "evidence_type": EvidenceType.REPEAT_ERROR.value,
                "recorded_at": (current_time - timedelta(hours=2)).isoformat(),
            },
        ]
        
        # When: 检查条件
        result = conditions.check_all_conditions(gap_data, evidences, current_time)
        
        # Then: 不应该触发排除，而应该触发结晶
        assert result["should_dismiss"] is False
        assert result["should_crystallize"] is True
    
    def test_condition_summary(self, conditions):
        """测试条件配置摘要."""
        # When: 获取配置摘要
        summary = conditions.get_condition_summary()
        
        # Then: 应该包含所有阈值
        assert "repeat_error_hours" in summary
        assert "cross_homework_threshold" in summary
        assert "observation_period_hours" in summary
        assert summary["cross_homework_threshold"] == 3


# ============== 结晶执行测试 ==============

class TestCrystallizationExecutor:
    """结晶执行器测试类."""
    
    @pytest.mark.asyncio
    async def test_execute_crystallization(self, executor, sample_gap_data, sample_evidences):
        """测试执行结晶."""
        # Given: 满足结晶条件的缺口
        
        # When: 执行结晶
        record = await executor.execute(sample_gap_data, sample_evidences)
        
        # Then: 状态应该变为crystallized
        assert record.new_status == GapStatus.CRYSTALLIZED.value
        assert record.old_status == GapStatus.PENDING.value
        assert record.gap_id == sample_gap_data["gap_id"]
        assert len(record.evidence_chain) == len(sample_evidences)
    
    @pytest.mark.asyncio
    async def test_execute_dismiss(self, executor):
        """测试执行排除."""
        # Given: 观察期满无证据的缺口
        current_time = datetime.now()
        gap_data = {
            "gap_id": "gap_002",
            "student_id": "stu_001",
            "gap_type": "concept_gap",
            "status": "pending",
            "discovered_at": (current_time - timedelta(hours=25)).isoformat(),
        }
        evidences = [
            {
                "evidence_id": "ev_001",
                "evidence_type": EvidenceType.INITIAL_DIAGNOSIS.value,
                "recorded_at": (current_time - timedelta(hours=25)).isoformat(),
            },
        ]
        
        # When: 执行
        record = await executor.execute(gap_data, evidences)
        
        # Then: 状态应该变为dismissed
        assert record.new_status == GapStatus.DISMISSED.value
    
    @pytest.mark.asyncio
    async def test_execute_force(self, executor, sample_gap_data, sample_evidences):
        """测试强制结晶."""
        # Given: 不满足条件的缺口
        gap_data = {
            **sample_gap_data,
            "discovered_at": datetime.now().isoformat(),  # 刚发现
        }
        
        # When: 强制执行结晶
        record = await executor.execute(gap_data, sample_evidences, force=True)
        
        # Then: 应该强制结晶
        assert record.new_status == GapStatus.CRYSTALLIZED.value
        assert "forced" in record.triggered_conditions
    
    @pytest.mark.asyncio
    async def test_profile_update_on_crystallization(
        self, executor, sample_gap_data, sample_evidences
    ):
        """测试结晶时Profile更新."""
        # Given: 画像数据
        profile_data = {
            "student_id": "stu_001",
            "error_dna": {
                "error_patterns": [],
            },
            "zpd_boundary": {
                "independent_level": 0.6,
            },
        }
        
        # When: 执行结晶
        record = await executor.execute(
            sample_gap_data, sample_evidences, profile_data
        )
        
        # Then: Profile应该被更新
        assert len(record.profile_updates) > 0
        assert "error_dna.error_patterns" in record.profile_updates
    
    def test_validate_evidence_chain_valid(self, executor, sample_gap_data, sample_evidences):
        """测试有效证据链验证."""
        # When: 验证证据链
        validation = executor.validate_evidence_chain(sample_gap_data, sample_evidences)
        
        # Then: 应该有效
        assert validation["is_valid"] is True
        assert validation["stats"]["initial_diagnosis"] == 1
        assert validation["stats"]["repeat_errors"] == 1
    
    def test_validate_evidence_chain_missing_initial(self, executor, sample_gap_data):
        """测试缺少初始诊断证据."""
        # Given: 没有初始诊断的证据
        evidences = [
            {
                "evidence_id": "ev_001",
                "evidence_type": EvidenceType.REPEAT_ERROR.value,
            },
        ]
        
        # When: 验证证据链
        validation = executor.validate_evidence_chain(sample_gap_data, evidences)
        
        # Then: 应该无效
        assert validation["is_valid"] is False
        assert any("Missing initial" in e for e in validation["errors"])
    
    def test_get_execution_history(self, executor, sample_gap_data, sample_evidences):
        """测试获取执行历史."""
        # Given: 已有执行记录
        asyncio.run(executor.execute(sample_gap_data, sample_evidences))
        
        # When: 获取历史
        history = executor.get_execution_history()
        
        # Then: 应该返回记录
        assert len(history) >= 1
    
    def test_get_execution_summary(self, executor, sample_gap_data, sample_evidences):
        """测试获取执行摘要."""
        # Given: 已有执行记录
        asyncio.run(executor.execute(sample_gap_data, sample_evidences))
        
        # When: 获取摘要
        summary = executor.get_execution_summary()
        
        # Then: 应该包含统计数据
        assert "total_executions" in summary
        assert "crystallized" in summary
        assert "success_rate" in summary


# ============== 数据压缩测试 ==============

class TestMemoryCompaction:
    """记忆压缩测试类."""
    
    def test_compress_episodic_records(self, compaction):
        """测试Episodic记录压缩."""
        # Given: 多条Episodic记录
        student_id = "stu_001"
        old_time = datetime.now() - timedelta(days=10)
        records = [
            {
                "record_id": "rec_001",
                "timestamp": old_time.isoformat(),
                "knowledge_tags": ["math"],
                "error_type": "concept_gap",
                "is_correct": False,
            },
            {
                "record_id": "rec_002",
                "timestamp": (old_time + timedelta(days=1)).isoformat(),
                "knowledge_tags": ["math"],
                "error_type": "concept_gap",
                "is_correct": True,
            },
            {
                "record_id": "rec_003",
                "timestamp": (old_time + timedelta(days=2)).isoformat(),
                "knowledge_tags": ["english"],
                "error_type": "reading_error",
                "is_correct": False,
            },
        ]
        
        # When: 压缩
        result = compaction.compress_episodic_records(student_id, records)
        
        # Then: 应该生成压缩结果
        assert isinstance(result, EpisodicCompression)
        assert result.student_id == student_id
        assert result.compression_ratio >= 0
        assert result.original_count == 3
        assert "clusters" in result.compressed_data
    
    def test_archive_images(self, compaction):
        """测试图片归档."""
        # Given: 旧图片
        old_time = datetime.now() - timedelta(days=35)
        images = [
            {
                "image_id": "img_001",
                "url": "http://example.com/1.jpg",
                "uploaded_at": old_time.isoformat(),
            },
            {
                "image_id": "img_002",
                "url": "http://example.com/2.jpg",
                "uploaded_at": datetime.now().isoformat(),
            },
        ]
        
        # When: 归档
        archived = compaction.archive_images(images)
        
        # Then: 只有旧图片被归档
        assert len(archived) == 1
        assert archived[0].image_id == "img_001"
        assert archived[0].archive_url.startswith("archive://")
    
    def test_get_archive_stats(self, compaction):
        """测试归档统计."""
        # When: 获取统计
        stats = compaction.get_archive_stats()
        
        # Then: 应该包含统计信息
        assert "total_archived" in stats
        assert "total_compressed" in stats
        assert "avg_compression_ratio" in stats


# ============== 调度器测试 ==============

class TestCrystallizationScheduler:
    """结晶调度器测试类."""
    
    @pytest.mark.asyncio
    async def test_run_once(self, scheduler):
        """测试单次执行."""
        # Given: 模拟缺口数据提供函数
        def gap_provider():
            return [
                {
                    "gap_id": "gap_001",
                    "student_id": "stu_001",
                    "status": "pending",
                    "discovered_at": (datetime.now() - timedelta(hours=25)).isoformat(),
                    "evidences": [
                        {
                            "evidence_id": "ev_001",
                            "evidence_type": EvidenceType.INITIAL_DIAGNOSIS.value,
                            "recorded_at": (datetime.now() - timedelta(hours=25)).isoformat(),
                        },
                    ],
                },
            ]
        
        # When: 执行一次
        result = await scheduler.run_once(gap_provider)
        
        # Then: 应该返回结果
        assert "execution_id" in result
        assert "timestamp" in result
        assert result["gaps_processed"] == 1
    
    def test_get_status(self, scheduler):
        """测试获取调度器状态."""
        # When: 获取状态
        status = scheduler.get_status()
        
        # Then: 应该包含状态信息
        assert "is_running" in status
        assert "interval_minutes" in status
        assert "execution_count" in status
        assert status["is_running"] is False
    
    def test_is_due(self, scheduler):
        """测试检查是否应该处理."""
        # Given: 已过期和未过期的缺口
        old_gap = {
            "gap_id": "gap_001",
            "status": "pending",
            "discovered_at": (datetime.now() - timedelta(hours=25)).isoformat(),
        }
        new_gap = {
            "gap_id": "gap_002",
            "status": "pending",
            "discovered_at": datetime.now().isoformat(),
        }
        crystallized_gap = {
            "gap_id": "gap_003",
            "status": "crystallized",
            "discovered_at": (datetime.now() - timedelta(hours=25)).isoformat(),
        }
        
        # When & Then
        assert scheduler.is_due(old_gap) is True
        assert scheduler.is_due(new_gap) is False
        assert scheduler.is_due(crystallized_gap) is False
    
    def test_callback(self, scheduler):
        """测试回调函数."""
        # Given: 回调函数
        received = []
        def callback(data):
            received.append(data)
        
        scheduler.set_callback(callback)
        
        # When: 执行
        asyncio.run(scheduler.run_once(lambda: []))
        
        # Then: 回调应该被调用
        assert len(received) == 1
        assert received[0]["type"] == "execution_complete"


# ============== 监控测试 ==============

class TestCrystallizationMonitor:
    """结晶监控器测试类."""
    
    def test_record_execution(self, monitor):
        """测试记录执行."""
        # Given: 执行结果
        result = {
            "gaps_processed": 5,
            "success": True,
        }
        
        # When: 记录
        monitor.record_execution(result)
        
        # Then: 应该被记录
        metrics = monitor.get_metrics(hours=1)
        assert metrics["total_executions"] == 1
        assert metrics["successful_executions"] == 1
    
    def test_alert_on_failure(self, monitor):
        """测试失败时生成告警."""
        # Given: 失败的执行结果
        result = {
            "gaps_processed": 0,
            "success": False,
            "error": "Database connection failed",
        }
        
        # When: 记录
        monitor.record_execution(result)
        
        # Then: 应该生成告警
        alerts = monitor.get_alerts(level=AlertLevel.ERROR)
        assert len(alerts) >= 1
    
    def test_alert_on_long_pending(self, monitor):
        """测试长期pending时生成告警."""
        # Given: 有长期pending缺口的执行结果
        result = {
            "gaps_processed": 1,
            "success": True,
            "gaps": [
                {
                    "gap_id": "gap_001",
                    "student_id": "stu_001",
                    "pending_hours": 50,
                },
            ],
        }
        
        # When: 记录
        monitor.record_execution(result)
        
        # Then: 应该生成警告
        alerts = monitor.get_alerts(level=AlertLevel.WARNING)
        assert len(alerts) >= 1
        assert any("gap_001" in a.message for a in alerts)
    
    def test_get_health_status(self, monitor):
        """测试获取健康状态."""
        # Given: 一些执行记录
        for _ in range(5):
            monitor.record_execution({"gaps_processed": 3, "success": True})
        
        # When: 获取健康状态
        health = monitor.get_health_status()
        
        # Then: 应该返回健康状态
        assert "status" in health
        assert health["status"] in ["healthy", "warning", "critical"]
        assert "success_rate_24h" in health
    
    def test_acknowledge_alert(self, monitor):
        """测试确认告警."""
        # Given: 一个告警
        result = {"gaps_processed": 0, "success": False, "error": "test"}
        monitor.record_execution(result)
        
        alert = monitor.get_alerts()[0]
        
        # When: 确认
        success = monitor.acknowledge_alert(alert.alert_id)
        
        # Then: 应该被确认
        assert success is True
        assert alert.acknowledged is True
        
        # 未确认的应该为空
        unack = monitor.get_alerts(unacknowledged_only=True)
        assert len(unack) == 0
    
    def test_add_alert_handler(self, monitor):
        """测试添加告警处理器."""
        # Given: 处理器
        received = []
        def handler(alert):
            received.append(alert)
        
        monitor.add_alert_handler(handler)
        
        # When: 触发告警
        result = {"gaps_processed": 0, "success": False, "error": "test"}
        monitor.record_execution(result)
        
        # Then: 处理器应该被调用
        assert len(received) >= 1
