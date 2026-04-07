"""错题识别引擎测试."""

import pytest
from unittest.mock import MagicMock

from src.domain.engines.error_detection import (
    ErrorDetectionEngine,
    ErrorDetectionResult,
    ErrorLocation,
)
from src.domain.models.diagnosis import Problem, ErrorType, WrongProblem
from src.domain.models.arbitration import ArbitrationResult, ModelVote


@pytest.fixture
def detection_engine():
    """创建错题识别引擎."""
    return ErrorDetectionEngine()


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
def correct_arbitration_result():
    """创建正确仲裁结果."""
    return ArbitrationResult(
        problem_id="prob_123",
        is_correct=True,
        confidence=0.9,
        is_consensus=True,
        consensus_ratio=1.0,
        used_models=["model_a", "model_b", "model_c"],
    )


@pytest.fixture
def wrong_arbitration_result():
    """创建错误仲裁结果."""
    return ArbitrationResult(
        problem_id="prob_123",
        is_correct=False,
        error_type=ErrorType.CALCULATION_ERROR,
        confidence=0.85,
        is_consensus=True,
        consensus_ratio=1.0,
        model_votes={
            "model_a": ModelVote(
                model_id="model_a",
                is_correct=False,
                error_type=ErrorType.CALCULATION_ERROR,
                confidence=0.9,
                reason="计算错误",
            ),
        },
        used_models=["model_a", "model_b", "model_c"],
    )


class TestErrorDetectionEngine:
    """错题识别引擎测试类."""
    
    @pytest.mark.asyncio
    async def test_detect_correct_problem(
        self,
        detection_engine,
        sample_problem,
        correct_arbitration_result,
    ):
        """测试识别正确的题目."""
        result = await detection_engine.detect(
            problem=sample_problem,
            arbitration_result=correct_arbitration_result,
        )
        
        assert isinstance(result, ErrorDetectionResult)
        assert result.is_wrong is False
        assert result.problem_id == "prob_123"
    
    @pytest.mark.asyncio
    async def test_detect_wrong_problem(
        self,
        detection_engine,
        sample_problem,
        wrong_arbitration_result,
    ):
        """测试识别错题."""
        ocr_result = {
            "student_answer": "6",
            "position": {"x": 100, "y": 200},
        }
        
        result = await detection_engine.detect(
            problem=sample_problem,
            arbitration_result=wrong_arbitration_result,
            ocr_result=ocr_result,
        )
        
        assert isinstance(result, ErrorDetectionResult)
        assert result.is_wrong is True
        assert result.error_type == ErrorType.CALCULATION_ERROR
        assert result.student_answer == "6"
        assert result.correct_answer == "5"
    
    @pytest.mark.asyncio
    async def test_classify_error_type_calculation(
        self,
        detection_engine,
        sample_problem,
    ):
        """测试计算错误分类."""
        arbitration_result = ArbitrationResult(
            problem_id="prob_123",
            is_correct=False,
            error_type=None,
            confidence=0.8,
            model_votes={
                "model_a": ModelVote(
                    model_id="model_a",
                    is_correct=False,
                    confidence=0.8,
                    reason="计算错误，数字运算有误",
                ),
            },
            used_models=["model_a"],
        )
        
        error_type = await detection_engine._classify_error_type(
            sample_problem,
            arbitration_result,
            None,
        )
        
        assert error_type == ErrorType.CALCULATION_ERROR
    
    @pytest.mark.asyncio
    async def test_classify_error_type_concept(
        self,
        detection_engine,
        sample_problem,
    ):
        """测试概念错误分类."""
        arbitration_result = ArbitrationResult(
            problem_id="prob_123",
            is_correct=False,
            error_type=None,
            confidence=0.8,
            model_votes={
                "model_a": ModelVote(
                    model_id="model_a",
                    is_correct=False,
                    confidence=0.8,
                    reason="概念理解有误，混淆了相关概念",
                ),
            },
            used_models=["model_a"],
        )
        
        error_type = await detection_engine._classify_error_type(
            sample_problem,
            arbitration_result,
            None,
        )
        
        assert error_type == ErrorType.CONCEPT_MISUNDERSTANDING
    
    def test_analyze_answer_difference_same(self, detection_engine):
        """测试相同答案分析."""
        diff = detection_engine._analyze_answer_difference("5", "5")
        assert "相同" in diff["description"]
    
    def test_analyze_answer_difference_length(self, detection_engine):
        """测试长度不同答案分析."""
        # 使用非纯数字，避免触发计算错误检测
        diff = detection_engine._analyze_answer_difference("ab", "abc")
        assert "长度不同" in diff["description"]
    
    def test_analyze_answer_difference_calc(self, detection_engine):
        """测试数字计算差异分析."""
        diff = detection_engine._analyze_answer_difference("15", "16")
        assert "偏差" in diff["description"]
        assert diff.get("calc_diff") == 1
    
    def test_get_error_description(self, detection_engine):
        """测试错误描述获取."""
        assert "计算" in detection_engine._get_error_description(ErrorType.CALCULATION_ERROR)
        assert "概念" in detection_engine._get_error_description(ErrorType.CONCEPT_MISUNDERSTANDING)
        assert "逻辑" in detection_engine._get_error_description(ErrorType.LOGICAL_FLAW)
        assert "粗心" in detection_engine._get_error_description(ErrorType.CARELESS_MISTAKE)
        assert "知识" in detection_engine._get_error_description(ErrorType.KNOWLEDGE_GAP)
    
    def test_calculate_confidence(self, detection_engine):
        """测试置信度计算."""
        arbitration_result = MagicMock()
        arbitration_result.confidence = 0.7
        arbitration_result.is_consensus = True
        
        confidence = detection_engine._calculate_confidence(
            arbitration_result,
            ErrorType.CALCULATION_ERROR,
            ErrorLocation(x=100, y=200),
        )
        
        assert confidence > 0.7
        assert confidence <= 1.0
    
    def test_to_wrong_problem(self, detection_engine):
        """测试转换为WrongProblem."""
        detection_result = ErrorDetectionResult(
            problem_id="prob_123",
            is_wrong=True,
            error_type=ErrorType.CALCULATION_ERROR,
            student_answer="6",
            correct_answer="5",
            error_location=ErrorLocation(
                line=1,
                column=5,
                x=100,
                y=200,
                description="计算位置错误",
            ),
            confidence=0.85,
        )
        
        wrong_problem = detection_engine.to_wrong_problem(detection_result)
        
        assert isinstance(wrong_problem, WrongProblem)
        assert wrong_problem.problem_id == "prob_123"
        assert wrong_problem.error_type == ErrorType.CALCULATION_ERROR
        assert wrong_problem.student_answer == "6"
        assert wrong_problem.error_position["x"] == 100
    
    @pytest.mark.asyncio
    async def test_detect_batch(self, detection_engine):
        """测试批量检测."""
        problems = [
            Problem(id="p1", content="1+1=?", subject="math", difficulty=1, answer="2"),
            Problem(id="p2", content="2+2=?", subject="math", difficulty=1, answer="4"),
        ]
        
        arbitration_results = [
            ArbitrationResult(
                problem_id="p1",
                is_correct=True,
                confidence=0.9,
                used_models=["a"],
            ),
            ArbitrationResult(
                problem_id="p2",
                is_correct=False,
                error_type=ErrorType.CALCULATION_ERROR,
                confidence=0.8,
                used_models=["a"],
            ),
        ]
        
        results = await detection_engine.detect_batch(
            problems, arbitration_results
        )
        
        assert len(results) == 2
        assert results[0].is_wrong is False
        assert results[1].is_wrong is True
