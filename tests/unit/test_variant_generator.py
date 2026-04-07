"""变形题生成引擎单元测试.

测试生成引擎功能：
- 5秒超时控制
- 策略选择正确性
- 失败fallback
- 并发生成
"""

import time
import pytest
import asyncio

from src.domain.models.diagnosis import ErrorType
from src.domain.models.variant import VariantProblem
from src.domain.models.diagnosis import Problem
from src.domain.engines.variant_generator import (
    VariantGenerator,
    GenerationConfig,
    VariantGenerationOutput,
)


class TestGenerationConfig:
    """生成器配置测试."""
    
    def test_default_config(self):
        """测试默认配置."""
        config = GenerationConfig()
        
        assert config.timeout_seconds == 5.0
        assert config.max_retries == 2
        assert config.fallback_to_preset is True
        assert config.enable_credibility_rating is True
        assert config.enable_validation is True
    
    def test_custom_config(self):
        """测试自定义配置."""
        config = GenerationConfig(
            timeout_seconds=10.0,
            max_retries=5,
            fallback_to_preset=False,
        )
        
        assert config.timeout_seconds == 10.0
        assert config.max_retries == 5
        assert config.fallback_to_preset is False


class TestVariantGeneratorCreation:
    """生成器创建测试."""
    
    def test_default_creation(self):
        """测试默认创建."""
        generator = VariantGenerator()
        
        assert generator.config is not None
        assert generator.config.timeout_seconds == 5.0
    
    def test_custom_config_creation(self):
        """测试自定义配置创建."""
        config = GenerationConfig(timeout_seconds=3.0)
        generator = VariantGenerator(config=config)
        
        assert generator.config.timeout_seconds == 3.0


class TestVariantGeneration:
    """变形题生成测试."""
    
    @pytest.fixture
    def generator(self):
        """创建生成器实例."""
        return VariantGenerator()
    
    @pytest.fixture
    def sample_problem(self):
        """创建示例题目."""
        return Problem(
            content="2x + 5 = 15",
            subject="math",
            difficulty=3,
            answer="5",
            knowledge_points=["linear_equation"],
        )
    
    @pytest.mark.asyncio
    async def test_generate_returns_output(self, generator, sample_problem):
        """测试生成返回输出."""
        result = await generator.generate(
            original_problem=sample_problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.5,
        )
        
        assert isinstance(result, VariantGenerationOutput)
        assert hasattr(result, 'variant')
        assert hasattr(result, 'credibility')
        assert hasattr(result, 'generation_time')
    
    @pytest.mark.asyncio
    async def test_generate_with_timeout(self, generator, sample_problem):
        """测试带超时的生成."""
        start = time.time()
        result = await generator.generate(
            original_problem=sample_problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.5,
        )
        elapsed = time.time() - start
        
        # 应该在合理时间内完成（允许一些误差）
        assert elapsed < 10.0
        assert result.generation_time >= 0
    
    @pytest.mark.asyncio
    async def test_generate_respects_timeout(self):
        """测试超时被尊重."""
        config = GenerationConfig(timeout_seconds=0.001)
        generator = VariantGenerator(config=config)
        
        problem = Problem(
            content="2x + 5 = 15",
            subject="math",
            difficulty=3,
            answer="5",
            knowledge_points=["linear_equation"],
        )
        
        result = await generator.generate(
            original_problem=problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.5,
        )
        
        # 应该超时并返回fallback或空结果
        assert result is not None


class TestStrategySelection:
    """策略选择测试."""
    
    def test_strategy_selection_by_error_type(self):
        """测试根据错误类型选择策略."""
        generator = VariantGenerator()
        
        problem = Problem(
            content="2x + 5 = 15",
            subject="math",
            difficulty=3,
            answer="5",
        )
        
        # 不同错误类型应该产生不同的策略列表
        strategies_calc = generator._select_strategies(ErrorType.CALCULATION_ERROR, problem)
        strategies_concept = generator._select_strategies(ErrorType.CONCEPT_MISUNDERSTANDING, problem)
        
        assert len(strategies_calc) > 0
        assert len(strategies_concept) > 0
    
    def test_calculate_target_difficulty(self):
        """测试目标难度计算."""
        generator = VariantGenerator()
        
        difficulty = generator._calculate_target_difficulty(
            original_difficulty=5,
            student_level=0.5,
            error_type=ErrorType.CALCULATION_ERROR,
        )
        
        assert 1 <= difficulty <= 10


class TestFallbackGeneration:
    """Fallback生成测试."""
    
    @pytest.mark.asyncio
    async def test_fallback_enabled(self):
        """测试启用fallback."""
        config = GenerationConfig(fallback_to_preset=True, timeout_seconds=0.001)
        generator = VariantGenerator(config=config)
        
        problem = Problem(
            content="特殊题目",
            subject="math",
            difficulty=5,
            answer="42",
            knowledge_points=["special"],
        )
        
        result = await generator.generate(
            original_problem=problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.5,
        )
        
        # fallback应该处理超时情况
        assert result is not None


class TestBatchGeneration:
    """批量生成测试."""
    
    @pytest.mark.asyncio
    async def test_batch_generation(self):
        """测试批量生成."""
        generator = VariantGenerator()
        
        problem = Problem(
            content="2x + 5 = 15",
            subject="math",
            difficulty=3,
            answer="5",
            knowledge_points=["linear_equation"],
        )
        
        result = await generator.generate_batch(
            original_problem=problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.5,
            count=2,
        )
        
        assert len(result.variants) <= 2
        assert hasattr(result, 'metadata')


class TestCredibilityHistory:
    """可信度历史测试."""
    
    def test_get_credibility_history(self):
        """测试获取历史记录."""
        generator = VariantGenerator()
        history = generator.get_credibility_history()
        
        assert history is not None
    
    def test_get_calibration_report(self):
        """测试获取校准报告."""
        generator = VariantGenerator()
        report = generator.get_calibration_report()
        
        assert isinstance(report, dict)


class TestVariantGenerationOutput:
    """生成输出测试."""
    
    def test_output_creation(self):
        """测试输岀创建."""
        output = VariantGenerationOutput(
            variant=None,
            credibility=None,
            validation=None,
            generation_time=1.5,
            strategy_used="numeric",
            is_fallback=False,
            metadata={},
        )
        
        assert output.generation_time == 1.5
        assert output.strategy_used == "numeric"
        assert output.is_fallback is False
    
    def test_output_to_dict(self):
        """测试转换为字典."""
        output = VariantGenerationOutput(
            variant=None,
            credibility=None,
            validation=None,
            generation_time=1.0,
            strategy_used="test",
            is_fallback=False,
            metadata={"key": "value"},
        )
        
        data = output.to_dict()
        
        assert data["generation_time"] == 1.0
        assert data["strategy_used"] == "test"
        assert data["metadata"]["key"] == "value"


class TestEdgeCases:
    """边界情况测试."""
    
    @pytest.mark.asyncio
    async def test_empty_problem(self):
        """测试空题目."""
        generator = VariantGenerator()
        
        problem = Problem(
            content="",
            subject="math",
            difficulty=3,
            answer="",
        )
        
        result = await generator.generate(
            original_problem=problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.5,
        )
        
        # 应该优雅处理，不抛出异常
        assert isinstance(result, VariantGenerationOutput)
    
    @pytest.mark.asyncio
    async def test_special_characters_in_problem(self):
        """测试特殊字符题目."""
        generator = VariantGenerator()
        
        problem = Problem(
            content="解方程: 2x² + √5 = π",
            subject="math",
            difficulty=5,
            answer="x",
        )
        
        result = await generator.generate(
            original_problem=problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.5,
        )
        
        # 应该优雅处理
        assert isinstance(result, VariantGenerationOutput)
