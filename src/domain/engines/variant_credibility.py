"""变形题可信度评分系统.

实现1-5星人工评分机制，支持AI自动评估和家长手动调整。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.domain.models.base import now_timestamp
from src.domain.models.diagnosis import ErrorType, Problem
from src.domain.models.variant import VariantProblem


class StarRating(int, Enum):
    """星级评分枚举."""
    
    ONE_STAR = 1      # ⭐ 无法使用，重新生成
    TWO_STARS = 2     # ⭐⭐ 勉强可用，有缺陷
    THREE_STARS = 3   # ⭐⭐⭐ 基本可用
    FOUR_STARS = 4    # ⭐⭐⭐⭐ 良好变形
    FIVE_STARS = 5    # ⭐⭐⭐⭐⭐ 优秀变形，可直接使用


@dataclass
class CredibilityFactors:
    """可信度评分因子.
    
    各因子取值范围为0-1，用于计算综合可信度。
    
    Attributes:
        semantic_equivalence: 语义等价性 - 变形题与原题在数学意义上的等价程度
        difficulty_consistency: 难度一致性 - 变形题难度与目标难度的匹配程度
        solvability: 可解性 - 变形题是否有明确、可计算的答案
        answer_validity: 答案有效性 - 提供的答案是否正确、合理
        student_level_match: 学生水平匹配 - 变形题是否适合学生当前水平
        context_naturalness: 情境自然度 - 变形题表述是否自然、符合常识
    """
    
    semantic_equivalence: float = 0.0
    difficulty_consistency: float = 0.0
    solvability: float = 0.0
    answer_validity: float = 0.0
    student_level_match: float = 0.0
    context_naturalness: float = 0.0
    
    def __post_init__(self):
        """验证因子值范围."""
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be in [0, 1], got {value}")
    
    def to_dict(self) -> Dict[str, float]:
        """转换为字典."""
        return {
            "semantic_equivalence": self.semantic_equivalence,
            "difficulty_consistency": self.difficulty_consistency,
            "solvability": self.solvability,
            "answer_validity": self.answer_validity,
            "student_level_match": self.student_level_match,
            "context_naturalness": self.context_naturalness,
        }
    
    @property
    def average_score(self) -> float:
        """计算因子平均分."""
        values = [
            self.semantic_equivalence,
            self.difficulty_consistency,
            self.solvability,
            self.answer_validity,
            self.student_level_match,
            self.context_naturalness,
        ]
        return sum(values) / len(values)
    
    @property
    def weighted_score(self) -> float:
        """计算加权分数.
        
        各因子权重：
        - semantic_equivalence: 0.25 (最重要)
        - answer_validity: 0.20
        - solvability: 0.20
        - difficulty_consistency: 0.15
        - student_level_match: 0.10
        - context_naturalness: 0.10
        """
        weights = {
            "semantic_equivalence": 0.25,
            "answer_validity": 0.20,
            "solvability": 0.20,
            "difficulty_consistency": 0.15,
            "student_level_match": 0.10,
            "context_naturalness": 0.10,
        }
        
        total = 0.0
        for field_name, weight in weights.items():
            total += getattr(self, field_name) * weight
        
        return total


@dataclass
class CredibilityRating:
    """可信度评分结果.
    
    包含AI自动评分和家长手动评分。
    
    Attributes:
        stars: 星级评分(1-5)
        ai_stars: AI自动评分
        manual_stars: 家长手动评分(None表示未手动评分)
        factors: 可信度因子评分
        confidence: AI评分的置信度
        rating_time: 评分时间
        rater_id: 评分者ID
        adjustment_reason: 手动调整原因
    """
    
    stars: int = field(default=3)
    ai_stars: int = field(default=3)
    manual_stars: Optional[int] = None
    factors: CredibilityFactors = field(default_factory=CredibilityFactors)
    confidence: float = field(default=0.5)
    rating_time: datetime = field(default_factory=now_timestamp)
    rater_id: Optional[str] = None
    adjustment_reason: Optional[str] = None
    
    # 详细评分说明
    rating_breakdown: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """验证星级范围."""
        for field_name in ["stars", "ai_stars", "manual_stars"]:
            value = getattr(self, field_name)
            if value is not None and not 1 <= value <= 5:
                raise ValueError(f"{field_name} must be in [1, 5], got {value}")
    
    @classmethod
    def from_factors(
        cls,
        factors: CredibilityFactors,
        confidence: float = 0.5,
        rater_id: Optional[str] = None,
    ) -> "CredibilityRating":
        """从因子评分创建可信度评分.
        
        Args:
            factors: 可信度因子
            confidence: AI置信度
            rater_id: 评分者ID
            
        Returns:
            可信度评分对象
        """
        # 根据加权分数计算星级
        weighted = factors.weighted_score
        ai_stars = cls._score_to_stars(weighted)
        
        return cls(
            stars=ai_stars,
            ai_stars=ai_stars,
            factors=factors,
            confidence=confidence,
            rater_id=rater_id,
            rating_breakdown={
                "weighted_score": weighted,
                "average_score": factors.average_score,
                "factors": factors.to_dict(),
            },
        )
    
    @staticmethod
    def _score_to_stars(score: float) -> int:
        """将分数转换为星级.
        
        评分标准：
        - 0.9-1.0: 5星 (优秀)
        - 0.75-0.9: 4星 (良好)
        - 0.6-0.75: 3星 (基本可用)
        - 0.4-0.6: 2星 (勉强可用)
        - 0-0.4: 1星 (无法使用)
        
        Args:
            score: 分数(0-1)
            
        Returns:
            星级(1-5)
        """
        if score >= 0.90:
            return 5
        elif score >= 0.75:
            return 4
        elif score >= 0.60:
            return 3
        elif score >= 0.40:
            return 2
        else:
            return 1
    
    def adjust_rating(
        self,
        new_stars: int,
        reason: Optional[str] = None,
        rater_id: Optional[str] = None,
    ) -> None:
        """手动调整评分.
        
        Args:
            new_stars: 新评分
            reason: 调整原因
            rater_id: 评分者ID
        """
        if not 1 <= new_stars <= 5:
            raise ValueError(f"new_stars must be in [1, 5], got {new_stars}")
        
        self.manual_stars = new_stars
        self.stars = new_stars  # 手动评分优先
        self.adjustment_reason = reason
        if rater_id:
            self.rater_id = rater_id
        self.rating_time = now_timestamp()
    
    def get_rating_description(self) -> str:
        """获取评分描述.
        
        Returns:
            评分描述文本
        """
        descriptions = {
            1: "⭐ (1星): 无法使用，需要重新生成",
            2: "⭐⭐ (2星): 勉强可用，有明显缺陷",
            3: "⭐⭐⭐ (3星): 基本可用，可以给学生练习",
            4: "⭐⭐⭐⭐ (4星): 良好变形，推荐使用",
            5: "⭐⭐⭐⭐⭐ (5星): 优秀变形，可直接使用",
        }
        return descriptions.get(self.stars, "未知评分")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "stars": self.stars,
            "ai_stars": self.ai_stars,
            "manual_stars": self.manual_stars,
            "description": self.get_rating_description(),
            "factors": self.factors.to_dict(),
            "confidence": self.confidence,
            "rating_time": self.rating_time.isoformat(),
            "rater_id": self.rater_id,
            "adjustment_reason": self.adjustment_reason,
            "rating_breakdown": self.rating_breakdown,
        }


class CredibilityEvaluator:
    """可信度评估器.
    
    负责对变形题进行AI自动可信度评估。
    """
    
    def __init__(self, model_client: Optional[Any] = None):
        """初始化评估器.
        
        Args:
            model_client: 可选的模型客户端
        """
        self.model_client = model_client
    
    async def evaluate(
        self,
        variant: VariantProblem,
        original: Problem,
        student_level: float,
        target_difficulty: int,
    ) -> CredibilityRating:
        """评估变形题可信度.
        
        Args:
            variant: 变形题
            original: 原题
            student_level: 学生水平
            target_difficulty: 目标难度
            
        Returns:
            可信度评分
        """
        # 评估各因子
        factors = CredibilityFactors(
            semantic_equivalence=self._evaluate_semantic_equivalence(
                variant, original
            ),
            difficulty_consistency=self._evaluate_difficulty_consistency(
                variant, target_difficulty
            ),
            solvability=self._evaluate_solvability(variant),
            answer_validity=self._evaluate_answer_validity(variant, original),
            student_level_match=self._evaluate_student_level_match(
                variant, student_level
            ),
            context_naturalness=self._evaluate_context_naturalness(variant),
        )
        
        # 计算AI置信度
        confidence = self._calculate_confidence(factors)
        
        # 创建评分
        rating = CredibilityRating.from_factors(
            factors=factors,
            confidence=confidence,
        )
        
        return rating
    
    def _evaluate_semantic_equivalence(
        self,
        variant: VariantProblem,
        original: Problem,
    ) -> float:
        """评估语义等价性.
        
        评估变形题与原题在数学意义上是否等价。
        
        Args:
            variant: 变形题
            original: 原题
            
        Returns:
            等价性分数(0-1)
        """
        score = 1.0
        
        # 1. 检查运算符一致性
        variant_ops = set(c for c in variant.content if c in "+-×÷*/=＋－＊／")
        original_ops = set(c for c in original.content if c in "+-×÷*/=＋－＊／")
        
        if variant_ops != original_ops:
            # 运算符不一致，可能是逆运算变形，降低但不完全扣分
            score -= 0.1
        
        # 2. 检查知识点一致性
        if variant.target_concept in original.knowledge_points:
            score += 0.1
        else:
            score -= 0.1
        
        # 3. 检查结构相似度
        # 提取数字并比较数量
        import re
        variant_nums = len(re.findall(r'\d+', variant.content))
        original_nums = len(re.findall(r'\d+', original.content))
        
        if abs(variant_nums - original_nums) > 1:
            score -= 0.1
        
        # 4. 检查是否有答案
        if variant.answer and original.answer:
            score += 0.05
        elif not variant.answer and original.answer:
            score -= 0.2
        
        return min(1.0, max(0.0, score))
    
    def _evaluate_difficulty_consistency(
        self,
        variant: VariantProblem,
        target_difficulty: int,
    ) -> float:
        """评估难度一致性.
        
        Args:
            variant: 变形题
            target_difficulty: 目标难度
            
        Returns:
            一致性分数(0-1)
        """
        actual_difficulty = variant.difficulty
        diff = abs(actual_difficulty - target_difficulty)
        
        # 难度差越小分数越高
        if diff == 0:
            return 1.0
        elif diff == 1:
            return 0.9
        elif diff == 2:
            return 0.7
        elif diff == 3:
            return 0.5
        else:
            return 0.3
    
    def _evaluate_solvability(self, variant: VariantProblem) -> float:
        """评估可解性.
        
        Args:
            variant: 变形题
            
        Returns:
            可解性分数(0-1)
        """
        score = 0.0
        
        # 1. 检查题目内容
        if variant.content and len(variant.content.strip()) >= 10:
            score += 0.3
        
        # 2. 检查问题完整性
        question_markers = ["?", "？", "多少", "几", "求", "计算"]
        if any(marker in variant.content for marker in question_markers):
            score += 0.3
        
        # 3. 检查是否有答案
        if variant.answer:
            score += 0.4
        elif variant.solution:
            score += 0.2
        
        return min(1.0, score)
    
    def _evaluate_answer_validity(
        self,
        variant: VariantProblem,
        original: Problem,
    ) -> float:
        """评估答案有效性.
        
        Args:
            variant: 变形题
            original: 原题
            
        Returns:
            有效性分数(0-1)
        """
        if not variant.answer:
            return 0.5  # 无答案时给中等分
        
        score = 0.5
        
        # 1. 检查答案格式
        answer = str(variant.answer).strip()
        
        # 检查是否为数字
        try:
            float(answer)
            score += 0.3
        except (ValueError, TypeError):
            # 非数字答案，检查是否有合理解释
            if len(answer) > 0:
                score += 0.1
        
        # 2. 检查答案合理性
        # 提取变形题中的数字
        import re
        content_nums = [float(n) for n in re.findall(r'\d+\.?\d*', variant.content)]
        
        if content_nums and variant.answer:
            try:
                ans_val = float(variant.answer)
                # 答案应该在合理范围内
                max_content = max(content_nums) if content_nums else 1
                min_content = min(content_nums) if content_nums else 0
                
                if min_content <= ans_val <= max_content * 10:
                    score += 0.2
            except (ValueError, TypeError):
                pass
        
        return min(1.0, score)
    
    def _evaluate_student_level_match(
        self,
        variant: VariantProblem,
        student_level: float,
    ) -> float:
        """评估学生水平匹配度.
        
        Args:
            variant: 变形题
            student_level: 学生水平(0-1)
            
        Returns:
            匹配度分数(0-1)
        """
        # 将难度(1-10)映射到学生水平(0-1)
        difficulty_level = variant.difficulty / 10.0
        
        # 计算差距
        gap = abs(difficulty_level - student_level)
        
        # 差距越小越匹配
        if gap <= 0.1:
            return 1.0
        elif gap <= 0.2:
            return 0.9
        elif gap <= 0.3:
            return 0.7
        elif gap <= 0.4:
            return 0.5
        else:
            return 0.3
    
    def _evaluate_context_naturalness(self, variant: VariantProblem) -> float:
        """评估情境自然度.
        
        Args:
            variant: 变形题
            
        Returns:
            自然度分数(0-1)
        """
        content = variant.content
        score = 0.5
        
        # 1. 检查是否有奇怪的量词搭配
        unnatural_patterns = [
            r"\d+只\s*[汽飞卡]",
            r"\d+辆\s*[苹橙梨]",
            r"\d+本\s*[铅橡尺]",
        ]
        
        for pattern in unnatural_patterns:
            if __import__("re").search(pattern, content):
                score -= 0.2
        
        # 2. 检查句子流畅度
        # 连续标点
        if __import__("re").search(r"[，,\.。]\s*[，,\.。]", content):
            score -= 0.1
        
        # 3. 检查是否有完整的问题结构
        if "?" in content or "？" in content:
            score += 0.2
        
        # 4. 检查长度合理性
        if 20 <= len(content) <= 200:
            score += 0.1
        elif len(content) > 300:
            score -= 0.1
        
        return min(1.0, max(0.0, score))
    
    def _calculate_confidence(self, factors: CredibilityFactors) -> float:
        """计算AI评估的置信度.
        
        基于各因子的一致性计算置信度。
        
        Args:
            factors: 可信度因子
            
        Returns:
            置信度(0-1)
        """
        values = [
            factors.semantic_equivalence,
            factors.difficulty_consistency,
            factors.solvability,
            factors.answer_validity,
            factors.student_level_match,
            factors.context_naturalness,
        ]
        
        # 计算标准差
        avg = sum(values) / len(values)
        variance = sum((v - avg) ** 2 for v in values) / len(values)
        std_dev = variance ** 0.5
        
        # 标准差越小，置信度越高
        # 标准差0 -> 置信度1.0
        # 标准差0.5 -> 置信度0.5
        confidence = 1.0 - std_dev * 2
        
        return min(1.0, max(0.0, confidence))


class CredibilityHistory:
    """可信度历史记录.
    
    记录和管理历史评分数据，用于模型校准。
    """
    
    def __init__(self):
        """初始化历史记录."""
        self._records: List[Dict[str, Any]] = []
    
    def add_record(
        self,
        variant_id: str,
        ai_rating: CredibilityRating,
        manual_rating: Optional[CredibilityRating] = None,
    ) -> None:
        """添加评分记录.
        
        Args:
            variant_id: 变形题ID
            ai_rating: AI评分
            manual_rating: 手动评分
        """
        record = {
            "variant_id": variant_id,
            "ai_rating": ai_rating.to_dict(),
            "manual_rating": manual_rating.to_dict() if manual_rating else None,
            "timestamp": now_timestamp().isoformat(),
        }
        self._records.append(record)
    
    def get_calibration_data(self) -> Dict[str, Any]:
        """获取校准数据.
        
        Returns:
            校准统计数据
        """
        if not self._records:
            return {"error": "No records available"}
        
        # 统计AI评分和手动评分的差异
        differences = []
        for record in self._records:
            if record["manual_rating"]:
                ai_stars = record["ai_rating"]["stars"]
                manual_stars = record["manual_rating"]["stars"]
                differences.append(abs(ai_stars - manual_stars))
        
        if not differences:
            return {"error": "No manual ratings available"}
        
        return {
            "total_records": len(self._records),
            "manual_rated_records": len(differences),
            "average_difference": sum(differences) / len(differences),
            "max_difference": max(differences),
            "exact_match_rate": sum(1 for d in differences if d == 0) / len(differences),
            "within_1_star_rate": sum(1 for d in differences if d <= 1) / len(differences),
        }
    
    def get_star_distribution(self) -> Dict[int, int]:
        """获取星级分布.
        
        Returns:
            各星级数量统计
        """
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        
        for record in self._records:
            stars = record["ai_rating"]["stars"]
            if stars in distribution:
                distribution[stars] += 1
        
        return distribution
