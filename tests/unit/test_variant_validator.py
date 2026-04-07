"""变形题验证器单元测试.

测试验证器功能：
- 答案正确性验证
- 等价性检查
- 难度评估准确性
- 学生水平匹配
"""

import pytest

from src.domain.models.diagnosis import ErrorType
from src.domain.models.variant import GenerationStrategy, VariantProblem
from src.domain.engines.variant_validator import VariantValidator, ValidationResult
from src.domain.engines.credibility_rating import CredibilityFactors
from tests.fixtures.variant_fixtures import (
    create_sample_variant,
    SAMPLE_EQUATION_PROBLEMS,
    STUDENT_LEVELS,
)


class TestVariantValidator:
    """变形题验证器测试."""
    
    @pytest.fixture
    def validator(self):
        """创建验证器实例."""
        return VariantValidator(min_credibility_score=0.4)
    
    @pytest.fixture
    def valid_variant(self):
        """创建有效变形题."""
        return create_sample_variant(
            content="2x + 6 = 16，求x",
            answer="5",
            difficulty=3,
        )
    
    @pytest.fixture
    def invalid_variant(self):
        """创建无效变形题."""
        return create_sample_variant(
            content="",
            answer="",
            difficulty=3,
        )
    
    def test_validator_creation(self, validator):
        """测试验证器创建."""
        assert validator.min_credibility_score == 0.4
        assert validator.rater is not None
    
    def test_validate_valid_variant(self, validator, valid_variant):
        """测试验证有效变形题."""
        result = validator.validate(valid_variant)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_invalid_variant(self, validator, invalid_variant):
        """测试验证无效变形题."""
        result = validator.validate(invalid_variant)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
    
    def test_validate_content_empty(self, validator):
        """测试空内容验证."""
        variant = create_sample_variant(content="", answer="5")
        result = validator.validate(variant)
        
        assert result.is_valid is False
        assert any("内容" in e or "empty" in e.lower() for e in result.errors)
    
    def test_validate_content_too_short(self, validator):
        """测试内容过短验证."""
        variant = create_sample_variant(content="2x", answer="5")
        result = validator.validate(variant)
        
        assert result.is_valid is False
    
    def test_validate_content_too_long(self, validator):
        """测试内容过长验证."""
        variant = create_sample_variant(content="x" * 1001, answer="5")
        result = validator.validate(variant)
        
        assert any("过长" in e or "long" in e.lower() for e in result.errors)
    
    def test_validate_answer_empty(self, validator):
        """测试空答案验证."""
        variant = create_sample_variant(content="2x + 5 = 15", answer="")
        result = validator.validate(variant)
        
        assert result.is_valid is False
        assert any("答案" in e or "answer" in e.lower() for e in result.errors)
    
    def test_validate_answer_same_as_content(self, validator):
        """测试答案与内容相同."""
        content = "2x + 5 = 15"
        variant = create_sample_variant(content=content, answer=content)
        result = validator.validate(variant)
        
        assert any("相同" in e or "same" in e.lower() for e in result.errors)
    
    def test_answer_verified_flag(self, validator, valid_variant):
        """测试答案验证标志."""
        result = validator.validate(valid_variant)
        
        assert result.answer_verified is True
    
    def test_difficulty_assessed(self, validator, valid_variant):
        """测试难度评估."""
        result = validator.validate(valid_variant)
        
        assert result.difficulty_assessed is not None
        assert 1 <= result.difficulty_assessed <= 10
    
    def test_structure_score_with_original(self, validator, valid_variant):
        """测试与原题的结构评分."""
        original = "2x + 5 = 15"
        result = validator.validate(valid_variant, original_problem=original)
        
        assert result.structure_score > 0
    
    def test_equivalence_check(self, validator):
        """测试等价性检查."""
        original = "小明有5个苹果，给了小红2个，还剩几个？"
        variant = create_sample_variant(
            content="小华有5个橘子，给了小李2个，还剩几个？",
            answer="3",
        )
        
        result = validator.validate(variant, original_problem=original)
        
        # 结构应保持，数值相同
        assert result.structure_score >= 0.5
    
    def test_equivalence_warning_on_number_change(self, validator):
        """测试数值变化的警告."""
        original = "2x + 5 = 15"
        variant = create_sample_variant(
            content="3x + 8 = 20",  # 数值改变
            answer="4",
        )
        
        result = validator.validate(variant, original_problem=original)
        
        # 应该有警告
        assert len(result.warnings) > 0
    
    def test_student_level_match_beginner(self, validator):
        """测试初学者水平匹配."""
        variant = create_sample_variant(
            content="简单的题目",
            answer="5",
            difficulty=2,
        )
        result = validator.validate(variant, student_level="beginner")
        
        # 低难度题目匹配初学者
        assert result.credibility_rating.factors.student_level_match > 0.5
    
    def test_student_level_match_advanced(self, validator):
        """测试高级水平匹配."""
        variant = create_sample_variant(
            content="复杂证明题",
            answer="证明见解析",
            difficulty=9,
        )
        result = validator.validate(variant, student_level="advanced")
        
        # 高难度题目匹配高级学生
        assert result.credibility_rating.factors.student_level_match > 0.5
    
    def test_student_level_mismatch(self, validator):
        """测试水平不匹配."""
        variant = create_sample_variant(
            content="简单加法",
            answer="5",
            difficulty=2,
        )
        result = validator.validate(variant, student_level="advanced")
        
        # 低难度题目对高级学生来说太简单
        assert result.credibility_rating.factors.student_level_match < 0.5
    
    def test_credibility_rating_generation(self, validator, valid_variant):
        """测试可信度评分生成."""
        result = validator.validate(valid_variant)
        
        assert result.credibility_rating is not None
        assert 0 <= result.credibility_rating.score <= 1
        assert 1 <= result.credibility_rating.stars.value <= 5
    
    def test_min_credibility_threshold(self):
        """测试最小可信度阈值."""
        strict_validator = VariantValidator(min_credibility_score=0.9)
        
        # 创建一个中等质量的变形题
        variant = create_sample_variant(
            content="一般的题目",
            answer="10",
            difficulty=5,
        )
        
        result = strict_validator.validate(variant)
        
        # 可能因为可信度不足而无效
        if result.credibility_rating and result.credibility_rating.score < 0.9:
            assert result.is_valid is False


class TestDifficultyAssessment:
    """难度评估测试."""
    
    @pytest.fixture
    def validator(self):
        """创建验证器实例."""
        return VariantValidator()
    
    def test_assess_long_content_difficulty(self, validator):
        """测试长内容的难度增加."""
        variant = create_sample_variant(
            content="x" * 250,  # 长内容
            answer="5",
            difficulty=5,
        )
        assessed = validator._assess_difficulty(variant)
        
        assert assessed >= variant.difficulty
    
    def test_assess_short_content_difficulty(self, validator):
        """测试短内容的难度降低."""
        variant = create_sample_variant(
            content="2+3=?",  # 短内容
            answer="5",
            difficulty=5,
        )
        assessed = validator._assess_difficulty(variant)
        
        assert assessed <= variant.difficulty
    
    def test_hard_keywords_increase_difficulty(self, validator):
        """测试困难关键词增加难度."""
        variant = create_sample_variant(
            content="证明这个复杂的定理",
            answer="见解析",
            difficulty=5,
        )
        assessed = validator._assess_difficulty(variant)
        
        assert assessed > variant.difficulty
    
    def test_easy_keywords_decrease_difficulty(self, validator):
        """测试简单关键词降低难度."""
        variant = create_sample_variant(
            content="简单计算一步得出",
            answer="5",
            difficulty=5,
        )
        assessed = validator._assess_difficulty(variant)
        
        assert assessed < variant.difficulty
    
    def test_difficulty_bounds(self, validator):
        """测试难度边界."""
        variant_low = create_sample_variant(difficulty=1)
        variant_high = create_sample_variant(difficulty=10)
        
        assessed_low = validator._assess_difficulty(variant_low)
        assessed_high = validator._assess_difficulty(variant_high)
        
        assert 1 <= assessed_low <= 10
        assert 1 <= assessed_high <= 10


class TestStudentLevelMatching:
    """学生水平匹配测试."""
    
    @pytest.fixture
    def validator(self):
        """创建验证器实例."""
        return VariantValidator()
    
    def test_beginner_match(self, validator):
        """测试初学者匹配."""
        variant = create_sample_variant(difficulty=2)
        match = validator._assess_student_level_match(variant, "beginner")
        
        assert match == 1.0
    
    def test_advanced_match(self, validator):
        """测试高级学生匹配."""
        variant = create_sample_variant(difficulty=8)
        match = validator._assess_student_level_match(variant, "advanced")
        
        assert match == 1.0
    
    def test_average_match(self, validator):
        """测试平均水平匹配."""
        variant = create_sample_variant(difficulty=5)
        match = validator._assess_student_level_match(variant, "average")
        
        assert match == 1.0
    
    def test_beginner_too_hard(self, validator):
        """测试初学者题目过难."""
        variant = create_sample_variant(difficulty=8)
        match = validator._assess_student_level_match(variant, "beginner")
        
        assert match < 1.0
        assert match > 0.0  # 但仍有一定的匹配度
    
    def test_advanced_too_easy(self, validator):
        """测试高级学生题目太简单."""
        variant = create_sample_variant(difficulty=2)
        match = validator._assess_student_level_match(variant, "advanced")
        
        assert match < 1.0


class TestTextSimilarity:
    """文本相似度测试."""
    
    @pytest.fixture
    def validator(self):
        """创建验证器实例."""
        return VariantValidator()
    
    def test_identical_text_similarity(self, validator):
        """测试相同文本相似度."""
        text = "解方程 2x + 5 = 15"
        similarity = validator._calculate_text_similarity(text, text)
        
        assert similarity == 1.0
    
    def test_completely_different_text(self, validator):
        """测试完全不同文本."""
        text1 = "abc def"
        text2 = "xyz uvw"
        similarity = validator._calculate_text_similarity(text1, text2)
        
        assert similarity == 0.0
    
    def test_partial_similarity(self, validator):
        """测试部分相似."""
        text1 = "解方程 2x + 5 = 15"
        text2 = "解方程 3x + 7 = 20"
        similarity = validator._calculate_text_similarity(text1, text2)
        
        assert 0 < similarity < 1.0


class TestIntegration:
    """集成测试."""
    
    def test_full_validation_workflow(self):
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
        
        original = "2x + 5 = 15"
        
        # 验证
        result = validator.validate(
            variant,
            original_problem=original,
            student_level="average"
        )
        
        # 检查结果结构
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'warnings')
        assert hasattr(result, 'credibility_rating')
        assert hasattr(result, 'answer_verified')
        assert hasattr(result, 'difficulty_assessed')
        assert hasattr(result, 'structure_score')
