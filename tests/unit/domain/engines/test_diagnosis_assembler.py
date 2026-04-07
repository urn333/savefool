"""诊断结果组装引擎测试."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from src.domain.engines.diagnosis_assembler import (
    DiagnosisAssembler,
    DiagnosisReport,
)
from src.domain.engines.error_detection import ErrorDetectionResult, ErrorLocation
from src.domain.engines.error_attribution import ErrorAttributionResult
from src.domain.engines.explanation_generator import ExplanationResult, ExplanationContent
from src.domain.engines.layered_diagnosis import DiagnosisPath
from src.domain.models.diagnosis import DiagnosisResult, DiagnosisStatus, Problem, ErrorType
from src.domain.memory.memory_manager import MemoryManager


@pytest.fixture
def mock_memory_manager():
    """创建模拟记忆管理器."""
    mm = MagicMock(spec=MemoryManager)
    mm.record_problem_attempt = AsyncMock(return_value={
        "episode_id": "ep_123",
        "status": "recorded",
    })
    return mm


@pytest.fixture
def assembler(mock_memory_manager):
    """创建诊断组装引擎."""
    return DiagnosisAssembler(mock_memory_manager)


@pytest.fixture
def sample_problem():
    """创建示例题目."""
    return Problem(
        id="prob_123",
        content="计算：2 + 3 = ?",
        subject="math",
        difficulty=3,
        answer="5",
        knowledge_points=["addition"],
    )


@pytest.fixture
def sample_detection_result():
    """创建示例错题识别结果."""
    return ErrorDetectionResult(
        problem_id="prob_123",
        is_wrong=True,
        error_type=ErrorType.CALCULATION_ERROR,
        student_answer="6",
        correct_answer="5",
        error_location=ErrorLocation(
            line=1,
            column=3,
            description="计算位置",
        ),
        confidence=0.85,
    )


@pytest.fixture
def sample_attribution_result():
    """创建示例归因结果."""
    return ErrorAttributionResult(
        problem_id="prob_123",
        student_id="stu_456",
        primary_cause="计算错误",
        secondary_causes=["方法不熟练"],
        error_type=ErrorType.CALCULATION_ERROR,
        confidence=0.8,
        knowledge_gaps=["加法运算"],
        is_careless_pattern=False,
        historical_similarity=0.2,
        factors=[],
        recommendations=["多做练习", "仔细验算"],
    )


@pytest.fixture
def sample_explanation_result():
    """创建示例讲解结果."""
    return ExplanationResult(
        problem_id="prob_123",
        student_id="stu_456",
        content=ExplanationContent(
            main_explanation="这道题的讲解",
            analogy="就像打游戏",
            step_hints=["第一步", "第二步"],
            key_points=["注意计算"],
            practice_suggestion="多做练习",
        ),
        safety_score=1.0,
        estimated_reading_time=30,
    )


class TestDiagnosisAssembler:
    """诊断组装引擎测试类."""
    
    @pytest.mark.asyncio
    async def test_assemble_basic(
        self,
        assembler,
        sample_problem,
        sample_detection_result,
        sample_attribution_result,
        sample_explanation_result,
    ):
        """测试基础组装."""
        result, report = await assembler.assemble(
            task_id="task_123",
            student_id="stu_456",
            problems=[sample_problem],
            detection_results=[sample_detection_result],
            attribution_results=[sample_attribution_result],
            explanation_results=[sample_explanation_result],
            diagnosis_paths=[None],
            processing_time=10.0,
        )
        
        assert isinstance(result, DiagnosisResult)
        assert isinstance(report, DiagnosisReport)
        
        assert result.task_id == "task_123"
        assert result.status == DiagnosisStatus.COMPLETED
        assert len(result.wrong_problems) == 1
        
        assert report.task_id == "task_123"
        assert report.student_id == "stu_456"
    
    @pytest.mark.asyncio
    async def test_assemble_no_wrong_problems(
        self,
        assembler,
        sample_problem,
    ):
        """测试无错题情况."""
        detection_result = ErrorDetectionResult(
            problem_id="prob_123",
            is_wrong=False,
            confidence=0.95,
        )
        
        result, report = await assembler.assemble(
            task_id="task_123",
            student_id="stu_456",
            problems=[sample_problem],
            detection_results=[detection_result],
            attribution_results=[],
            explanation_results=[],
            diagnosis_paths=[None],
            processing_time=5.0,
        )
        
        assert len(result.wrong_problems) == 0
        assert report.diagnosis_summary["wrong_count"] == 0
        assert report.diagnosis_summary["accuracy_rate"] == 1.0
    
    def test_build_wrong_problems(self, assembler, sample_problem, sample_detection_result):
        """测试构建错题列表."""
        wrong_problems = assembler._build_wrong_problems(
            [sample_detection_result],
            [],
        )
        
        assert len(wrong_problems) == 1
        assert wrong_problems[0].problem_id == "prob_123"
        assert wrong_problems[0].error_type == ErrorType.CALCULATION_ERROR
    
    def test_generate_diagnosis_summary(self, assembler, sample_problem):
        """测试生成诊断摘要."""
        from src.domain.models.diagnosis import WrongProblem
        
        wrong_problem = WrongProblem(
            problem_id="prob_123",
            error_type=ErrorType.CALCULATION_ERROR,
            root_cause="计算错误",
            concept_gap=["加法"],
            confidence=0.85,
        )
        
        attribution_result = MagicMock()
        attribution_result.problem_id = "prob_123"
        attribution_result.primary_cause = "计算错误"
        attribution_result.confidence = 0.8
        
        summary = assembler._generate_diagnosis_summary(
            [sample_problem],
            [wrong_problem],
            [attribution_result],
        )
        
        assert summary["total_problems"] == 1
        assert summary["wrong_count"] == 1
        assert summary["accuracy_rate"] == 0.0
        assert "calculation" in summary["error_type_distribution"]
    
    def test_assemble_explanations(self, assembler, sample_explanation_result):
        """测试组装讲解内容."""
        explanations = assembler._assemble_explanations([sample_explanation_result])
        
        assert len(explanations) == 1
        assert explanations[0]["problem_id"] == "prob_123"
        assert "main_explanation" in explanations[0]
        assert "analogy" in explanations[0]
    
    def test_generate_recommendations(self, assembler, sample_attribution_result):
        """测试生成建议."""
        recommendations = assembler._generate_recommendations(
            [sample_attribution_result],
            [None],
        )
        
        assert len(recommendations) > 0
        assert any("练习" in r for r in recommendations)
    
    def test_determine_next_steps(self, assembler):
        """测试确定下一步行动."""
        from src.domain.models.diagnosis import WrongProblem
        
        wrong_problem = WrongProblem(
            problem_id="prob_123",
            error_type=ErrorType.CALCULATION_ERROR,
            root_cause="计算错误",
            concept_gap=[],
            confidence=0.8,
        )
        
        steps = assembler._determine_next_steps(
            [wrong_problem],
            [],
            None,
        )
        
        assert len(steps) > 0
        assert any("错题" in s for s in steps)
    
    def test_calculate_statistics(self, assembler, sample_problem, sample_attribution_result):
        """测试计算统计信息."""
        from src.domain.models.diagnosis import WrongProblem
        
        wrong_problem = WrongProblem(
            problem_id="prob_123",
            error_type=ErrorType.CALCULATION_ERROR,
            root_cause="计算错误",
            concept_gap=[],
            confidence=0.8,
        )
        
        statistics = assembler._calculate_statistics(
            [sample_problem],
            [wrong_problem],
            [sample_attribution_result],
            10.5,
        )
        
        assert statistics["total_problems"] == 1
        assert statistics["wrong_count"] == 1
        assert statistics["processing_time_seconds"] == 10.5
        assert "average_attribution_confidence" in statistics
    
    def test_prepare_knowledge_update(self, assembler, sample_problem, sample_attribution_result):
        """测试准备知识图谱更新."""
        from src.domain.models.diagnosis import WrongProblem
        
        wrong_problem = WrongProblem(
            problem_id="prob_123",
            error_type=ErrorType.CALCULATION_ERROR,
            root_cause="计算错误",
            concept_gap=["加法运算"],
            confidence=0.8,
        )
        
        update = assembler._prepare_knowledge_update(
            "stu_456",
            [sample_problem],
            [wrong_problem],
            [sample_attribution_result],
        )
        
        assert update["student_id"] == "stu_456"
        assert "addition" in [u["concept_id"] for u in update["concept_updates"]]
        assert "加法运算" in update["weak_points_identified"]
    
    @pytest.mark.asyncio
    async def test_create_push_notification_all_correct(self, assembler):
        """测试全对推送通知."""
        report = DiagnosisReport(
            report_id="report_123",
            task_id="task_123",
            student_id="stu_456",
            created_at=MagicMock(),
            diagnosis_summary={
                "total_problems": 5,
                "wrong_count": 0,
            },
        )
        
        notification = await assembler.create_push_notification(report)
        
        assert "全对" in notification["title"] or "太棒" in notification["body"]
        assert notification["priority"] == "normal"
    
    @pytest.mark.asyncio
    async def test_create_push_notification_with_wrong(self, assembler):
        """测试有错题推送通知."""
        report = DiagnosisReport(
            report_id="report_123",
            task_id="task_123",
            student_id="stu_456",
            created_at=MagicMock(),
            diagnosis_summary={
                "total_problems": 5,
                "wrong_count": 2,
            },
        )
        
        notification = await assembler.create_push_notification(report)
        
        assert "2道" in notification["title"] or "错题" in notification["body"]
        assert notification["priority"] == "high"
