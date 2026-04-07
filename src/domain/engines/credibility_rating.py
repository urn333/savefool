"""可信度评分模块.

实现变形题的可信度评分，支持1-5星评级。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class StarRating(int, Enum):
    """星级评分枚举."""
    
    UNUSABLE = 1  # 1星 - 无法使用
    POOR = 2      # 2星 - 质量较差
    FAIR = 3      # 3星 - 一般
    GOOD = 4      # 4星 - 良好
    EXCELLENT = 5 # 5星 - 优秀


@dataclass
class CredibilityFactors:
    """可信度因子.
    
    影响变形题质量的各维度评分。
    
    Attributes:
        semantic_similarity: 语义相似度 (0-1)
        difficulty_match: 难度匹配度 (0-1)
        solvability: 可解性 (0-1)
        validity: 有效性/正确性 (0-1)
        student_level_match: 学生水平匹配度 (0-1)
        structure_preservation: 结构保持度 (0-1)
    """
    
    semantic_similarity: float = 0.0  # 语义相似度
    difficulty_match: float = 0.0      # 难度匹配
    solvability: float = 0.0           # 可解性
    validity: float = 0.0              # 有效性
    student_level_match: float = 0.0   # 学生水平匹配
    structure_preservation: float = 0.0 # 结构保持
    
    def __post_init__(self):
        """验证并限制值范围."""
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            setattr(self, field_name, max(0.0, min(1.0, float(value))))


@dataclass
class CredibilityRating:
    """可信度评分结果.
    
    Attributes:
        stars: 星级评分 (1-5)
        score: 原始分数 (0-1)
        factors: 各维度评分
        confidence: 评分离散度
        explanation: 评分解释
        adjusted_by_parent: 是否被家长调整
        parent_adjustment: 家长调整值
    """
    
    stars: StarRating = StarRating.UNUSABLE
    score: float = 0.0
    factors: CredibilityFactors = field(default_factory=CredibilityFactors)
    confidence: float = 0.0
    explanation: str = ""
    adjusted_by_parent: bool = False
    parent_adjustment: Optional[int] = None
    historical_calibration: Optional[float] = None


class CredibilityRater:
    """可信度评分器.
    
    对变形题进行多维度的质量评估，输出1-5星评级。
    
    Example:
        >>> rater = CredibilityRater()
        >>> factors = CredibilityFactors(
        ...     semantic_similarity=0.95,
        ...     difficulty_match=0.90,
        ...     solvability=1.0,
        ...     validity=1.0,
        ...     student_level_match=0.95,
        ... )
        >>> rating = rater.calculate_rating(factors)
        >>> assert rating.stars == StarRating.EXCELLENT
    """
    
    # 权重配置
    DEFAULT_WEIGHTS = {
        "semantic_similarity": 0.20,
        "difficulty_match": 0.15,
        "solvability": 0.25,
        "validity": 0.25,
        "student_level_match": 0.10,
        "structure_preservation": 0.05,
    }
    
    # 星级阈值
    STAR_THRESHOLDS = {
        StarRating.EXCELLENT: 0.90,  # 5星: >= 0.90
        StarRating.GOOD: 0.75,       # 4星: >= 0.75
        StarRating.FAIR: 0.60,       # 3星: >= 0.60
        StarRating.POOR: 0.40,       # 2星: >= 0.40
        StarRating.UNUSABLE: 0.0,    # 1星: < 0.40
    }
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """初始化评分器.
        
        Args:
            weights: 自定义权重配置
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.logger = get_logger(__name__)
        
        # 验证权重和
        total_weight = sum(self.weights.values())
        if abs(total_weight - 1.0) > 0.01:
            logger.warning("Weights do not sum to 1.0", total=total_weight)
    
    def calculate_rating(
        self,
        factors: CredibilityFactors,
        history_data: Optional[List[float]] = None,
    ) -> CredibilityRating:
        """计算可信度评分.
        
        Args:
            factors: 可信度因子
            history_data: 历史评分数据（用于校准）
            
        Returns:
            可信度评分结果
        """
        # 计算加权分数
        score = self._calculate_weighted_score(factors)
        
        # 应用历史校准
        calibration = None
        if history_data and len(history_data) >= 5:
            calibration = self._apply_historical_calibration(score, history_data)
            score = calibration
        
        # 计算星级
        stars = self._score_to_stars(score)
        
        # 计算置信度（评分离散度）
        confidence = self._calculate_confidence(factors)
        
        # 生成解释
        explanation = self._generate_explanation(factors, stars, score)
        
        return CredibilityRating(
            stars=stars,
            score=round(score, 4),
            factors=factors,
            confidence=round(confidence, 4),
            explanation=explanation,
            historical_calibration=round(calibration, 4) if calibration else None,
        )
    
    def adjust_by_parent(
        self,
        rating: CredibilityRating,
        parent_rating: int,
    ) -> CredibilityRating:
        """家长手动调整评分.
        
        Args:
            rating: 原评分
            parent_rating: 家长评分 (1-5)
            
        Returns:
            调整后的评分
        """
        if not 1 <= parent_rating <= 5:
            raise ValueError(f"Parent rating must be between 1 and 5, got {parent_rating}")
        
        # 计算家长评分和系统评分的差异
        system_stars = rating.stars.value
        difference = parent_rating - system_stars
        
        # 根据差异调整分数
        # 差异越大，调整越谨慎
        adjustment_factor = min(abs(difference) * 0.1, 0.2)
        
        if difference > 0:
            # 家长评分更高
            new_score = min(1.0, rating.score + adjustment_factor)
        else:
            # 家长评分更低
            new_score = max(0.0, rating.score - adjustment_factor)
        
        new_stars = self._score_to_stars(new_score)
        
        return CredibilityRating(
            stars=new_stars,
            score=round(new_score, 4),
            factors=rating.factors,
            confidence=rating.confidence,
            explanation=f"{rating.explanation} [家长调整: {system_stars}→{parent_rating}]",
            adjusted_by_parent=True,
            parent_adjustment=parent_rating,
        )
    
    def _calculate_weighted_score(self, factors: CredibilityFactors) -> float:
        """计算加权分数.
        
        Args:
            factors: 可信度因子
            
        Returns:
            加权分数 (0-1)
        """
        score = 0.0
        
        score += factors.semantic_similarity * self.weights["semantic_similarity"]
        score += factors.difficulty_match * self.weights["difficulty_match"]
        score += factors.solvability * self.weights["solvability"]
        score += factors.validity * self.weights["validity"]
        score += factors.student_level_match * self.weights["student_level_match"]
        score += factors.structure_preservation * self.weights["structure_preservation"]
        
        return score
    
    def _apply_historical_calibration(
        self,
        current_score: float,
        history_data: List[float],
    ) -> float:
        """应用历史校准.
        
        使用历史数据校准当前评分。
        
        Args:
            current_score: 当前评分
            history_data: 历史评分数据
            
        Returns:
            校准后的评分
        """
        import statistics
        
        # 计算历史平均值
        history_mean = statistics.mean(history_data)
        
        # 计算历史标准差
        if len(history_data) >= 2:
            history_std = statistics.stdev(history_data)
        else:
            history_std = 0.1
        
        # 如果当前评分偏离历史均值超过1个标准差，向均值靠拢
        deviation = current_score - history_mean
        if abs(deviation) > history_std:
            calibration_factor = 0.2  # 校准因子
            calibrated = current_score - deviation * calibration_factor
            return max(0.0, min(1.0, calibrated))
        
        return current_score
    
    def _score_to_stars(self, score: float) -> StarRating:
        """将分数转换为星级.
        
        Args:
            score: 分数 (0-1)
            
        Returns:
            星级评分
        """
        if score >= self.STAR_THRESHOLDS[StarRating.EXCELLENT]:
            return StarRating.EXCELLENT
        elif score >= self.STAR_THRESHOLDS[StarRating.GOOD]:
            return StarRating.GOOD
        elif score >= self.STAR_THRESHOLDS[StarRating.FAIR]:
            return StarRating.FAIR
        elif score >= self.STAR_THRESHOLDS[StarRating.POOR]:
            return StarRating.POOR
        else:
            return StarRating.UNUSABLE
    
    def _calculate_confidence(self, factors: CredibilityFactors) -> float:
        """计算评分离散度（置信度）.
        
        因子得分越集中，置信度越高。
        
        Args:
            factors: 可信度因子
            
        Returns:
            置信度 (0-1)
        """
        values = [
            factors.semantic_similarity,
            factors.difficulty_match,
            factors.solvability,
            factors.validity,
            factors.student_level_match,
            factors.structure_preservation,
        ]
        
        import statistics
        
        if len(values) < 2:
            return 1.0
        
        # 使用标准差衡量离散度
        try:
            std_dev = statistics.stdev(values)
            # 标准差越小，置信度越高
            confidence = 1.0 - min(std_dev * 2, 1.0)
            return max(0.0, confidence)
        except statistics.StatisticsError:
            return 1.0
    
    def _generate_explanation(
        self,
        factors: CredibilityFactors,
        stars: StarRating,
        score: float,
    ) -> str:
        """生成评分解释.
        
        Args:
            factors: 可信度因子
            stars: 星级
            score: 分数
            
        Returns:
            解释文本
        """
        explanations = []
        
        # 总体评价
        star_names = {
            StarRating.EXCELLENT: "优秀",
            StarRating.GOOD: "良好",
            StarRating.FAIR: "一般",
            StarRating.POOR: "较差",
            StarRating.UNUSABLE: "无法使用",
        }
        
        explanations.append(f"总体评价: {star_names[stars]} ({score:.0%})")
        
        # 突出优势和不足
        factor_names = {
            "semantic_similarity": "语义相似度",
            "difficulty_match": "难度匹配",
            "solvability": "可解性",
            "validity": "有效性",
            "student_level_match": "学生水平匹配",
            "structure_preservation": "结构保持",
        }
        
        factor_values = {
            "semantic_similarity": factors.semantic_similarity,
            "difficulty_match": factors.difficulty_match,
            "solvability": factors.solvability,
            "validity": factors.validity,
            "student_level_match": factors.student_level_match,
            "structure_preservation": factors.structure_preservation,
        }
        
        # 找出最高分因子
        best_factor = max(factor_values.items(), key=lambda x: x[1])
        if best_factor[1] >= 0.8:
            explanations.append(f"优势: {factor_names[best_factor[0]]}优秀({best_factor[1]:.0%})")
        
        # 找出最低分因子
        worst_factor = min(factor_values.items(), key=lambda x: x[1])
        if worst_factor[1] < 0.6:
            explanations.append(f"待改进: {factor_names[worst_factor[0]]}较低({worst_factor[1]:.0%})")
        
        return " | ".join(explanations)


def calculate_stars(
    semantic: float = 0.0,
    difficulty: float = 0.0,
    solvability: float = 0.0,
    validity: float = 0.0,
    match: float = 0.0,
    structure: float = 0.0,
) -> int:
    """便捷函数：计算星级.
    
    Args:
        semantic: 语义相似度
        difficulty: 难度匹配度
        solvability: 可解性
        validity: 有效性
        match: 学生水平匹配度
        structure: 结构保持度
        
    Returns:
        星级 (1-5)
    """
    factors = CredibilityFactors(
        semantic_similarity=semantic,
        difficulty_match=difficulty,
        solvability=solvability,
        validity=validity,
        student_level_match=match,
        structure_preservation=structure,
    )
    
    rater = CredibilityRater()
    rating = rater.calculate_rating(factors)
    return rating.stars.value
