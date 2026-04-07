"""讲解生成测试."""
import pytest
import pytest_asyncio
from src.domain.engines.explanation_generator import (
    ExplanationGenerator, ExplanationResult, ExplanationContent
)
from src.domain.models.diagnosis import ErrorType


class TestExplanationGenerator:
    """讲解生成器测试."""
    
    @pytest.fixture
    def generator(self):
        return ExplanationGenerator()
    
    def test_generator_creation(self, generator):
        """测试生成器创建."""
        assert generator is not None
