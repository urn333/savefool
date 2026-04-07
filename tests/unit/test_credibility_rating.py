"""可信度评分单元测试.

测试1-5星评分系统：
- 各factor计算正确性
- 综合星级计算
- 家长手动调整
- 历史数据校准
"""

import statistics
import pytest

from src.domain.engines.variant_credibility import (
    CredibilityFactors,
    CredibilityEvaluator,
    CredibilityRating,
    StarRating,
    CredibilityHistory,
)


class TestCredibilityFactors:
    """可信度因子测试."""
    
    def test_default_values(self):
        """测试默认值."""
        factors = CredibilityFactors()
        
        assert factors.semantic_equivalence == 0.0
        assert factors.difficulty_consistency == 0.0
        assert factors.solvability == 0.0
        assert factors.answer_validity == 0.0
        assert factors.student_level_match == 0.0
        assert factors.context_naturalness == 0.0
    
    def test_custom_values(self):
        """测试自定义值."""
        factors = CredibilityFactors(
            semantic_equivalence=0.8,
            difficulty_consistency=0.7,
            solvability=1.0,
        )
        
        assert factors.semantic_equivalence == 0.8
        assert factors.difficulty_consistency == 0.7
        assert factors.solvability == 1.0
    
    def test_value_validation(self):
        """测试值验证."""
        with pytest.raises(ValueError):
            CredibilityFactors(semantic_equivalence=1.5)  # 超出1.0
        
        with pytest.raises(ValueError):
            CredibilityFactors(solvability=-0.5)  # 低于0.0
    
    def test_average_score(self):
        """测试平均分计算."""
        factors = CredibilityFactors(
            semantic_equivalence=0.8,
            difficulty_consistency=0.8,
            solvability=0.8,
            answer_validity=0.8,
            student_level_match=0.8,
            context_naturalness=0.8,
        )
        
        assert abs(factors.average_score - 0.8) < 0.001
    
    def test_weighted_score(self):
        """测试加权分数计算."""
        factors = CredibilityFactors(
            semantic_equivalence=1.0,
            difficulty_consistency=1.0,
            solvability=1.0,
            answer_validity=1.0,
            student_level_match=1.0,
            context_naturalness=1.0,
        )
        
        # 所有因子满分，加权分数应为1.0
        assert factors.weighted_score == 1.0


class TestStarRating:
    """星级评分枚举测试."""
    
    def test_star_values(self):
        """测试星级值."""
        assert StarRating.ONE_STAR == 1
        assert StarRating.TWO_STARS == 2
        assert StarRating.THREE_STARS == 3
        assert StarRating.FOUR_STARS == 4
        assert StarRating.FIVE_STARS == 5
    
    def test_star_ordering(self):
        """测试星级排序."""
        assert StarRating.ONE_STAR < StarRating.TWO_STARS
        assert StarRating.TWO_STARS < StarRating.THREE_STARS
        assert StarRating.THREE_STARS < StarRating.FOUR_STARS
        assert StarRating.FOUR_STARS < StarRating.FIVE_STARS


class TestCredibilityRating:
    """可信度评分结果测试."""
    
    def test_default_creation(self):
        """测试默认创建."""
        rating = CredibilityRating()
        
        assert rating.stars == 3
        assert rating.ai_stars == 3
        assert rating.manual_stars is None
    
    def test_from_factors_excellent(self):
        """测试从因子创建5星评分."""
        factors = CredibilityFactors(
            semantic_equivalence=0.95,
            difficulty_consistency=0.90,
            solvability=1.0,
            answer_validity=1.0,
            student_level_match=0.95,
            context_naturalness=0.90,
        )
        
        rating = CredibilityRating.from_factors(factors)
        
        assert rating.ai_stars == 5
        assert rating.stars == 5
        assert rating.factors == factors
    
    def test_from_factors_poor(self):
        """测试从因子创建低星评分."""
        factors = CredibilityFactors(
            semantic_equivalence=0.3,
            difficulty_consistency=0.2,
            solvability=0.0,
            answer_validity=0.3,
            student_level_match=0.2,
            context_naturalness=0.2,
        )
        
        rating = CredibilityRating.from_factors(factors)
        
        assert rating.ai_stars == 1
        assert rating.stars == 1
    
    def test_adjust_rating_increase(self):
        """测试增加评分调整."""
        factors = CredibilityFactors(solvability=0.8, answer_validity=0.8)
        rating = CredibilityRating.from_factors(factors)
        
        original_stars = rating.stars
        rating.adjust_rating(5, reason="家长认为质量很好")
        
        assert rating.manual_stars == 5
        assert rating.stars == 5
        assert rating.adjustment_reason == "家长认为质量很好"
    
    def test_adjust_rating_decrease(self):
        """测试降低评分调整."""
        factors = CredibilityFactors(solvability=1.0, answer_validity=1.0)
        rating = CredibilityRating.from_factors(factors)
        
        rating.adjust_rating(2, reason="题目有误")
        
        assert rating.manual_stars == 2
        assert rating.stars == 2
    
    def test_adjust_rating_invalid(self):
        """测试无效评分调整."""
        rating = CredibilityRating()
        
        with pytest.raises(ValueError):
            rating.adjust_rating(6)  # 超出范围
        
        with pytest.raises(ValueError):
            rating.adjust_rating(0)  # 超出范围
    
    def test_get_rating_description(self):
        """测试评分描述."""
        rating_5 = CredibilityRating(stars=5)
        rating_1 = CredibilityRating(stars=1)
        
        assert "优秀" in rating_5.get_rating_description()
        assert "无法使用" in rating_1.get_rating_description()
    
    def test_to_dict(self):
        """测试转换为字典."""
        factors = CredibilityFactors(solvability=0.8)
        rating = CredibilityRating.from_factors(factors)
        
        data = rating.to_dict()
        
        assert "stars" in data
        assert "ai_stars" in data
        assert "factors" in data
        assert "description" in data


class TestCredibilityEvaluator:
    """可信度评估器测试."""
    
    @pytest.fixture
    def evaluator(self):
        """创建评估器实例."""
        return CredibilityEvaluator()
    
    @pytest.mark.asyncio
    async def test_evaluate_returns_rating(self, evaluator):
        """测试评估返回评分."""
        from src.domain.models.variant import VariantProblem
        from src.domain.models.diagnosis import Problem
        
        variant = VariantProblem(
            original_problem_id="test",
            content="2x + 5 = 15",
            difficulty=3,
            target_concept="algebra",
            error_type="calculation",
            strategy="value_substitution",
            answer="5",
        )
        
        original = Problem(
            content="2x + 6 = 16",
            subject="math",
            difficulty=3,
            answer="5",
        )
        
        rating = await evaluator.evaluate(variant, original, 0.5, 3)
        
        assert isinstance(rating, CredibilityRating)
        assert 1 <= rating.stars <= 5
        assert rating.factors is not None


class TestCredibilityHistory:
    """可信度历史记录测试."""
    
    def test_add_record(self):
        """测试添加记录."""
        history = CredibilityHistory()
        rating = CredibilityRating(stars=4, ai_stars=4)
        
        history.add_record("variant_001", rating)
        
        assert len(history._records) == 1
    
    def test_star_distribution(self):
        """测试星级分布."""
        history = CredibilityHistory()
        
        # 添加不同星级的记录
        for stars in [3, 4, 4, 5, 5, 5]:
            rating = CredibilityRating(stars=stars, ai_stars=stars)
            history.add_record(f"variant_{stars}", rating)
        
        distribution = history.get_star_distribution()
        
        assert distribution[3] == 1
        assert distribution[4] == 2
        assert distribution[5] == 3
    
    def test_calibration_data_no_records(self):
        """测试无记录时的校准数据."""
        history = CredibilityHistory()
        
        data = history.get_calibration_data()
        
        assert "error" in data
    
    def test_calibration_data_with_manual_ratings(self):
        """测试有手动评分时的校准数据."""
        history = CredibilityHistory()
        
        ai_rating = CredibilityRating(stars=4, ai_stars=4)
        manual_rating = CredibilityRating(stars=5, ai_stars=4, manual_stars=5)
        
        history.add_record("v1", ai_rating, manual_rating)
        
        data = history.get_calibration_data()
        
        assert data["total_records"] == 1
        assert data["manual_rated_records"] == 1


class TestStarThresholds:
    """星级阈值测试."""
    
    def test_five_star_threshold(self):
        """测试5星阈值."""
        # 刚好达到5星
        factors = CredibilityFactors(
            semantic_equivalence=0.90,
            difficulty_consistency=0.90,
            solvability=0.90,
            answer_validity=0.90,
            student_level_match=0.90,
            context_naturalness=0.90,
        )
        rating = CredibilityRating.from_factors(factors)
        
        assert rating.ai_stars == 5
    
    def test_four_star_boundary(self):
        """测试4星边界."""
        factors = CredibilityFactors(
            semantic_equivalence=0.75,
            difficulty_consistency=0.75,
            solvability=0.75,
            answer_validity=0.75,
            student_level_match=0.75,
            context_naturalness=0.75,
        )
        rating = CredibilityRating.from_factors(factors)
        
        assert rating.ai_stars == 4
    
    def test_one_star_boundary(self):
        """测试1星边界."""
        factors = CredibilityFactors(
            semantic_equivalence=0.39,
            solvability=0.30,
            answer_validity=0.39,
        )
        rating = CredibilityRating.from_factors(factors)
        
        assert rating.ai_stars == 1


class TestEdgeCases:
    """边界情况测试."""
    
    def test_all_zeros(self):
        """测试全零因子."""
        factors = CredibilityFactors(
            semantic_equivalence=0.0,
            difficulty_consistency=0.0,
            solvability=0.0,
            answer_validity=0.0,
            student_level_match=0.0,
            context_naturalness=0.0,
        )
        rating = CredibilityRating.from_factors(factors)
        
        assert rating.ai_stars == 1
    
    def test_all_ones(self):
        """测试全满分因子."""
        factors = CredibilityFactors(
            semantic_equivalence=1.0,
            difficulty_consistency=1.0,
            solvability=1.0,
            answer_validity=1.0,
            student_level_match=1.0,
            context_naturalness=1.0,
        )
        rating = CredibilityRating.from_factors(factors)
        
        assert rating.ai_stars == 5
        assert rating.factors.weighted_score == 1.0
