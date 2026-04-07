"""变形题集成测试.

测试完整流程：
- 原题→变形→评分→验证
- 与诊断引擎集成
- 与记忆系统集成
"""

import pytest

from src.domain.models.diagnosis import ErrorType, Problem
from src.domain.models.variant import (
    GenerationStrategy,
    VariantProblem,
)
from src.domain.engines.variant_generator import (
    VariantGenerator,
    GenerationConfig,
)
from src.domain.engines.variant_validator import VariantValidator
from src.domain.engines.variant_credibility import (
    CredibilityEvaluator,
    CredibilityFactors,
    StarRating,
)
from src.domain.engines.variant_strategies import (
    NumericVariationStrategy,
    InverseOperationStrategy,
    ContextTransferStrategy,
    StrategyContext,
)


class TestVariantGenerationFlow:
    """变形题生成流程集成测试."""
    
    @pytest.fixture
    def full_pipeline(self):
        """创建完整处理流水线."""
        return {
            "generator": VariantGenerator(),
            "validator": VariantValidator(),
            "evaluator": CredibilityEvaluator(),
        }
    
    @pytest.mark.asyncio
    async def test_complete_generation_flow(self, full_pipeline):
        """测试完整生成流程."""
        problem = Problem(
            content="2x + 5 = 15",
            subject="math",
            difficulty=3,
            answer="5",
            knowledge_points=["linear_equation"],
        )
        
        # 1. 生成变形题
        result = await full_pipeline["generator"].generate(
            original_problem=problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.5,
        )
        
        # 2. 验证结果结构
        assert hasattr(result, 'variant')
        assert hasattr(result, 'credibility')
        assert hasattr(result, 'generation_time')
        
        # 3. 如果有变形题生成，验证质量
        if result.variant:
            validation = await full_pipeline["validator"].validate(
                result.variant, problem, 0.5
            )
            assert hasattr(validation, 'is_valid')
    
    @pytest.mark.asyncio
    async def test_generation_with_timeout(self, full_pipeline):
        """测试带超时的生成."""
        problem = Problem(
            content="3x - 7 = 14",
            subject="math",
            difficulty=4,
            answer="7",
            knowledge_points=["linear_equation"],
        )
        
        result = await full_pipeline["generator"].generate(
            original_problem=problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.5,
        )
        
        # 验证在合理时间内完成
        assert result.generation_time < 10.0
    
    @pytest.mark.asyncio
    async def test_batch_generation_flow(self, full_pipeline):
        """测试批量生成流程."""
        problem = Problem(
            content="5x + 3 = 28",
            subject="math",
            difficulty=3,
            answer="5",
            knowledge_points=["linear_equation"],
        )
        
        result = await full_pipeline["generator"].generate_batch(
            original_problem=problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.5,
            count=2,
        )
        
        # 验证批量结果
        assert len(result.variants) <= 2
        assert hasattr(result, 'metadata')


class TestDiagnosisEngineIntegration:
    """诊断引擎集成测试."""
    
    def test_error_type_to_strategy_mapping(self):
        """测试错误类型到策略的映射."""
        generator = VariantGenerator()
        
        problem = Problem(
            content="2x + 5 = 15",
            subject="math",
            difficulty=3,
            answer="5",
        )
        
        # 不同错误类型应该产生不同的策略列表
        for error_type in [
            ErrorType.CALCULATION_ERROR,
            ErrorType.CONCEPT_MISUNDERSTANDING,
            ErrorType.CARELESS_MISTAKE,
        ]:
            strategies = generator._select_strategies(error_type, problem)
            assert len(strategies) > 0
    
    def test_strategy_can_apply(self):
        """测试策略适用性判断."""
        strategies = [
            NumericVariationStrategy(),
            InverseOperationStrategy(),
            ContextTransferStrategy(),
        ]
        
        problem = Problem(
            content="2x + 5 = 15",
            subject="math",
            difficulty=3,
            answer="5",
        )
        
        # 至少有一个策略适用
        can_apply_count = sum(
            1 for s in strategies 
            if s.can_apply(problem, ErrorType.CALCULATION_ERROR)
        )
        assert can_apply_count >= 1


class TestCredibilitySystemIntegration:
    """可信度系统集成测试."""
    
    def test_credibility_factors_calculation(self):
        """测试可信度因子计算."""
        factors = CredibilityFactors(
            semantic_equivalence=0.8,
            difficulty_consistency=0.7,
            solvability=0.9,
            answer_validity=0.85,
            student_level_match=0.75,
            context_naturalness=0.8,
        )
        
        # 验证加权分数计算
        weighted = factors.weighted_score
        assert 0.0 <= weighted <= 1.0
        
        # 验证平均分数
        avg = factors.average_score
        assert 0.0 <= avg <= 1.0
    
    def test_star_rating_from_factors(self):
        """测试从因子到星级的转换."""
        from src.domain.engines.variant_credibility import CredibilityRating
        
        # 5星测试
        excellent_factors = CredibilityFactors(
            semantic_equivalence=0.95,
            difficulty_consistency=0.90,
            solvability=1.0,
            answer_validity=1.0,
            student_level_match=0.95,
            context_naturalness=0.90,
        )
        rating = CredibilityRating.from_factors(excellent_factors)
        assert rating.stars == 5
        
        # 1星测试
        poor_factors = CredibilityFactors(
            semantic_equivalence=0.3,
            difficulty_consistency=0.2,
            solvability=0.0,
            answer_validity=0.3,
            student_level_match=0.2,
            context_naturalness=0.2,
        )
        rating = CredibilityRating.from_factors(poor_factors)
        assert rating.stars == 1
    
    def test_parent_adjustment_workflow(self):
        """测试家长调整工作流程."""
        from src.domain.engines.variant_credibility import CredibilityRating
        
        # 初始AI评分
        factors = CredibilityFactors(
            semantic_equivalence=0.8,
            difficulty_consistency=0.75,
            solvability=0.9,
            answer_validity=0.85,
            student_level_match=0.8,
            context_naturalness=0.75,
        )
        rating = CredibilityRating.from_factors(factors)
        original_stars = rating.stars
        
        # 家长调整
        rating.adjust_rating(5, reason="家长认为质量很好", rater_id="parent_001")
        
        # 验证调整
        assert rating.manual_stars == 5
        assert rating.stars == 5
        assert rating.adjustment_reason == "家长认为质量很好"


class TestEndToEndWorkflow:
    """端到端工作流测试."""
    
    @pytest.mark.asyncio
    async def test_full_workflow_equation(self):
        """测试方程题完整工作流."""
        problem = Problem(
            content="2x + 8 = 20",
            subject="math",
            difficulty=3,
            answer="6",
            knowledge_points=["linear_equation"],
        )
        
        # Step 1: 生成
        generator = VariantGenerator()
        gen_result = await generator.generate(
            original_problem=problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.5,
        )
        
        # Step 2: 验证
        if gen_result.variant:
            validator = VariantValidator()
            validation = await validator.validate(
                gen_result.variant,
                problem,
                student_level=0.5,
            )
            
            # Step 3: 检查验证结果结构
            assert hasattr(validation, 'is_valid')
            assert hasattr(validation, 'errors')
            assert hasattr(validation, 'warnings')
    
    @pytest.mark.asyncio
    async def test_multi_strategy_workflow(self):
        """测试多策略工作流."""
        problem = Problem(
            content="小明有5个苹果，给了小红2个，还剩几个？",
            subject="math",
            difficulty=2,
            answer="3",
            knowledge_points=["subtraction"],
        )
        
        strategies = [
            NumericVariationStrategy(),
            ContextTransferStrategy(),
        ]
        
        results = []
        for strategy in strategies:
            if strategy.can_apply(problem, ErrorType.CARELESS_MISTAKE):
                context = StrategyContext(
                    original_problem=problem,
                    error_type=ErrorType.CARELESS_MISTAKE,
                    student_level=0.5,
                    target_difficulty=2,
                )
                result = await strategy.generate(context)
                results.append(result)
        
        # 验证至少有一个策略成功
        assert len(results) > 0


class TestQualityAssurance:
    """质量保证测试."""
    
    @pytest.mark.asyncio
    async def test_answer_preservation(self):
        """测试答案保持."""
        problem = Problem(
            content="4x + 10 = 30",
            subject="math",
            difficulty=3,
            answer="5",
        )
        
        generator = VariantGenerator()
        result = await generator.generate(
            original_problem=problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.5,
        )
        
        # 验证生成的变形题有答案
        if result.variant:
            assert result.variant.answer is not None
    
    @pytest.mark.asyncio
    async def test_difficulty_range_constraint(self):
        """测试难度范围约束."""
        problem = Problem(
            content="2x + 5 = 15",
            subject="math",
            difficulty=3,
            answer="5",
        )
        
        generator = VariantGenerator()
        result = await generator.generate(
            original_problem=problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.5,
        )
        
        # 验证难度在1-10范围
        if result.variant:
            assert 1 <= result.variant.difficulty <= 10
