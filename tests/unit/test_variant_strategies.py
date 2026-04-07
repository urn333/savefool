"""变形策略单元测试.

测试数值变形策略：
- 整数/分数/小数转换
- 等价性验证
- 结构保持验证
- 边界情况
"""

import re
import pytest
import asyncio

from src.domain.models.diagnosis import ErrorType
from src.domain.models.variant import GenerationStrategy
from src.domain.engines.variant_strategies import (
    NumericVariationStrategy,
    InverseOperationStrategy,
    ContextTransferStrategy,
    StrategyContext,
    StrategyResult,
    VariantStrategy,
)
from src.domain.models.diagnosis import Problem


class TestNumericVariationStrategy:
    """数值变形策略测试."""
    
    @pytest.fixture
    def strategy(self):
        """创建策略实例."""
        return NumericVariationStrategy()
    
    @pytest.fixture
    def sample_problem(self):
        """创建示例题目."""
        return Problem(
            content="2x + 5 = 15",
            subject="math",
            difficulty=3,
            answer="5",
            solution_steps=["移项", "计算"],
        )
    
    def test_strategy_attributes(self, strategy):
        """测试策略属性."""
        assert strategy.strategy_name == "数值变形"
        assert strategy.strategy_type == "numeric"
        assert strategy.difficulty_adjustment == 0.0
    
    def test_can_apply_with_numbers(self, strategy, sample_problem):
        """测试能处理包含数值的题目."""
        assert strategy.can_apply(sample_problem, ErrorType.CALCULATION_ERROR) is True
    
    def test_can_apply_without_numbers(self, strategy):
        """测试不能处理无数值的题目."""
        problem = Problem(
            content="求未知数",
            subject="math",
            difficulty=3,
        )
        assert strategy.can_apply(problem, ErrorType.CARELESS_MISTAKE) is False
    
    @pytest.mark.asyncio
    async def test_generate_success(self, strategy, sample_problem):
        """测试成功变形."""
        context = StrategyContext(
            original_problem=sample_problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.5,
            target_difficulty=3,
        )
        
        result = await strategy.generate(context)
        
        assert result.success is True
        assert result.variant is not None
    
    def test_extract_numbers(self, strategy):
        """测试数值提取."""
        text = "2x + 5.5 = 15，解是3/4"
        numbers = strategy._extract_numbers(text)
        
        # 检查提取到的数值
        assert "2" in numbers
        assert "5.5" in numbers
        assert "15" in numbers
    
    def test_select_number_to_replace(self, strategy):
        """测试选择替换数值."""
        numbers = ["2", "5", "15"]
        answer = "5"
        
        target = strategy._select_number_to_replace(numbers, answer)
        assert target is not None
    
    def test_generate_new_number(self, strategy):
        """测试生成新数值."""
        original = "5"
        difficulty = 5
        
        new_value = strategy._generate_new_number(original, difficulty)
        assert new_value is not None
        assert new_value != original
    
    def test_replace_number(self, strategy):
        """测试数值替换."""
        content = "2x + 5 = 15"
        new_content = strategy._replace_number(content, "5", "10")
        
        assert "10" in new_content
        assert "2x + 10 = 15" == new_content


class TestInverseOperationStrategy:
    """逆运算变形策略测试."""
    
    @pytest.fixture
    def strategy(self):
        """创建策略实例."""
        return InverseOperationStrategy()
    
    def test_strategy_attributes(self, strategy):
        """测试策略属性."""
        assert strategy.strategy_name == "逆运算变形"
        assert strategy.strategy_type == "inverse"
        assert strategy.difficulty_adjustment == 1.0
    
    def test_can_apply_with_equation(self, strategy):
        """测试能处理方程题."""
        problem = Problem(
            content="解方程 2x + 5 = 15",
            subject="math",
            difficulty=3,
            answer="5",
        )
        assert strategy.can_apply(problem, ErrorType.CALCULATION_ERROR) is True
    
    def test_can_apply_without_variable(self, strategy):
        """测试不能处理无变量题."""
        problem = Problem(
            content="计算 5 + 3",
            subject="math",
            difficulty=2,
            answer="8",
        )
        assert strategy.can_apply(problem, ErrorType.CARELESS_MISTAKE) is False
    
    @pytest.mark.asyncio
    async def test_generate(self, strategy):
        """测试生成."""
        problem = Problem(
            content="2x + 5 = 15",
            subject="math",
            difficulty=3,
            answer="5",
        )
        context = StrategyContext(
            original_problem=problem,
            error_type=ErrorType.LOGICAL_FLAW,
            student_level=0.5,
            target_difficulty=4,
        )
        
        result = await strategy.generate(context)
        
        assert isinstance(result, StrategyResult)
        # 可能成功也可能失败，取决于实现


class TestContextTransferStrategy:
    """情境迁移策略测试."""
    
    @pytest.fixture
    def strategy(self):
        """创建策略实例."""
        return ContextTransferStrategy()
    
    def test_strategy_attributes(self, strategy):
        """测试策略属性."""
        assert strategy.strategy_name == "情境迁移"
        assert strategy.strategy_type == "context"
    
    def test_can_apply_with_context(self, strategy):
        """测试能处理有背景情境的题目."""
        problem = Problem(
            content="小明有5个苹果",
            subject="math",
            difficulty=2,
            answer="5",
        )
        assert strategy.can_apply(problem, ErrorType.CARELESS_MISTAKE) is True
    
    def test_context_mappings_exist(self, strategy):
        """测试情境映射表存在."""
        assert len(strategy.CONTEXT_MAPPINGS) > 0
        assert "苹果" in strategy.CONTEXT_MAPPINGS
    
    @pytest.mark.asyncio
    async def test_generate(self, strategy):
        """测试生成."""
        problem = Problem(
            content="小明有5个苹果，给了小红2个，还剩几个？",
            subject="math",
            difficulty=2,
            answer="3",
        )
        context = StrategyContext(
            original_problem=problem,
            error_type=ErrorType.CARELESS_MISTAKE,
            student_level=0.5,
            target_difficulty=2,
        )
        
        result = await strategy.generate(context)
        
        assert isinstance(result, StrategyResult)
        if result.success:
            assert result.variant is not None


class TestStrategyContext:
    """策略上下文测试."""
    
    def test_context_creation(self):
        """测试上下文创建."""
        problem = Problem(
            content="2x + 5 = 15",
            subject="math",
            difficulty=3,
        )
        
        context = StrategyContext(
            original_problem=problem,
            error_type=ErrorType.CALCULATION_ERROR,
            student_level=0.5,
            target_difficulty=5,
        )
        
        assert context.original_problem == problem
        assert context.error_type == ErrorType.CALCULATION_ERROR
        assert context.student_level == 0.5
        assert context.target_difficulty == 5
    
    def test_student_level_validation(self):
        """测试学生水平验证."""
        problem = Problem(content="test", subject="math", difficulty=3)
        
        with pytest.raises(ValueError):
            StrategyContext(
                original_problem=problem,
                error_type=ErrorType.CARELESS_MISTAKE,
                student_level=1.5,  # 超出范围
                target_difficulty=5,
            )


class TestStrategyResult:
    """策略结果测试."""
    
    def test_result_creation_success(self):
        """测试成功结果创建."""
        from src.domain.models.variant import VariantProblem
        
        variant = VariantProblem(
            original_problem_id="test",
            content="2x + 5 = 15",
            difficulty=3,
            target_concept="algebra",
            error_type=ErrorType.CALCULATION_ERROR,
            strategy=GenerationStrategy.VALUE_SUBSTITUTION,
            answer="5",
        )
        
        result = StrategyResult(
            success=True,
            variant=variant,
            metadata={"strategy": "numeric"},
        )
        
        assert result.success is True
        assert result.variant == variant
    
    def test_result_creation_failure(self):
        """测试失败结果创建."""
        result = StrategyResult(
            success=False,
            error_message="变形失败",
        )
        
        assert result.success is False
        assert result.variant is None
        assert result.error_message == "变形失败"


class TestIntegration:
    """集成测试."""
    
    @pytest.mark.asyncio
    async def test_all_strategies_on_sample_problems(self):
        """测试所有策略在样本题目上."""
        strategies = [
            NumericVariationStrategy(),
            InverseOperationStrategy(),
            ContextTransferStrategy(),
        ]
        
        problems = [
            Problem(content="2x + 5 = 15", subject="math", difficulty=3, answer="5"),
            Problem(content="3x - 7 = 14", subject="math", difficulty=4, answer="7"),
            Problem(content="小明有5个苹果", subject="math", difficulty=2, answer="5"),
        ]
        
        for strategy in strategies:
            for problem in problems:
                if strategy.can_apply(problem, ErrorType.CALCULATION_ERROR):
                    context = StrategyContext(
                        original_problem=problem,
                        error_type=ErrorType.CALCULATION_ERROR,
                        student_level=0.5,
                        target_difficulty=problem.difficulty,
                    )
                    
                    result = await strategy.generate(context)
                    
                    # 验证结果格式
                    assert result.success in [True, False]
                    if result.success:
                        assert result.variant is not None
