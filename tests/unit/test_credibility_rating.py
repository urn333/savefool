"""可信度评分单元测试.

测试1-5星评分系统：
- 各factor计算正确性
- 综合星级计算
- 家长手动调整
- 历史数据校准
"""

import statistics
import pytest

from src.domain.engines.credibility_rating import (
    CredibilityFactors,
    CredibilityRater,
    CredibilityRating,
    StarRating,
    calculate_stars,
)
from tests.fixtures.variant_fixtures import (
    CREDIBILITY_TEST_CASES,
    CREDIBILITY_EDGE_CASES,
)


class TestCredibilityFactors:
    """可信度因子测试."""
    
    def test_default_values(self):
        """测试默认值."""
        factors = CredibilityFactors()
        
        assert factors.semantic_similarity == 0.0
        assert factors.difficulty_match == 0.0
        assert factors.solvability == 0.0
        assert factors.validity == 0.0
        assert factors.student_level_match == 0.0
        assert factors.structure_preservation == 0.0
    
    def test_custom_values(self):
        """测试自定义值."""
        factors = CredibilityFactors(
            semantic_similarity=0.8,
            difficulty_match=0.7,
            solvability=1.0,
        )
        
        assert factors.semantic_similarity == 0.8
        assert factors.difficulty_match == 0.7
        assert factors.solvability == 1.0
    
    def test_value_clamping_upper(self):
        """测试值上限截断."""
        factors = CredibilityFactors(
            semantic_similarity=1.5,  # 超出1.0
            solvability=2.0,          # 超出1.0
        )
        
        assert factors.semantic_similarity == 1.0
        assert factors.solvability == 1.0
    
    def test_value_clamping_lower(self):
        """测试值下限截断."""
        factors = CredibilityFactors(
            semantic_similarity=-0.5,  # 低于0.0
            solvability=-1.0,          # 低于0.0
        )
        
        assert factors.semantic_similarity == 0.0
        assert factors.solvability == 0.0


class TestStarRating:
    """星级评分枚举测试."""
    
    def test_star_values(self):
        """测试星级值."""
        assert StarRating.UNUSABLE == 1
        assert StarRating.POOR == 2
        assert StarRating.FAIR == 3
        assert StarRating.GOOD == 4
        assert StarRating.EXCELLENT == 5
    
    def test_star_ordering(self):
        """测试星级排序."""
        assert StarRating.UNUSABLE < StarRating.POOR
        assert StarRating.POOR < StarRating.FAIR
        assert StarRating.FAIR < StarRating.GOOD
        assert StarRating.GOOD < StarRating.EXCELLENT


class TestCredibilityRater:
    """可信度评分器测试."""
    
    @pytest.fixture
    def rater(self):
        """创建评分器实例."""
        return CredibilityRater()
    
    @pytest.fixture
    def excellent_factors(self):
        """创建5星因子."""
        return CredibilityFactors(
            semantic_similarity=0.95,
            difficulty_match=0.90,
            solvability=1.0,
            validity=1.0,
            student_level_match=0.95,
            structure_preservation=0.90,
        )
    
    def test_default_weights_sum_to_one(self, rater):
        """测试默认权重和为1."""
        total = sum(rater.DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01
    
    def test_calculate_excellent_rating(self, rater, excellent_factors):
        """测试5星评分计算."""
        rating = rater.calculate_rating(excellent_factors)
        
        assert rating.stars == StarRating.EXCELLENT
        assert rating.score >= 0.90
        assert rating.factors == excellent_factors
    
    def test_calculate_poor_rating(self, rater):
        """测试2星评分计算."""
        factors = CredibilityFactors(
            semantic_similarity=0.50,
            difficulty_match=0.45,
            solvability=0.70,
            validity=0.60,
            student_level_match=0.40,
            structure_preservation=0.50,
        )
        rating = rater.calculate_rating(factors)
        
        assert rating.stars == StarRating.POOR
        assert 0.40 <= rating.score < 0.60
    
    def test_calculate_unusable_rating(self, rater):
        """测试1星评分计算."""
        factors = CredibilityFactors(
            semantic_similarity=0.30,
            solvability=0.0,
            validity=0.30,
        )
        rating = rater.calculate_rating(factors)
        
        assert rating.stars == StarRating.UNUSABLE
        assert rating.score < 0.40
    
    def test_score_calculation_correctness(self, rater):
        """测试分数计算正确性."""
        factors = CredibilityFactors(
            semantic_similarity=1.0,
            difficulty_match=1.0,
            solvability=1.0,
            validity=1.0,
            student_level_match=1.0,
            structure_preservation=1.0,
        )
        rating = rater.calculate_rating(factors)
        
        # 满分应该是1.0
        assert abs(rating.score - 1.0) < 0.01
    
    def test_confidence_calculation(self, rater):
        """测试置信度计算."""
        # 各因子一致，置信度高
        uniform_factors = CredibilityFactors(
            semantic_similarity=0.8,
            difficulty_match=0.8,
            solvability=0.8,
            validity=0.8,
            student_level_match=0.8,
            structure_preservation=0.8,
        )
        rating = rater.calculate_rating(uniform_factors)
        assert rating.confidence > 0.5
        
        # 各因子差异大，置信度低
        varied_factors = CredibilityFactors(
            semantic_similarity=1.0,
            difficulty_match=0.2,
            solvability=1.0,
            validity=0.2,
            student_level_match=1.0,
            structure_preservation=0.2,
        )
        rating2 = rater.calculate_rating(varied_factors)
        assert rating2.confidence < rating.confidence
    
    def test_explanation_generation(self, rater, excellent_factors):
        """测试解释生成."""
        rating = rater.calculate_rating(excellent_factors)
        
        assert len(rating.explanation) > 0
        assert "优秀" in rating.explanation or "良好" in rating.explanation
    
    def test_parent_adjustment_increase(self, rater, excellent_factors):
        """测试家长增加评分."""
        rating = rater.calculate_rating(excellent_factors)
        original_stars = rating.stars.value
        
        # 家长给出更高评分
        adjusted = rater.adjust_by_parent(rating, 5)
        
        assert adjusted.adjusted_by_parent is True
        assert adjusted.parent_adjustment == 5
    
    def test_parent_adjustment_decrease(self, rater, excellent_factors):
        """测试家长降低评分."""
        rating = rater.calculate_rating(excellent_factors)
        
        # 家长给出更低评分
        adjusted = rater.adjust_by_parent(rating, 3)
        
        assert adjusted.adjusted_by_parent is True
        assert adjusted.parent_adjustment == 3
        assert adjusted.score <= rating.score  # 分数应该降低或不变
    
    def test_parent_adjustment_invalid(self, rater, excellent_factors):
        """测试无效的家长评分."""
        rating = rater.calculate_rating(excellent_factors)
        
        with pytest.raises(ValueError):
            rater.adjust_by_parent(rating, 6)  # 超出范围
        
        with pytest.raises(ValueError):
            rater.adjust_by_parent(rating, 0)  # 超出范围
    
    def test_historical_calibration(self, rater):
        """测试历史数据校准."""
        factors = CredibilityFactors(
            semantic_similarity=0.85,
            difficulty_match=0.80,
            solvability=0.90,
            validity=0.85,
            student_level_match=0.80,
            structure_preservation=0.85,
        )
        
        # 提供历史数据
        history = [0.75, 0.78, 0.76, 0.77, 0.79]  # 历史评分偏低
        rating = rater.calculate_rating(factors, history)
        
        # 应该有历史校准值
        assert rating.historical_calibration is not None


class TestStarThresholds:
    """星级阈值测试."""
    
    def test_five_star_threshold(self):
        """测试5星阈值."""
        # 刚好达到5星
        factors = CredibilityFactors(
            semantic_similarity=0.90,
            difficulty_match=0.90,
            solvability=0.90,
            validity=0.90,
            student_level_match=0.90,
            structure_preservation=0.90,
        )
        rater = CredibilityRater()
        rating = rater.calculate_rating(factors)
        
        assert rating.stars == StarRating.EXCELLENT
    
    def test_four_star_boundary(self):
        """测试4星边界."""
        # 刚好低于5星
        factors = CredibilityFactors(
            semantic_similarity=0.75,
            difficulty_match=0.75,
            solvability=0.75,
            validity=0.75,
            student_level_match=0.75,
            structure_preservation=0.75,
        )
        rater = CredibilityRater()
        rating = rater.calculate_rating(factors)
        
        assert rating.stars == StarRating.GOOD
    
    def test_one_star_boundary(self):
        """测试1星边界."""
        # 刚好达到1星上限
        factors = CredibilityFactors(
            semantic_similarity=0.39,
            solvability=0.50,
            validity=0.39,
        )
        rater = CredibilityRater()
        rating = rater.calculate_rating(factors)
        
        assert rating.stars == StarRating.UNUSABLE


class TestCalculateStarsFunction:
    """便捷函数测试."""
    
    def test_calculate_stars_excellent(self):
        """测试5星计算."""
        stars = calculate_stars(
            semantic=0.95,
            difficulty=0.90,
            solvability=1.0,
            validity=1.0,
            match=0.95,
        )
        assert stars == 5
    
    def test_calculate_stars_unusable(self):
        """测试1星计算."""
        stars = calculate_stars(
            semantic=0.3,
            solvability=0.0,
        )
        assert stars == 1
    
    def test_calculate_stars_with_defaults(self):
        """测试使用默认值的计算."""
        stars = calculate_stars(
            semantic=0.8,
            solvability=0.9,
            validity=0.85,
        )
        # 其他因子使用默认值0，可能影响星级
        assert isinstance(stars, int)
        assert 1 <= stars <= 5


class TestCredibilityEdgeCases:
    """边界情况测试."""
    
    def test_all_zeros(self):
        """测试全零因子."""
        factors = CredibilityFactors(
            semantic_similarity=0.0,
            difficulty_match=0.0,
            solvability=0.0,
            validity=0.0,
            student_level_match=0.0,
            structure_preservation=0.0,
        )
        rater = CredibilityRater()
        rating = rater.calculate_rating(factors)
        
        assert rating.stars == StarRating.UNUSABLE
        assert rating.score == 0.0
    
    def test_all_ones(self):
        """测试全满分因子."""
        factors = CredibilityFactors(
            semantic_similarity=1.0,
            difficulty_match=1.0,
            solvability=1.0,
            validity=1.0,
            student_level_match=1.0,
            structure_preservation=1.0,
        )
        rater = CredibilityRater()
        rating = rater.calculate_rating(factors)
        
        assert rating.stars == StarRating.EXCELLENT
        assert rating.score == 1.0
    
    def test_partial_factors(self):
        """测试部分因子."""
        factors = CredibilityFactors(
            solvability=1.0,
            validity=1.0,
        )
        rater = CredibilityRater()
        rating = rater.calculate_rating(factors)
        
        # 只有部分因子有值，评分应该中等
        assert rating.score > 0
        assert rating.score < 0.8  # 因为其他因子为0
    
    def test_negative_values_clamped(self):
        """测试负值被截断."""
        factors = CredibilityFactors(
            semantic_similarity=-1.0,
            solvability=-0.5,
            validity=0.5,
        )
        
        assert factors.semantic_similarity == 0.0
        assert factors.solvability == 0.0
        assert factors.validity == 0.5


class TestTestCasesFromFixtures:
    """使用fixtures的测试用例."""
    
    @pytest.mark.parametrize("test_case", CREDIBILITY_TEST_CASES)
    def test_expected_stars(self, test_case):
        """测试预期星级."""
        factors = CredibilityFactors(**test_case["factors"])
        rater = CredibilityRater()
        rating = rater.calculate_rating(factors)
        
        assert rating.stars.value == test_case["expected_stars"], \
            f"Failed for {test_case['name']}: expected {test_case['expected_stars']} stars, got {rating.stars.value}"
        
        # 验证分数范围
        min_score, max_score = test_case["expected_score_range"]
        assert min_score <= rating.score <= max_score, \
            f"Score {rating.score} not in range ({min_score}, {max_score}) for {test_case['name']}"
    
    @pytest.mark.parametrize("test_case", CREDIBILITY_EDGE_CASES)
    def test_edge_cases(self, test_case):
        """测试边界情况."""
        factors = CredibilityFactors(**test_case["factors"])
        rater = CredibilityRater()
        rating = rater.calculate_rating(factors)
        
        assert rating.stars.value == test_case["expected_stars"], \
            f"Failed for {test_case['name']}"
        
        if test_case.get("expected_clamped"):
            # 验证值被正确截断到0-1范围
            assert 0.0 <= rating.score <= 1.0
