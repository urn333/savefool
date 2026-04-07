"""错题识别测试."""
import pytest
import pytest_asyncio
from src.domain.engines.error_detection import (
    ErrorDetectionEngine, ErrorDetectionResult, ErrorLocation
)
from src.domain.models.diagnosis import Problem, ErrorType
from src.domain.models.arbitration import ArbitrationResult


class TestErrorLocation:
    """错误位置测试."""
    
    def test_location_creation(self):
        """测试位置创建."""
        loc = ErrorLocation(x=100.0, y=200.0, width=50.0, height=30.0)
        assert loc.x == 100.0
        assert loc.y == 200.0
    
    def test_location_defaults(self):
        """测试位置默认值."""
        loc = ErrorLocation()
        assert loc.line is None
        assert loc.column is None


class TestErrorDetectionResult:
    """错题识别结果测试."""
    
    def test_result_creation(self):
        """测试结果创建."""
        result = ErrorDetectionResult(
            problem_id="p1",
            is_wrong=True,
            error_type=ErrorType.CALCULATION_ERROR,
            student_answer="5",
            correct_answer="4",
        )
        assert result.problem_id == "p1"
        assert result.is_wrong is True


class TestErrorDetectionEngine:
    """错题检测引擎测试."""
    
    @pytest.fixture
    def engine(self):
        return ErrorDetectionEngine()
    
    @pytest.fixture
    def sample_problem(self):
        return Problem(
            id="p1",
            content="2+2=?",
            subject="math",
            difficulty=1,
            answer="4",
        )
    
    @pytest.mark.asyncio
    async def test_detect_wrong_answer(self, engine, sample_problem):
        """测试检测错误答案."""
        arbitration = ArbitrationResult(
            problem_id="p1",
            is_correct=False,
            error_type=ErrorType.CALCULATION_ERROR,
            confidence=0.85,
        )
        result = await engine.detect(
            problem=sample_problem,
            arbitration_result=arbitration,
        )
        assert isinstance(result, ErrorDetectionResult)
        assert result.is_wrong is True
    
    @pytest.mark.asyncio
    async def test_detect_correct_answer(self, engine, sample_problem):
        """测试检测正确答案."""
        arbitration = ArbitrationResult(
            problem_id="p1",
            is_correct=True,
            confidence=0.95,
        )
        result = await engine.detect(
            problem=sample_problem,
            arbitration_result=arbitration,
        )
        assert result.is_wrong is False
    
    @pytest.mark.asyncio
    async def test_detect_batch(self, engine):
        """测试批量检测."""
        problems = [
            Problem(id="p1", content="1+1=?", subject="math", difficulty=1, answer="2"),
            Problem(id="p2", content="2+2=?", subject="math", difficulty=1, answer="4"),
        ]
        arbitration_results = [
            ArbitrationResult(problem_id="p1", is_correct=True, confidence=0.95),
            ArbitrationResult(problem_id="p2", is_correct=False, 
                            error_type=ErrorType.CALCULATION_ERROR, confidence=0.85),
        ]
        
        results = await engine.detect_batch(problems, arbitration_results)
        assert len(results) == 2


class TestErrorLocationFeatures:
    """错误定位测试."""
    
    @pytest.fixture
    def engine(self):
        return ErrorDetectionEngine()
    
    @pytest.mark.asyncio
    async def test_locate_error(self, engine):
        """测试错误定位."""
        problem = Problem(id="p1", content="计算题", subject="math", difficulty=2, answer="10")
        location = await engine._locate_error(
            problem, "5", "10", ErrorType.CALCULATION_ERROR, None
        )
        assert isinstance(location, ErrorLocation)
    
    def test_has_calculation_features(self, engine):
        """测试计算特征检测."""
        result = engine._has_calculation_features("5", "10")
        assert isinstance(result, bool)
    
    def test_analyze_answer_difference(self, engine):
        """测试答案差异分析."""
        result = engine._analyze_answer_difference("5", "10")
        assert isinstance(result, dict)
