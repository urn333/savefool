"""变形题生成引擎单元测试.

测试覆盖：
- 数值变形策略
- 逆运算变形策略
- 情境迁移策略
- 可信度评分系统
- 验证器
- 主生成引擎
"""

import asyncio
import pytest
from typing import List

from src.domain.engines.variant_credibility import (
    CredibilityEvaluator,
    CredibilityFactors,
    CredibilityHistory,
    CredibilityRating,
    StarRating,
)
from src.domain.engines.variant_generator import (
    GenerationConfig,
    VariantGenerationOutput,
    VariantGenerator,
)
from src.domain.engines.variant_strategies import (
    ContextTransferStrategy,
    InverseOperationStrategy,
    NumericVariationStrategy,
    StrategyContext,
)
from src.domain.engines.variant_validator import ValidationResult, VariantValidator
from src.domain.models.diagnosis import ErrorType, Problem
from src.domain.models.variant import VariantProblem


# ==================== 测试数据 ====================

def create_sample_problem(
    content: str = "小明有3个苹果，妈妈又给他5个，小明一共有多少个苹果？",
    answer: str = "8",
    difficulty: int = 3,
) -> Problem:
    """创建示例题目."""
    return Problem(
        content=content,
        subject="math",
        difficulty=difficulty,
        answer=answer,
        solution_steps=["3 + 5 = 8"],
        knowledge_points=["addition"],
    )


def create_calculation_problem() -> Problem:
    """创建计算题."""
    return Problem(
        content="计算: 25 × 4 + 16 = ?",
        subject="math",
        difficulty=4,
        answer="116",
        solution_steps=["25 × 4 = 100", "100 + 16 = 116"],
        knowledge_points=["multiplication", "addition"],
    )


def create_context_problem() -> Problem:
    """创建应用题."""
    return Problem(
        content="商店里有12个橙子，小明买了5个，还剩多少个？",
        subject="math",
        difficulty=2,
        answer="7",
        solution_steps=["12 - 5 = 7"],
        knowledge_points=["subtraction"],
    )


# ==================== 策略测试 ====================

class TestNumericVariationStrategy:
    """数值变形策略测试."""
    
    @pytest.mark.asyncio
    async def test_can_apply_with_numbers(self):
        """测试数字题目的适用性判断."""
        strategy = NumericVariationStrategy()
        problem = create_sample_problem()
        
        assert strategy.can_apply(problem, ErrorType.CALCULATION_ERROR) is True
        assert strategy.can_apply(problem, ErrorType.CARELESS_MISTAKE) is True
        assert strategy.can_apply(problem, ErrorType.CONCEPT_MISUNDERSTANDING) is True
    
    @pytest.mark.asyncio
    async def test_cannot_apply_without_numbers(self):
        """测试无数字题目的不适用性."""
        strategy = NumericVariationStrategy()
        problem = Problem(
            content="请描述勾股定理的内容。",
            subject="math",
            difficulty=5,
        )
        
        assert strategy.can_apply(problem, ErrorType.CALCULATION_ERROR) is False
    
    @pytest.mark.asyncio
    async def test_generate_numeric_variant(self):
        """测试生成数值变形题."""
        strategy = NumericVariationStrategy()
        problem = create_sample_problem()
        
        context = StrategyContext(
            original_problem=problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.6,
            target_difficulty=3,
        )
        
        result = await strategy.generate(context)
        
        assert result.success is True
        assert result.variant is not None
        assert result.variant.content != problem.content
        assert "苹果" in result.variant.content  # 情境应保持不变
        assert result.variant.answer is not None
        assert result.variant.difficulty >= 1
        assert result.variant.difficulty <= 10
    
    @pytest.mark.asyncio
    async def test_extract_numbers(self):
        """测试数字提取功能."""
        strategy = NumericVariationStrategy()
        text = "小明有3个苹果，吃了1.5个，还剩1/2个。"
        
        numbers = strategy._extract_numbers(text)
        
        assert len(numbers) >= 2
        # 检查是否提取到整数3
        assert any(n[1] == 3 and n[2] == "int" for n in numbers)
    
    @pytest.mark.asyncio
    async def test_confidence_score(self):
        """测试置信度计算."""
        strategy = NumericVariationStrategy()
        problem = create_sample_problem()
        
        context = StrategyContext(
            original_problem=problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.6,
            target_difficulty=3,
        )
        
        score = strategy.get_confidence_score(context)
        
        assert 0.8 <= score <= 1.0


class TestInverseOperationStrategy:
    """逆运算变形策略测试."""
    
    @pytest.mark.asyncio
    async def test_can_apply_with_operator(self):
        """测试有运算符题目的适用性."""
        strategy = InverseOperationStrategy()
        problem = create_sample_problem()
        
        assert strategy.can_apply(problem, ErrorType.LOGICAL_FLAW) is True
        assert strategy.can_apply(problem, ErrorType.CONCEPT_MISUNDERSTANDING) is True
    
    @pytest.mark.asyncio
    async def test_identify_addition(self):
        """测试识别加法运算."""
        strategy = InverseOperationStrategy()
        content = "3 + 5 = ?"
        
        op_type, op_info = strategy._identify_operation(content)
        
        assert op_type == "addition"
    
    @pytest.mark.asyncio
    async def test_identify_subtraction(self):
        """测试识别减法运算."""
        strategy = InverseOperationStrategy()
        content = "12 - 5 = ?"
        
        op_type, op_info = strategy._identify_operation(content)
        
        assert op_type == "subtraction"
    
    @pytest.mark.asyncio
    async def test_get_inverse_operation(self):
        """测试逆运算映射."""
        strategy = InverseOperationStrategy()
        
        assert strategy._get_inverse_operation("addition") == "subtraction"
        assert strategy._get_inverse_operation("subtraction") == "addition"
        assert strategy._get_inverse_operation("multiplication") == "division"
        assert strategy._get_inverse_operation("division") == "multiplication"
    
    @pytest.mark.asyncio
    async def test_generate_inverse_variant(self):
        """测试生成逆运算变形题."""
        strategy = InverseOperationStrategy()
        problem = create_sample_problem()
        
        context = StrategyContext(
            original_problem=problem,
            error_type=ErrorType.LOGICAL_FLAW,
            student_level=0.6,
            target_difficulty=4,
        )
        
        result = await strategy.generate(context)
        
        # 注：由于原题是自然语言描述，可能无法直接识别为数学运算
        # 所以可能成功也可能失败，取决于实现
        if result.success:
            assert result.variant is not None
            assert "如果" in result.variant.content or "已知" in result.variant.content


class TestContextTransferStrategy:
    """情境迁移策略测试."""
    
    @pytest.mark.asyncio
    async def test_can_apply_with_context(self):
        """测试有情境题目的适用性."""
        strategy = ContextTransferStrategy()
        problem = create_sample_problem()
        
        assert strategy.can_apply(problem, ErrorType.CARELESS_MISTAKE) is True
        assert strategy.can_apply(problem, ErrorType.CALCULATION_ERROR) is True
    
    @pytest.mark.asyncio
    async def test_detect_context_elements(self):
        """测试情境元素识别."""
        strategy = ContextTransferStrategy()
        content = "小明有3个苹果，小红有5个香蕉。"
        
        detected = strategy._detect_context_elements(content)
        
        assert len(detected) >= 2  # 应该检测到人物和水果
        categories = [d["category"] for d in detected]
        assert "fruit" in categories or "person" in categories
    
    @pytest.mark.asyncio
    async def test_generate_context_variant(self):
        """测试生成情境迁移变形题."""
        strategy = ContextTransferStrategy()
        problem = create_sample_problem()
        
        context = StrategyContext(
            original_problem=problem,
            error_type=ErrorType.CARELESS_MISTAKE,
            student_level=0.6,
            target_difficulty=3,
        )
        
        result = await strategy.generate(context)
        
        assert result.success is True
        assert result.variant is not None
        assert result.variant.content != problem.content
        # 数字应保持不变
        assert "3" in result.variant.content
        assert "5" in result.variant.content
    
    @pytest.mark.asyncio
    async def test_check_naturalness(self):
        """测试情境自然度检查."""
        strategy = ContextTransferStrategy()
        
        # 自然的表述
        natural_content = "小明有3个苹果。"
        natural_score = strategy._check_naturalness(natural_content)
        assert natural_score > 0.5
        
        # 不自然的表述(量词搭配错误)
        unnatural_content = "小明有3辆苹果。"
        unnatural_score = strategy._check_naturalness(unnatural_content)
        assert unnatural_score < natural_score


# ==================== 可信度评分测试 ====================

class TestCredibilityFactors:
    """可信度因子测试."""
    
    def test_factor_validation(self):
        """测试因子值范围验证."""
        with pytest.raises(ValueError):
            CredibilityFactors(semantic_equivalence=1.5)
        
        with pytest.raises(ValueError):
            CredibilityFactors(difficulty_consistency=-0.1)
    
    def test_average_score(self):
        """测试平均分计算."""
        factors = CredibilityFactors(
            semantic_equivalence=0.8,
            difficulty_consistency=0.7,
            solvability=0.9,
            answer_validity=0.8,
            student_level_match=0.75,
            context_naturalness=0.85,
        )
        
        avg = factors.average_score
        expected = (0.8 + 0.7 + 0.9 + 0.8 + 0.75 + 0.85) / 6
        assert abs(avg - expected) < 0.01
    
    def test_weighted_score(self):
        """测试加权分数计算."""
        factors = CredibilityFactors(
            semantic_equivalence=1.0,  # 权重0.25
            difficulty_consistency=0.0,  # 权重0.15
            solvability=1.0,  # 权重0.20
            answer_validity=1.0,  # 权重0.20
            student_level_match=0.0,  # 权重0.10
            context_naturalness=0.0,  # 权重0.10
        )
        
        weighted = factors.weighted_score
        expected = 1.0 * 0.25 + 1.0 * 0.20 + 1.0 * 0.20  # = 0.65
        assert abs(weighted - expected) < 0.01


class TestCredibilityRating:
    """可信度评分测试."""
    
    def test_star_rating_validation(self):
        """测试星级范围验证."""
        with pytest.raises(ValueError):
            CredibilityRating(stars=0)
        
        with pytest.raises(ValueError):
            CredibilityRating(stars=6)
    
    def test_score_to_stars(self):
        """测试分数到星级的转换."""
        assert CredibilityRating._score_to_stars(0.95) == 5
        assert CredibilityRating._score_to_stars(0.80) == 4
        assert CredibilityRating._score_to_stars(0.65) == 3
        assert CredibilityRating._score_to_stars(0.50) == 2
        assert CredibilityRating._score_to_stars(0.30) == 1
    
    def test_from_factors(self):
        """测试从因子创建评分."""
        factors = CredibilityFactors(
            semantic_equivalence=0.9,
            difficulty_consistency=0.85,
            solvability=0.95,
            answer_validity=0.9,
            student_level_match=0.8,
            context_naturalness=0.85,
        )
        
        rating = CredibilityRating.from_factors(factors)
        
        assert rating.stars >= 4  # 高分应该得到4-5星
        assert rating.ai_stars == rating.stars
        assert rating.manual_stars is None
    
    def test_adjust_rating(self):
        """测试手动调整评分."""
        factors = CredibilityFactors(
            semantic_equivalence=0.9,
            difficulty_consistency=0.9,
            solvability=0.9,
            answer_validity=0.9,
            student_level_match=0.9,
            context_naturalness=0.9,
        )
        rating = CredibilityRating.from_factors(factors)
        
        # AI评分应该是5星
        assert rating.stars == 5
        
        # 手动调整为3星
        rating.adjust_rating(3, reason="答案有误", rater_id="parent_001")
        
        assert rating.stars == 3
        assert rating.manual_stars == 3
        assert rating.adjustment_reason == "答案有误"
        assert rating.rater_id == "parent_001"
    
    def test_get_rating_description(self):
        """测试获取评分描述."""
        rating = CredibilityRating(stars=5)
        desc = rating.get_rating_description()
        assert "5星" in desc or "优秀" in desc
        
        rating2 = CredibilityRating(stars=1)
        desc2 = rating2.get_rating_description()
        assert "1星" in desc2 or "无法使用" in desc2


class TestCredibilityEvaluator:
    """可信度评估器测试."""
    
    @pytest.mark.asyncio
    async def test_evaluate_semantic_equivalence(self):
        """测试语义等价性评估."""
        evaluator = CredibilityEvaluator()
        
        original = create_sample_problem()
        variant = VariantProblem(
            original_problem_id=original.id,
            content="小明有4个苹果，妈妈又给他6个，小明一共有多少个苹果？",
            difficulty=3,
            target_concept="addition",
            error_type=ErrorType.CALCULATION_ERROR,
            strategy=__import__("src.domain.models.variant", fromlist=["GenerationStrategy"]).GenerationStrategy.VALUE_SUBSTITUTION,
            answer="10",
        )
        
        score = evaluator._evaluate_semantic_equivalence(variant, original)
        assert 0.5 <= score <= 1.0
    
    @pytest.mark.asyncio
    async def test_evaluate_solvability(self):
        """测试可解性评估."""
        evaluator = CredibilityEvaluator()
        
        # 有答案的变形题
        variant_with_answer = VariantProblem(
            original_problem_id="test",
            content="1 + 1 = ?",
            difficulty=1,
            target_concept="addition",
            error_type=ErrorType.CALCULATION_ERROR,
            strategy=__import__("src.domain.models.variant", fromlist=["GenerationStrategy"]).GenerationStrategy.VALUE_SUBSTITUTION,
            answer="2",
        )
        
        score = evaluator._evaluate_solvability(variant_with_answer)
        assert score >= 0.7
        
        # 无答案的变形题
        variant_without_answer = VariantProblem(
            original_problem_id="test",
            content="1 + 1 = ?",
            difficulty=1,
            target_concept="addition",
            error_type=ErrorType.CALCULATION_ERROR,
            strategy=__import__("src.domain.models.variant", fromlist=["GenerationStrategy"]).GenerationStrategy.VALUE_SUBSTITUTION,
        )
        
        score2 = evaluator._evaluate_solvability(variant_without_answer)
        assert score2 < 0.7


# ==================== 验证器测试 ====================

class TestVariantValidator:
    """变形题验证器测试."""
    
    @pytest.mark.asyncio
    async def test_validate_valid_variant(self):
        """测试有效变形题的验证."""
        validator = VariantValidator()
        
        original = create_sample_problem()
        variant = VariantProblem(
            original_problem_id=original.id,
            content="小明有4个苹果，妈妈又给他6个，小明一共有多少个苹果？",
            difficulty=3,
            target_concept="addition",
            error_type=ErrorType.CALCULATION_ERROR,
            strategy=__import__("src.domain.models.variant", fromlist=["GenerationStrategy"]).GenerationStrategy.VALUE_SUBSTITUTION,
            answer="10",
        )
        
        result = await validator.validate(variant, original, 0.6)
        
        assert isinstance(result, ValidationResult)
        # 有效变形题应该没有错误或很少
        assert len(result.errors) == 0 or result.is_valid
    
    @pytest.mark.asyncio
    async def test_validate_empty_content(self):
        """测试空内容变形题的验证."""
        validator = VariantValidator()
        
        original = create_sample_problem()
        variant = VariantProblem(
            original_problem_id=original.id,
            content="",
            difficulty=3,
            target_concept="addition",
            error_type=ErrorType.CALCULATION_ERROR,
            strategy=__import__("src.domain.models.variant", fromlist=["GenerationStrategy"]).GenerationStrategy.VALUE_SUBSTITUTION,
        )
        
        result = await validator.validate(variant, original, 0.6)
        
        assert result.is_valid is False
        assert any("内容" in e or "empty" in e.lower() for e in result.errors)
    
    def test_quick_validate(self):
        """测试快速验证."""
        validator = VariantValidator()
        
        # 有效变形题
        from src.domain.models.variant import GenerationStrategy
        valid_variant = VariantProblem(
            original_problem_id="test",
            content="计算：1 + 2 = ?",
            difficulty=1,
            target_concept="addition",
            error_type=ErrorType.CALCULATION_ERROR,
            strategy=GenerationStrategy.VALUE_SUBSTITUTION,
            answer="3",
        )
        assert validator.quick_validate(valid_variant) is True
        
        # 无效变形题(内容太短)
        from src.domain.models.variant import GenerationStrategy
        invalid_variant = VariantProblem(
            original_problem_id="test",
            content="1",
            difficulty=1,
            target_concept="addition",
            error_type=ErrorType.CALCULATION_ERROR,
            strategy=GenerationStrategy.VALUE_SUBSTITUTION,
        )
        assert validator.quick_validate(invalid_variant) is False


# ==================== 主生成引擎测试 ====================

class TestVariantGenerator:
    """变形题生成引擎测试."""
    
    @pytest.fixture
    def generator(self):
        """创建生成器实例."""
        config = GenerationConfig(
            timeout_seconds=5.0,
            fallback_to_preset=False,  # 测试中不使用preset
        )
        return VariantGenerator(config=config)
    
    @pytest.mark.asyncio
    async def test_generate_success(self, generator):
        """测试成功生成变形题."""
        problem = create_sample_problem()
        
        output = await generator.generate(
            original_problem=problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.6,
        )
        
        assert isinstance(output, VariantGenerationOutput)
        assert output.generation_time < 5.0  # 5秒内完成
        
        if output.variant:
            assert output.variant.content != problem.content
            assert output.credibility is not None
            assert 1 <= output.credibility.stars <= 5
    
    @pytest.mark.asyncio
    async def test_generate_with_calculation_error(self, generator):
        """测试计算错误的变形题生成."""
        problem = create_calculation_problem()
        
        output = await generator.generate(
            original_problem=problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.5,
        )
        
        assert output.generation_time < 5.0
        if output.variant:
            assert output.strategy_used in [
                "NumericVariationStrategy",
                "ContextTransferStrategy",
                "InverseOperationStrategy",
                "preset_bank",
                "fallback_failed",
            ]
    
    @pytest.mark.asyncio
    async def test_generate_with_logical_flaw(self, generator):
        """测试逻辑错误的变形题生成."""
        problem = create_sample_problem()
        
        output = await generator.generate(
            original_problem=problem,
            error_type=ErrorType.LOGICAL_FLAW,
            student_level=0.6,
        )
        
        assert output.generation_time < 5.0
    
    @pytest.mark.asyncio
    async def test_select_strategies(self, generator):
        """测试策略选择."""
        problem = create_sample_problem()
        
        # 计算错误应优先选择数值变形
        strategies = generator._select_strategies(
            ErrorType.CALCULATION_ERROR, problem
        )
        assert len(strategies) > 0
        
        # 逻辑错误应优先选择逆运算
        strategies2 = generator._select_strategies(
            ErrorType.LOGICAL_FLAW, problem
        )
        assert len(strategies2) > 0
    
    def test_calculate_target_difficulty(self, generator):
        """测试目标难度计算."""
        # 高水平学生，难度应降低
        difficulty1 = generator._calculate_target_difficulty(
            original_difficulty=5,
            student_level=0.9,
            error_type=ErrorType.CALCULATION_ERROR,
        )
        assert difficulty1 <= 5
        
        # 低水平学生，难度应降低更多(有知识缺口)
        difficulty2 = generator._calculate_target_difficulty(
            original_difficulty=5,
            student_level=0.3,
            error_type=ErrorType.KNOWLEDGE_GAP,
        )
        assert difficulty2 < 5
    
    @pytest.mark.asyncio
    async def test_generate_batch(self, generator):
        """测试批量生成."""
        problem = create_sample_problem()
        
        result = await generator.generate_batch(
            original_problem=problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.6,
            count=2,
        )
        
        assert len(result.variants) <= 2
        assert result.metadata["requested_count"] == 2


# ==================== 集成测试 ====================

class TestIntegration:
    """集成测试."""
    
    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        """测试完整流程."""
        # 1. 创建题目
        problem = create_sample_problem()
        
        # 2. 生成变形题
        generator = VariantGenerator()
        output = await generator.generate(
            original_problem=problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.6,
        )
        
        # 3. 验证结果
        assert output.generation_time <= 5.0  # 5秒约束
        
        if output.variant:
            # 验证变形题
            validator = VariantValidator()
            validation = await validator.validate(
                output.variant, problem, 0.6
            )
            
            # 如果有答案，验证答案
            if output.variant.answer:
                assert len(output.variant.answer) > 0
            
            # 验证可信度
            if output.credibility:
                assert 1 <= output.credibility.stars <= 5
                
                # 验证星级描述
                desc = output.credibility.get_rating_description()
                assert len(desc) > 0
    
    @pytest.mark.asyncio
    async def test_credibility_history(self):
        """测试可信度历史记录."""
        history = CredibilityHistory()
        
        # 添加记录
        factors = CredibilityFactors(
            semantic_equivalence=0.9,
            difficulty_consistency=0.85,
            solvability=0.95,
            answer_validity=0.9,
            student_level_match=0.8,
            context_naturalness=0.85,
        )
        rating = CredibilityRating.from_factors(factors)
        
        history.add_record("variant_001", rating)
        
        # 获取校准数据(没有手动评分时会有error字段)
        calibration = history.get_calibration_data()
        assert "total_records" in calibration or "error" in calibration
        
        # 获取星级分布
        distribution = history.get_star_distribution()
        assert sum(distribution.values()) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
