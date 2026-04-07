"""诊断流程引擎测试."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from src.domain.engines.diagnosis_engine import (
    DiagnosisEngine,
    DiagnosisConfig,
    DiagnosisProgress,
)
from src.domain.engines.ocr_engine import OCREngine, OCRResult
from src.domain.engines.arbitration_engine import ArbitrationEngine
from src.domain.engines.model_schedulers import (
    ModelAScheduler,
    ModelBScheduler,
    ModelCScheduler,
)
from src.domain.models.diagnosis import DiagnosisResult, DiagnosisStatus
from src.domain.memory.memory_manager import MemoryManager


@pytest.fixture
def mock_ocr_engine():
    """创建模拟OCR引擎."""
    engine = MagicMock(spec=OCREngine)
    engine.recognize = AsyncMock(return_value=OCRResult(
        success=True,
        content="计算：2 + 3 = ?",
        student_answer="6",
        subject="math",
        problem_type="calculation",
        knowledge_points=["addition"],
        confidence=0.9,
    ))
    return engine


@pytest.fixture
def mock_arbitration_engine():
    """创建模拟仲裁引擎."""
    engine = MagicMock(spec=ArbitrationEngine)
    
    from src.domain.models.arbitration import ArbitrationResult
    from src.domain.models.diagnosis import ErrorType
    
    engine.arbitrate = MagicMock(return_value=ArbitrationResult(
        problem_id="prob_123",
        is_correct=False,
        error_type=ErrorType.CALCULATION_ERROR,
        confidence=0.85,
        is_consensus=True,
        consensus_ratio=1.0,
        used_models=["model_a", "model_b", "model_c"],
    ))
    
    engine.should_trigger_variant = MagicMock(return_value=False)
    
    return engine


@pytest.fixture
def mock_memory_manager():
    """创建模拟记忆管理器."""
    mm = MagicMock(spec=MemoryManager)
    mm.get_snapshot = AsyncMock(return_value=MagicMock(
        recent_episodes=[],
        knowledge_graph=None,
        pending_gaps=[],
        profile=None,
    ))
    mm.record_problem_attempt = AsyncMock(return_value={
        "episode_id": "ep_123",
        "status": "recorded",
    })
    return mm


@pytest.fixture
def mock_model_schedulers():
    """创建模拟模型调度器."""
    scheduler_a = MagicMock(spec=ModelAScheduler)
    scheduler_a.config = MagicMock(model_id="model_a")
    scheduler_a.schedule = AsyncMock()
    
    scheduler_b = MagicMock(spec=ModelBScheduler)
    scheduler_b.config = MagicMock(model_id="model_b")
    scheduler_b.schedule = AsyncMock()
    
    scheduler_c = MagicMock(spec=ModelCScheduler)
    scheduler_c.config = MagicMock(model_id="model_c")
    scheduler_c.schedule = AsyncMock()
    
    return scheduler_a, scheduler_b, scheduler_c


@pytest.fixture
def diagnosis_engine(
    mock_ocr_engine,
    mock_arbitration_engine,
    mock_memory_manager,
    mock_model_schedulers,
):
    """创建诊断引擎."""
    scheduler_a, scheduler_b, scheduler_c = mock_model_schedulers
    
    return DiagnosisEngine(
        ocr_engine=mock_ocr_engine,
        arbitration_engine=mock_arbitration_engine,
        memory_manager=mock_memory_manager,
        model_a_scheduler=scheduler_a,
        model_b_scheduler=scheduler_b,
        model_c_scheduler=scheduler_c,
        config=DiagnosisConfig(
            total_timeout=60.0,
            ocr_timeout=5.0,
            arbitration_timeout=10.0,
            enable_variant=False,  # 测试中禁用变形题
            enable_layered_diagnosis=True,
        ),
    )


class TestDiagnosisEngine:
    """诊断流程引擎测试类."""
    
    @pytest.mark.asyncio
    async def test_diagnose_basic(self, diagnosis_engine, tmp_path):
        """测试基础诊断流程."""
        # 创建临时图片文件
        image_path = tmp_path / "test_homework.jpg"
        image_path.write_bytes(b"fake_image_data")
        
        result, report = await diagnosis_engine.diagnose(
            homework_image=str(image_path),
            student_id="stu_123",
            subject_hint="math",
        )
        
        assert isinstance(result, DiagnosisResult)
        from src.domain.engines.diagnosis_assembler import DiagnosisReport
        assert isinstance(report, DiagnosisReport)
        
        assert result.task_id is not None
        assert result.status == DiagnosisStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_diagnose_timeout(self, diagnosis_engine, tmp_path):
        """测试诊断超时."""
        # 创建临时图片文件
        image_path = tmp_path / "test_homework.jpg"
        image_path.write_bytes(b"fake_image_data")
        
        # 设置一个很短的超时
        diagnosis_engine.config.total_timeout = 0.001
        
        # 模拟OCR延迟
        async def slow_ocr(*args, **kwargs):
            await asyncio.sleep(1)
            return OCRResult(success=True, content="test")
        
        diagnosis_engine.ocr_engine.recognize = slow_ocr
        
        result, report = await diagnosis_engine.diagnose(
            homework_image=str(image_path),
            student_id="stu_123",
        )
        
        assert result.status == DiagnosisStatus.TIMEOUT
        assert result.error is not None
    
    @pytest.mark.asyncio
    async def test_step_ocr(self, diagnosis_engine, tmp_path):
        """测试OCR步骤."""
        image_path = tmp_path / "test.jpg"
        image_path.write_bytes(b"fake")
        
        ocr_result = await diagnosis_engine._step_ocr(
            str(image_path),
            "math",
            0.0,
        )
        
        assert ocr_result.success is True
        assert ocr_result.content is not None
        diagnosis_engine.ocr_engine.recognize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_step_ocr_timeout(self, diagnosis_engine, tmp_path):
        """测试OCR超时."""
        image_path = tmp_path / "test.jpg"
        image_path.write_bytes(b"fake")
        
        async def slow_ocr(*args, **kwargs):
            await asyncio.sleep(10)
            return OCRResult(success=True, content="test")
        
        diagnosis_engine.ocr_engine.recognize = slow_ocr
        diagnosis_engine.config.ocr_timeout = 0.01
        
        ocr_result = await diagnosis_engine._step_ocr(
            str(image_path),
            "math",
            0.0,
        )
        
        # 超时时应该返回降级结果
        assert ocr_result.success is True
    
    def test_create_problem_from_ocr(self, diagnosis_engine):
        """测试从OCR结果创建题目."""
        ocr_result = OCRResult(
            success=True,
            content="计算：1+1=?",
            subject="math",
            knowledge_points=["addition"],
        )
        
        problem = diagnosis_engine._create_problem_from_ocr(ocr_result, "task_123")
        
        assert problem.content == "计算：1+1=?"
        assert problem.subject == "math"
        assert problem.knowledge_points == ["addition"]
    
    def test_log_progress(self, diagnosis_engine):
        """测试进度记录."""
        # 应该不会抛出异常
        diagnosis_engine._log_progress("test_stage", 50, 0.0)
    
    def test_create_timeout_result(self, diagnosis_engine):
        """测试创建超时结果."""
        result, report = diagnosis_engine._create_timeout_result("task_123", 90.0)
        
        assert result.status == DiagnosisStatus.TIMEOUT
        assert result.error["type"] == "timeout"
        assert report.diagnosis_summary["status"] == "timeout"
    
    def test_create_error_result(self, diagnosis_engine):
        """测试创建错误结果."""
        result, report = diagnosis_engine._create_error_result("task_123", 10.0, "测试错误")
        
        assert result.status == DiagnosisStatus.FAILED
        assert result.error["type"] == "exception"
        assert "测试错误" in result.error["message"]
    
    @pytest.mark.asyncio
    async def test_diagnose_config(self, diagnosis_engine):
        """测试诊断配置."""
        config = diagnosis_engine.config
        
        assert config.total_timeout == 60.0
        assert config.ocr_timeout == 5.0
        assert config.enable_variant is False
        assert config.enable_layered_diagnosis is True
    
    @pytest.mark.asyncio
    async def test_step_error_detection(self, diagnosis_engine):
        """测试错题识别步骤."""
        from src.domain.models.diagnosis import Problem
        from src.domain.models.arbitration import ArbitrationResult
        
        problem = Problem(
            id="prob_123",
            content="1+1=?",
            subject="math",
            difficulty=1,
        )
        
        arbitration_result = ArbitrationResult(
            problem_id="prob_123",
            is_correct=False,
            confidence=0.8,
        )
        
        ocr_result = OCRResult(
            success=True,
            content="1+1=?",
            student_answer="3",
        )
        
        detection_result = await diagnosis_engine._step_error_detection(
            problem,
            arbitration_result,
            ocr_result,
            0.0,
        )
        
        assert detection_result.is_wrong is True
        assert detection_result.problem_id == "prob_123"
    
    @pytest.mark.asyncio
    async def test_step_error_attribution(self, diagnosis_engine):
        """测试错误归因步骤."""
        from src.domain.models.diagnosis import Problem
        from src.domain.engines.error_detection import ErrorDetectionResult, ErrorLocation
        from src.domain.models.diagnosis import ErrorType
        
        problem = Problem(
            id="prob_123",
            content="1+1=?",
            subject="math",
            difficulty=1,
            knowledge_points=["addition"],
        )
        
        detection_result = ErrorDetectionResult(
            problem_id="prob_123",
            is_wrong=True,
            error_type=ErrorType.CALCULATION_ERROR,
            confidence=0.85,
        )
        
        attribution_result = await diagnosis_engine._step_error_attribution(
            "stu_123",
            problem,
            detection_result,
            0.0,
        )
        
        assert attribution_result.student_id == "stu_123"
        assert attribution_result.problem_id == "prob_123"
        assert attribution_result.error_type == ErrorType.CALCULATION_ERROR
