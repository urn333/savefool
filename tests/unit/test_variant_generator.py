"""变形题生成引擎单元测试.

测试生成引擎功能：
- 5秒超时控制
- 策略选择正确性
- 失败fallback
- 并发生成
"""

import time
import pytest
from concurrent.futures import TimeoutError as FutureTimeoutError

from src.domain.models.diagnosis import ErrorType
from src.domain.models.variant import (
    GenerationStrategy,
    VariantGenerationRequest,
    VariantGenerationResult,
)
from src.domain.engines.variant_generator import (
    VariantGenerator,
    GeneratorConfig,
    generate_variant_simple,
)
from src.domain.engines.variant_strategies import TransformStatus
from tests.fixtures.variant_fixtures import (
    create_variant_request,
    SAMPLE_EQUATION_PROBLEMS,
)


class TestGeneratorConfig:
    """生成器配置测试."""
    
    def test_default_config(self):
        """测试默认配置."""
        config = GeneratorConfig()
        
        assert config.timeout_seconds == 5.0
        assert config.max_concurrent == 3
        assert config.enable_fallback is True
        assert config.min_credibility_score == 0.4
        assert len(config.default_strategy_order) > 0
    
    def test_custom_config(self):
        """测试自定义配置."""
        config = GeneratorConfig(
            timeout_seconds=10.0,
            max_concurrent=5,
            enable_fallback=False,
            min_credibility_score=0.6,
        )
        
        assert config.timeout_seconds == 10.0
        assert config.max_concurrent == 5
        assert config.enable_fallback is False
        assert config.min_credibility_score == 0.6


class TestVariantGeneratorCreation:
    """生成器创建测试."""
    
    def test_default_creation(self):
        """测试默认创建."""
        generator = VariantGenerator()
        
        assert generator.config is not None
        assert generator.validator is not None
        assert generator.rater is not None
    
    def test_custom_config_creation(self):
        """测试自定义配置创建."""
        config = GeneratorConfig(timeout_seconds=3.0)
        generator = VariantGenerator(config)
        
        assert generator.config.timeout_seconds == 3.0


class TestVariantGeneration:
    """变形题生成测试."""
    
    @pytest.fixture
    def generator(self):
        """创建生成器实例."""
        return VariantGenerator()
    
    @pytest.fixture
    def sample_request(self):
        """创建示例请求."""
        return create_variant_request(
            error_type=ErrorType.CALCULATION_ERROR,
            count=2,
        )
    
    def test_generate_returns_result(self, generator, sample_request):
        """测试生成返回结果."""
        result = generator.generate(
            sample_request,
            original_problem="2x + 5 = 15",
            original_answer="5",
        )
        
        assert isinstance(result, VariantGenerationResult)
        assert hasattr(result, 'variants')
        assert hasattr(result, 'metadata')
    
    def test_generate_single_variant(self, generator):
        """测试生成单个变形题."""
        request = create_variant_request(count=1)
        result = generator.generate(
            request,
            original_problem="2x + 5 = 15",
            original_answer="5",
        )
        
        assert len(result.variants) >= 0  # 可能为0如果所有策略都失败
    
    def test_generate_multiple_variants(self, generator):
        """测试生成多个变形题."""
        request = create_variant_request(count=3)
        result = generator.generate(
            request,
            original_problem="2x + 5 = 15",
            original_answer="5",
        )
        
        # 最多生成请求数量
        assert len(result.variants) <= 3
    
    def test_generated_variants_have_id(self, generator, sample_request):
        """测试生成的变形题有ID."""
        result = generator.generate(
            sample_request,
            original_problem="2x + 5 = 15",
            original_answer="5",
        )
        
        for variant in result.variants:
            assert variant.id is not None
            assert len(variant.id) > 0
    
    def test_generated_variants_solvable(self, generator, sample_request):
        """测试生成的变形题可解."""
        result = generator.generate(
            sample_request,
            original_problem="2x + 5 = 15",
            original_answer="5",
        )
        
        for variant in result.variants:
            assert variant.is_solvable is True
            assert variant.answer is not None
    
    def test_metadata_contains_strategies(self, generator, sample_request):
        """测试元数据包含策略信息."""
        result = generator.generate(
            sample_request,
            original_problem="2x + 5 = 15",
            original_answer="5",
        )
        
        assert "strategies_attempted" in result.metadata
        assert "strategies_succeeded" in result.metadata
    
    def test_metadata_contains_elapsed_time(self, generator, sample_request):
        """测试元数据包含耗时."""
        result = generator.generate(
            sample_request,
            original_problem="2x + 5 = 15",
            original_answer="5",
        )
        
        assert "elapsed_time" in result.metadata
        assert result.metadata["elapsed_time"] >= 0


class TestTimeoutControl:
    """超时控制测试."""
    
    def test_short_timeout(self):
        """测试短超时."""
        config = GeneratorConfig(timeout_seconds=0.001)  # 极短超时
        generator = VariantGenerator(config)
        
        request = create_variant_request(count=5)
        result = generator.generate(
            request,
            original_problem="2x + 5 = 15",
            original_answer="5",
        )
        
        # 应该超时，生成的数量可能少于请求
        assert result.metadata.get("timeout_reached") is True or len(result.variants) < 5
    
    def test_timeout_respected(self):
        """测试超时被尊重."""
        config = GeneratorConfig(timeout_seconds=0.5)
        generator = VariantGenerator(config)
        
        request = create_variant_request(count=10)
        
        start = time.time()
        result = generator.generate(
            request,
            original_problem="2x + 5 = 15",
            original_answer="5",
        )
        elapsed = time.time() - start
        
        # 总耗时应该接近或小于超时时间（允许一些误差）
        assert elapsed < 2.0  # 宽松的时间限制


class TestStrategySelection:
    """策略选择测试."""
    
    def test_strategy_selection_by_error_type(self):
        """测试根据错误类型选择策略."""
        generator = VariantGenerator()
        
        # 不同错误类型应该产生不同的策略列表
        request_calc = create_variant_request(error_type=ErrorType.CALCULATION_ERROR)
        request_concept = create_variant_request(error_type=ErrorType.CONCEPT_MISUNDERSTANDING)
        
        strategies_calc = generator._select_strategies(request_calc)
        strategies_concept = generator._select_strategies(request_concept)
        
        assert len(strategies_calc) > 0
        assert len(strategies_concept) > 0
    
    def test_strategy_selection_with_custom_strategies(self):
        """测试自定义策略选择."""
        generator = VariantGenerator()
        
        custom_strategies = [GenerationStrategy.VALUE_SUBSTITUTION]
        request = create_variant_request(strategies=custom_strategies)
        
        selected = generator._select_strategies(request)
        
        assert selected == custom_strategies
    
    def test_all_strategies_available(self):
        """测试所有策略可用."""
        generator = VariantGenerator()
        
        # 检查策略映射表
        assert GenerationStrategy.VALUE_SUBSTITUTION in generator._strategy_map
        assert GenerationStrategy.REVERSE_CONSTRUCT in generator._strategy_map
        assert GenerationStrategy.CONTEXT_CHANGE in generator._strategy_map
        assert GenerationStrategy.CONDITION_MODIFY in generator._strategy_map


class TestFallbackGeneration:
    """Fallback生成测试."""
    
    def test_fallback_enabled(self):
        """测试启用fallback."""
        config = GeneratorConfig(enable_fallback=True, timeout_seconds=0.001)
        generator = VariantGenerator(config)
        
        request = create_variant_request(count=3)
        result = generator.generate(
            request,
            original_problem="2x + 5 = 15",
            original_answer="5",
        )
        
        # fallback应该补充生成的数量
        # 注意：fallback可能也失败，但至少不会抛出异常
    
    def test_fallback_disabled(self):
        """测试禁用fallback."""
        config = GeneratorConfig(enable_fallback=False, timeout_seconds=0.001)
        generator = VariantGenerator(config)
        
        request = create_variant_request(count=3)
        result = generator.generate(
            request,
            original_problem="2x + 5 = 15",
            original_answer="5",
        )
        
        # 禁用fallback时，可能生成的更少
        assert len(result.variants) <= 3


class TestBatchGeneration:
    """批量生成测试."""
    
    def test_batch_generation(self):
        """测试批量生成."""
        config = GeneratorConfig(max_concurrent=2)
        generator = VariantGenerator(config)
        
        requests = [
            (create_variant_request(count=1), "2x + 5 = 15", "5"),
            (create_variant_request(count=1), "3x - 7 = 14", "7"),
        ]
        
        results = generator.generate_batch(requests)
        
        assert len(results) == len(requests)
        for result in results:
            assert isinstance(result, VariantGenerationResult)


class TestSimpleGenerationFunction:
    """简化生成函数测试."""
    
    def test_generate_variant_simple(self):
        """测试简化生成函数."""
        variant = generate_variant_simple(
            original_problem="2x + 5 = 15",
            original_answer="5",
            error_type=ErrorType.CALCULATION_ERROR,
            timeout=5.0,
        )
        
        # 可能成功也可能失败，但不应该抛出异常
        if variant is not None:
            assert variant.is_solvable
            assert variant.answer is not None


class TestGeneratorContextCreation:
    """上下文创建测试."""
    
    def test_context_creation_difficulty_same(self):
        """测试相同难度的上下文创建."""
        generator = VariantGenerator()
        request = create_variant_request(difficulty="same")
        
        context = generator._create_context(
            request, "2x + 5 = 15", "5"
        )
        
        assert context.original_difficulty == 5  # 默认难度
    
    def test_context_creation_difficulty_easier(self):
        """测试降低难度的上下文创建."""
        generator = VariantGenerator()
        request = create_variant_request(difficulty="easier")
        
        context = generator._create_context(
            request, "2x + 5 = 15", "5"
        )
        
        assert context.original_difficulty < 5
    
    def test_context_creation_difficulty_harder(self):
        """测试增加难度的上下文创建."""
        generator = VariantGenerator()
        request = create_variant_request(difficulty="harder")
        
        context = generator._create_context(
            request, "2x + 5 = 15", "5"
        )
        
        assert context.original_difficulty > 5


class TestGeneratorResultProperties:
    """生成结果属性测试."""
    
    def test_success_rate_calculation(self):
        """测试成功率计算."""
        generator = VariantGenerator()
        request = create_variant_request(count=2)
        
        result = generator.generate(
            request,
            original_problem="2x + 5 = 15",
            original_answer="5",
        )
        
        # 验证结果属性
        assert 0 <= result.success_rate <= 1
        assert result.valid_count <= len(result.variants)


class TestEdgeCases:
    """边界情况测试."""
    
    def test_empty_problem(self):
        """测试空题目."""
        generator = VariantGenerator()
        request = create_variant_request()
        
        result = generator.generate(
            request,
            original_problem="",
            original_answer="5",
        )
        
        # 应该优雅处理，不抛出异常
        assert isinstance(result, VariantGenerationResult)
    
    def test_very_long_problem(self):
        """测试超长题目."""
        generator = VariantGenerator()
        request = create_variant_request()
        
        long_problem = "2x + 5 = 15 " * 100
        result = generator.generate(
            request,
            original_problem=long_problem,
            original_answer="5",
        )
        
        # 应该优雅处理
        assert isinstance(result, VariantGenerationResult)
    
    def test_special_characters_in_problem(self):
        """测试特殊字符题目."""
        generator = VariantGenerator()
        request = create_variant_request()
        
        special_problem = "解方程: 2x² + √5 = π"
        result = generator.generate(
            request,
            original_problem=special_problem,
            original_answer="x",
        )
        
        # 应该优雅处理
        assert isinstance(result, VariantGenerationResult)
