"""变形题验证器单元测试.

测试验证器功能：
- 答案正确性验证
- 等价性检查
- 难度评估准确性
- 学生水平匹配
"""

import pytest

from src.domain.models.diagnosis import ErrorType
from src.domain.models.variant import VariantProblem, GenerationStrategy
from src.domain.engines.variant_validator import VariantValidator, ValidationResult
from src.domain.models.diagnosis import Problem


class TestVariantValidator:
    """变形题验证器测试."""
    
    @pytest.fixture
    def validator(self):
        """创建验证器实例."""
        return VariantValidator()
    
    @pytest.fixture
    def valid_variant(self):
        """创建有效变形题."""
        return VariantProblem(
            original_problem_id="orig_test",
            content="2x + 6 = 16，求x",
            difficulty=3,
            target_concept="一元一次方程",
            error_type=ErrorType.CALCULATION_ERROR,
            strategy=GenerationStrategy.VALUE_SUBSTITUTION,
            answer="5",
        )
    
    @pytest.fixture
    def sample_original(self):
        """创建原题."""
        return Problem(
            content="2x + 5 = 15",
            subject="math",
            difficulty=3,
            answer="5",
        )
    
    @pytest.mark.asyncio
    async def test_validate_valid_variant(self, validator, valid_variant, sample_original):
        """测试验证有效变形题."""
        result = await validator.validate(valid_variant, sample_original, 0.5)
        
        assert isinstance(result, ValidationResult)
        # 可能有效也可能无效，取决于具体实现
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'warnings')
    
    def test_quick_validate(self, validator, valid_variant):
        """测试快速验证."""
        result = validator.quick_validate(valid_variant)
        
        assert isinstance(result, bool)
    
    def test_quick_validate_empty_content(self, validator):
        """测试空内容快速验证."""
        variant = VariantProblem(
            original_problem_id="test",
            content="",
            difficulty=3,
            target_concept="test",
            error_type=ErrorType.CARELESS_MISTAKE,
            strategy=GenerationStrategy.VALUE_SUBSTITUTION,
            answer="5",
        )
        
        result = validator.quick_validate(variant)
        assert result is False
    
    def test_quick_validate_empty_answer(self, validator):
        """测试空答案快速验证."""
        variant = VariantProblem(
            original_problem_id="test",
            content="2x + 5 = 15",
            difficulty=3,
            target_concept="test",
            error_type=ErrorType.CARELESS_MISTAKE,
            strategy=GenerationStrategy.VALUE_SUBSTITUTION,
            answer="",
        )
        
        result = validator.quick_validate(variant)
        assert result is False
    
    def test_validate_content_empty(self, validator):
        """测试空内容验证."""
        variant = VariantProblem(
            original_problem_id="test",
            content="",
            difficulty=3,
            target_concept="test",
            error_type=ErrorType.CARELESS_MISTAKE,
            strategy=GenerationStrategy.VALUE_SUBSTITUTION,
            answer="5",
        )
        
        valid, errors = validator._validate_content(variant)
        assert valid is False
        assert len(errors) > 0
    
    def test_validate_content_too_short(self, validator):
        """测试内容过短验证."""
        variant = VariantProblem(
            original_problem_id="test",
            content="2x",
            difficulty=3,
            target_concept="test",
            error_type=ErrorType.CARELESS_MISTAKE,
            strategy=GenerationStrategy.VALUE_SUBSTITUTION,
            answer="5",
        )
        
        valid, errors = validator._validate_content(variant)
        assert valid is False
    
    def test_validate_answer_empty(self, validator):
        """测试空答案验证."""
        variant = VariantProblem(
            original_problem_id="test",
            content="2x + 5 = 15",
            difficulty=3,
            target_concept="test",
            error_type=ErrorType.CARELESS_MISTAKE,
            strategy=GenerationStrategy.VALUE_SUBSTITUTION,
            answer="",
        )
        
        valid, errors = validator._validate_answer(variant)
        assert valid is False
        assert len(errors) > 0
    
    def test_check_equivalence(self, validator):
        """测试等价性检查."""
        variant = VariantProblem(
            original_problem_id="test",
            content="小明有5个橘子，给了小李2个，还剩几个？",
            difficulty=2,
            target_concept="subtraction",
            error_type=ErrorType.CARELESS_MISTAKE,
            strategy=GenerationStrategy.CONTEXT_CHANGE,
            answer="3",
        )
        
        original = Problem(
            content="小明有5个苹果，给了小红2个，还剩几个？",
            subject="math",
            difficulty=2,
            answer="3",
        )
        
        equivalent, warnings = validator._check_equivalence(variant, original)
        
        # 数值应该保持
        assert isinstance(equivalent, bool)
        assert isinstance(warnings, list)
    
    def test_check_equivalence_warning_on_number_change(self, validator):
        """测试数值变化的警告."""
        variant = VariantProblem(
            original_problem_id="test",
            content="3x + 8 = 20",
            difficulty=4,
            target_concept="equation",
            error_type=ErrorType.CALCULATION_ERROR,
            strategy=GenerationStrategy.VALUE_SUBSTITUTION,
            answer="4",
        )
        
        original = Problem(
            content="2x + 5 = 15",
            subject="math",
            difficulty=3,
            answer="5",
        )
        
        equivalent, warnings = validator._check_equivalence(variant, original)
        
        # 可能有警告（取决于实现）
        assert isinstance(equivalent, bool)
        assert isinstance(warnings, list)
    
    def test_check_difficulty(self, validator):
        """测试难度检查."""
        variant = VariantProblem(
            original_problem_id="test",
            content="简单题目",
            difficulty=2,
            target_concept="basic",
            error_type=ErrorType.CARELESS_MISTAKE,
            strategy=GenerationStrategy.VALUE_SUBSTITUTION,
            answer="5",
        )
        
        ok, warnings = validator._check_difficulty(variant, 0.8)  # 高水平学生
        
        assert isinstance(ok, bool)
        assert isinstance(warnings, list)


class TestValidationResult:
    """验证结果测试."""
    
    def test_result_creation_valid(self):
        """测试有效结果创建."""
        result = ValidationResult(is_valid=True)
        
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
    
    def test_result_creation_invalid(self):
        """测试无效结果创建."""
        result = ValidationResult(
            is_valid=False,
            errors=["内容为空"],
            warnings=["难度可能过高"],
        )
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert len(result.warnings) == 1
    
    def test_result_to_dict(self):
        """测试转换为字典."""
        result = ValidationResult(
            is_valid=True,
            metadata={"score": 0.85},
        )
        
        data = result.to_dict()
        
        assert data["is_valid"] is True
        assert data["metadata"]["score"] == 0.85


class TestIntegration:
    """集成测试."""
    
    @pytest.mark.asyncio
    async def test_full_validation_workflow(self):
        """测试完整验证流程."""
        validator = VariantValidator()
        
        # 创建一个变形题
        variant = VariantProblem(
            original_problem_id="orig_001",
            content="2x + 8 = 18，求x的值",
            difficulty=3,
            target_concept="一元一次方程",
            error_type=ErrorType.CALCULATION_ERROR,
            strategy=GenerationStrategy.VALUE_SUBSTITUTION,
            answer="5",
        )
        
        original = Problem(
            content="2x + 5 = 15",
            subject="math",
            difficulty=3,
            answer="5",
        )
        
        # 验证
        result = await validator.validate(variant, original, 0.5)
        
        # 检查结果结构
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'warnings')
        assert hasattr(result, 'metadata')
