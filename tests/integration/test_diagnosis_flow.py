"""诊断流程集成测试."""
import pytest
import pytest_asyncio
from src.domain.engines.arbitration_engine import ArbitrationEngine, ArbitrationConfig
from src.domain.engines.error_detection import ErrorDetectionEngine
from src.domain.models.diagnosis import Problem, ErrorType
from src.domain.models.arbitration import ModelResult, ArbitrationResult


class TestArbitrationToDetectionFlow:
    """仲裁到检测流程测试."""
    
    @pytest.fixture
    def arbitration_engine(self):
        return ArbitrationEngine(ArbitrationConfig())
    
    @pytest.fixture
    def detection_engine(self):
        return ErrorDetectionEngine()
    
    @pytest.fixture
    def sample_problem(self):
        return Problem(
            id="prob_001",
            content="解方程: 3x + 7 = 22",
            subject="math",
            difficulty=3,
            answer="5",
        )
    
    def test_consensus_scenario(self, arbitration_engine):
        """测试共识场景."""
        model_results = [
            ModelResult(model_id="m1", is_correct=False,
                       error_type=ErrorType.CALCULATION_ERROR, confidence=0.9),
            ModelResult(model_id="m2", is_correct=False,
                       error_type=ErrorType.CALCULATION_ERROR, confidence=0.88),
            ModelResult(model_id="m3", is_correct=False,
                       error_type=ErrorType.CALCULATION_ERROR, confidence=0.85),
        ]
        result = arbitration_engine.arbitrate(problem_id="p1", model_results=model_results)
        assert result.is_consensus is True
    
    @pytest.mark.asyncio
    async def test_detection_after_arbitration(self, arbitration_engine, detection_engine, sample_problem):
        """测试仲裁后检测."""
        arbitration = ArbitrationResult(
            problem_id="p1",
            is_correct=False,
            error_type=ErrorType.CALCULATION_ERROR,
            confidence=0.85,
        )
        result = await detection_engine.detect(sample_problem, arbitration)
        assert result.is_wrong is True


class TestMultiModelIntegration:
    """多模型集成测试."""
    
    def test_model_consensus(self):
        """测试模型共识."""
        engine = ArbitrationEngine(ArbitrationConfig())
        results = [
            ModelResult(model_id="a", is_correct=False, error_type=ErrorType.CALCULATION_ERROR, confidence=0.9),
            ModelResult(model_id="b", is_correct=False, error_type=ErrorType.CALCULATION_ERROR, confidence=0.9),
            ModelResult(model_id="c", is_correct=False, error_type=ErrorType.CALCULATION_ERROR, confidence=0.9),
        ]
        arbitration = engine.arbitrate("p1", results)
        assert arbitration.is_consensus is True
