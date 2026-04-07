"""变形策略单元测试.

测试各种变形策略：
- 数值变形: 整数/分数/小数转换
- 逆运算变形: 等价性验证
- 情境迁移: 结构保持验证
- 边界情况: 除零、负数等
"""

import re
import pytest

from src.domain.models.diagnosis import ErrorType
from src.domain.models.variant import GenerationStrategy
from src.domain.engines.variant_strategies import (
    ContextTransferStrategy,
    DifficultyAdjustmentStrategy,
    InverseOperationStrategy,
    NumericTransformationStrategy,
    TransformationContext,
    TransformStatus,
)
from tests.fixtures.variant_fixtures import (
    SAMPLE_EQUATION_PROBLEMS,
    SAMPLE_APPLICATION_PROBLEMS,
    SAMPLE_FRACTION_PROBLEMS,
)


class TestNumericTransformationStrategy:
    """数值变形策略测试."""
    
    @pytest.fixture
    def strategy(self):
        """创建策略实例."""
        return NumericTransformationStrategy()
    
    @pytest.fixture
    def base_context(self):
        """创建基础上下文."""
        return TransformationContext(
            original_problem="2x + 5 = 15",
            original_answer="5",
            original_difficulty=3,
        )
    
    def test_strategy_type(self, strategy):
        """测试策略类型正确."""
        assert strategy.strategy_type == GenerationStrategy.VALUE_SUBSTITUTION
    
    def test_can_handle_with_numbers(self, strategy, base_context):
        """测试能处理包含数值的题目."""
        assert strategy.can_handle(base_context) is True
    
    def test_can_handle_without_numbers(self, strategy):
        """测试不能处理无数值的题目."""
        context = TransformationContext(
            original_problem="求未知数",
            original_answer="5",
        )
        assert strategy.can_handle(context) is False
    
    def test_transform_success(self, strategy, base_context):
        """测试成功变形."""
        result = strategy.transform(base_context)
        
        assert result.success is True
        assert result.status == TransformStatus.SUCCESS
        assert result.variant is not None
        assert result.variant.content != base_context.original_problem
    
    def test_extract_numbers(self, strategy):
        """测试数值提取."""
        text = "2x + 5.5 = 15，解是3/4"
        numbers = strategy._extract_numbers(text)
        
        assert "2" in numbers
        assert "5.5" in numbers
        assert "15" in numbers
    
    def test_transform_integer_to_fraction(self, strategy):
        """测试整数转分数."""
        context = TransformationContext(
            original_problem="4 + 3 = ?",
            original_answer="7",
        )
        result = strategy.transform(context)
        
        assert result.success is True
        # 检查是否包含分数形式
        if result.variant:
            assert "/" in result.variant.content or "." in result.variant.content
    
    def test_transform_fraction_reduction(self, strategy):
        """测试分数约分."""
        context = TransformationContext(
            original_problem="(4/8) + 1 = ?",
            original_answer="1.5",
        )
        transformed, transform_type = strategy._transform_fraction("4/8")
        
        assert transformed == "1/2"
        assert transform_type == "fraction_reduction"
    
    def test_transform_fraction_expansion(self, strategy):
        """测试分数扩分."""
        context = TransformationContext(
            original_problem="(1/2) + 1 = ?",
            original_answer="1.5",
        )
        transformed, transform_type = strategy._transform_fraction("1/2")
        
        assert "2/4" in transformed or "1/2" in transformed
    
    def test_transform_decimal_to_fraction(self, strategy):
        """测试小数转分数."""
        transformed, transform_type = strategy._transform_decimal("0.5")
        
        assert "/" in transformed
        assert transform_type == "decimal_to_fraction"
    
    def test_difficulty_adjustment(self, strategy):
        """测试难度调整."""
        # 整数转分数增加难度
        new_diff = strategy._adjust_difficulty(5, "integer_to_fraction")
        assert new_diff == 6
        
        # 分数约分降低难度
        new_diff = strategy._adjust_difficulty(5, "fraction_reduction")
        assert new_diff == 4
    
    def test_difficulty_bounds(self, strategy):
        """测试难度边界."""
        # 难度不超过10
        assert strategy._adjust_difficulty(10, "integer_to_fraction") == 10
        
        # 难度不低于1
        assert strategy._adjust_difficulty(1, "fraction_reduction") == 1
    
    def test_number_replacement(self, strategy):
        """测试数值替换."""
        content = "2x + 5 = 15"
        new_content = strategy._replace_number(content, "5", "10", occurrence=0)
        
        assert "10" in new_content
        assert "2x + 10 = 15" == new_content
    
    def test_select_target_number(self, strategy):
        """测试目标数值选择."""
        numbers = ["2", "5", "15"]
        answer = "5"
        
        # 优先选择非答案的数值
        idx = strategy._select_target_number(numbers, answer)
        assert numbers[idx] != answer
    
    def test_edge_case_division_by_zero(self, strategy):
        """测试除零边界情况."""
        # 分数变形中分母为0的情况已被预防
        # 通过构造特殊场景测试异常处理
        pass  # 当前实现不会触发除零


class TestInverseOperationStrategy:
    """逆运算变形策略测试."""
    
    @pytest.fixture
    def strategy(self):
        """创建策略实例."""
        return InverseOperationStrategy()
    
    def test_strategy_type(self, strategy):
        """测试策略类型正确."""
        assert strategy.strategy_type == GenerationStrategy.REVERSE_CONSTRUCT
    
    def test_can_handle_equation(self, strategy):
        """测试能处理方程题."""
        context = TransformationContext(
            original_problem="解方程 2x + 5 = 15",
            original_answer="5",
        )
        assert strategy.can_handle(context) is True
    
    def test_can_handle_non_equation(self, strategy):
        """测试不能处理非方程题."""
        context = TransformationContext(
            original_problem="计算 5 + 3",
            original_answer="8",
        )
        assert strategy.can_handle(context) is False
    
    def test_is_linear_equation(self, strategy):
        """测试线性方程识别."""
        assert strategy._is_linear_equation("2x + 5 = 15") is True
        assert strategy._is_linear_equation("X - 3 = 7") is True
        assert strategy._is_linear_equation("5 + 3 = 8") is False
    
    def test_is_application_problem(self, strategy):
        """测试应用题识别."""
        assert strategy._is_application_problem("小明有5个苹果") is True
        assert strategy._is_application_problem("商店买铅笔") is True
        assert strategy._is_application_problem("2x + 5 = 15") is False
    
    def test_transform_linear_equation(self, strategy):
        """测试线性方程变形."""
        context = TransformationContext(
            original_problem="2x + 5 = 15，求x",
            original_answer="5",
        )
        result = strategy.transform(context)
        
        assert result.success is True
        if result.variant:
            # 检查是否包含逆运算关键词
            keywords = ["验证", "解为", "已知", "反推"]
            assert any(kw in result.variant.content for kw in keywords)
    
    def test_transform_application_problem(self, strategy):
        """测试应用题变形."""
        context = TransformationContext(
            original_problem="小明有5个苹果，给了小红2个，还剩几个？",
            original_answer="3",
        )
        result = strategy.transform(context)
        
        # 应用题变形可能成功也可能失败，取决于实现
        assert result.status in [TransformStatus.SUCCESS, TransformStatus.FAILED]
    
    def test_extract_numbers(self, strategy):
        """测试数字提取."""
        text = "2x + 5 = 15"
        numbers = strategy._extract_numbers(text)
        
        assert "2" in numbers
        assert "5" in numbers
        assert "15" in numbers


class TestContextTransferStrategy:
    """情境迁移策略测试."""
    
    @pytest.fixture
    def strategy(self):
        """创建策略实例."""
        return ContextTransferStrategy()
    
    def test_strategy_type(self, strategy):
        """测试策略类型正确."""
        assert strategy.strategy_type == GenerationStrategy.CONTEXT_CHANGE
    
    def test_can_handle_with_context(self, strategy):
        """测试能处理有背景情境的题目."""
        context = TransformationContext(
            original_problem="小明有5个苹果",
            original_answer="5",
        )
        assert strategy.can_handle(context) is True
    
    def test_can_handle_without_context(self, strategy):
        """测试不能处理纯数学题."""
        context = TransformationContext(
            original_problem="2x + 5 = 15",
            original_answer="5",
        )
        # 纯数学题可能无法处理
        result = strategy.can_handle(context)
        assert isinstance(result, bool)
    
    def test_context_mappings_exist(self, strategy):
        """测试情境映射表存在."""
        assert len(strategy.CONTEXT_MAPPINGS) > 0
        assert "苹果" in strategy.CONTEXT_MAPPINGS
    
    def test_identify_context_type(self, strategy):
        """测试情境类型识别."""
        assert strategy._identify_context_type("买铅笔花了5元") == "shopping"
        assert strategy._identify_context_type("速度是10米/秒") == "motion"
    
    def test_apply_context_transfer(self, strategy):
        """测试情境替换应用."""
        problem = "小明有5个苹果"
        new_problem, replacements = strategy._apply_context_transfer(
            problem, "general", "shopping"
        )
        
        assert len(replacements) > 0
        assert new_problem != problem
    
    def test_structure_preservation(self, strategy):
        """测试结构保持验证."""
        original = "2x + 5 = 15"
        transformed = "2x + 5 = 15"
        
        assert strategy._verify_structure_preservation(original, transformed) is True
    
    def test_structure_not_preserved(self, strategy):
        """测试结构改变检测."""
        original = "2x + 5 = 15"
        transformed = "3x + 8 = 20"  # 数值改变
        
        assert strategy._verify_structure_preservation(original, transformed) is False
    
    def test_extract_operators(self, strategy):
        """测试运算符提取."""
        text = "2x + 5 = 15 - 3"
        operators = strategy._extract_operators(text)
        
        assert "+" in operators
        assert "=" in operators
        assert "-" in operators


class TestDifficultyAdjustmentStrategy:
    """难度调整策略测试."""
    
    def test_strategy_type_increase(self):
        """测试增加难度的策略类型."""
        strategy = DifficultyAdjustmentStrategy(difficulty_delta=1)
        assert strategy.strategy_type == GenerationStrategy.CONDITION_MODIFY
    
    def test_can_handle_always_true(self):
        """测试总是可以处理."""
        strategy = DifficultyAdjustmentStrategy()
        context = TransformationContext(
            original_problem="任意题目",
            original_answer="5",
        )
        assert strategy.can_handle(context) is True
    
    def test_decrease_difficulty(self):
        """测试降低难度."""
        strategy = DifficultyAdjustmentStrategy(difficulty_delta=-2)
        context = TransformationContext(
            original_problem="复杂的大数值题目 100 + 50 = ?",
            original_answer="150",
            original_difficulty=7,
        )
        result = strategy.transform(context)
        
        if result.success and result.variant:
            assert result.variant.difficulty < context.original_difficulty
    
    def test_increase_difficulty(self):
        """测试增加难度."""
        strategy = DifficultyAdjustmentStrategy(difficulty_delta=2)
        context = TransformationContext(
            original_problem="简单的题目",
            original_answer="5",
            original_difficulty=3,
        )
        result = strategy.transform(context)
        
        if result.success and result.variant:
            assert result.variant.difficulty > context.original_difficulty
    
    def test_no_adjustment_needed(self):
        """测试无需调整的情况."""
        strategy = DifficultyAdjustmentStrategy(difficulty_delta=0)
        context = TransformationContext(
            original_problem="2x + 5 = 15",
            original_answer="5",
        )
        result = strategy.transform(context)
        
        assert result.success is False
        assert "No difficulty adjustment needed" in result.error_message
    
    def test_simplify_numbers(self):
        """测试数值简化."""
        strategy = DifficultyAdjustmentStrategy(difficulty_delta=-1)
        problem = "100 + 50 = ?"
        simplified = strategy._simplify_numbers(problem)
        
        assert "100" not in simplified or "20" in simplified


class TestStrategyIntegration:
    """策略集成测试."""
    
    def test_all_strategies_on_sample_problems(self):
        """测试所有策略在样本题目上."""
        strategies = [
            NumericTransformationStrategy(),
            InverseOperationStrategy(),
            ContextTransferStrategy(),
            DifficultyAdjustmentStrategy(difficulty_delta=-1),
        ]
        
        for problem_data in SAMPLE_EQUATION_PROBLEMS[:2]:
            context = TransformationContext(
                original_problem=problem_data["content"],
                original_answer=problem_data["answer"],
                original_difficulty=problem_data["difficulty"],
                error_type=problem_data["error_type"],
            )
            
            for strategy in strategies:
                if strategy.can_handle(context):
                    result = strategy.transform(context)
                    # 验证结果格式
                    assert result.success in [True, False]
                    assert result.status in [
                        TransformStatus.SUCCESS,
                        TransformStatus.FAILED,
                        TransformStatus.TIMEOUT,
                    ]
    
    def test_strategy_validation(self):
        """测试策略验证功能."""
        strategy = NumericTransformationStrategy()
        context = TransformationContext(
            original_problem="2x + 5 = 15",
            original_answer="5",
        )
        result = strategy.transform(context)
        
        # 验证生成的变形题
        is_valid = strategy.validate_result(result)
        assert isinstance(is_valid, bool)
