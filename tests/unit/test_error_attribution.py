"""错误归因测试."""
import pytest
import pytest_asyncio
from src.domain.engines.error_attribution import (
    ErrorAttributionEngine, ErrorAttributionResult, AttributionFactor
)
from src.domain.models.diagnosis import ErrorType


class TestErrorAttributionResult:
    """归因结果测试."""
    
    def test_result_creation(self):
        """测试结果创建."""
        result = ErrorAttributionResult(
            problem_id="p1",
            student_id="stu_1",
            primary_cause="计算错误",
            error_type=ErrorType.CALCULATION_ERROR,
            confidence=0.85,
        )
        assert result.problem_id == "p1"
        assert result.confidence == 0.85


class TestAttributionFactor:
    """归因因子测试."""
    
    def test_factor_creation(self):
        """测试因子创建."""
        factor = AttributionFactor(
            factor_type="knowledge_gap",
            description="知识缺口",
            weight=0.5,
        )
        assert factor.factor_type == "knowledge_gap"


class TestErrorAttributionEngine:
    """错误归因引擎测试."""
    
    @pytest.fixture
    def engine(self):
        return ErrorAttributionEngine(None)
    
    def test_engine_creation(self, engine):
        """测试引擎创建."""
        assert engine is not None


class TestHistoricalPattern:
    """历史模式测试."""
    
    @pytest.fixture
    def engine(self):
        return ErrorAttributionEngine(None)
    
    def test_engine_exists(self, engine):
        """测试引擎存在."""
        assert engine is not None
