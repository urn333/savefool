"""错误归因分析引擎.

功能追溯ID: F-DIAG-002
基于历史数据进行错误归因，识别知识缺口，
区分粗心、方法错误、概念漏洞，计算归因置信度。
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from src.infrastructure.logging import get_logger
from src.domain.models.diagnosis import ErrorType
from src.domain.memory.memory_manager import MemoryManager, MemoryQuery
from src.domain.models.base import now_timestamp

logger = get_logger(__name__)


@dataclass
class AttributionFactor:
    """归因因子.
    
    Attributes:
        factor_type: 因子类型
        description: 描述
        weight: 权重
        evidence: 证据列表
    """
    factor_type: str
    description: str
    weight: float
    evidence: List[str] = field(default_factory=list)


@dataclass
class ErrorAttributionResult:
    """错误归因结果.
    
    Attributes:
        problem_id: 题目ID
        student_id: 学生ID
        primary_cause: 主要原因
        secondary_causes: 次要原因
        error_type: 错误类型
        confidence: 归因置信度
        knowledge_gaps: 知识缺口列表
        is_careless_pattern: 是否是粗心模式
        historical_similarity: 历史相似度
        factors: 归因因子列表
        recommendations: 建议列表
    """
    problem_id: str
    student_id: str
    primary_cause: str
    secondary_causes: List[str] = field(default_factory=list)
    error_type: Optional[ErrorType] = None
    confidence: float = 0.0
    knowledge_gaps: List[str] = field(default_factory=list)
    is_careless_pattern: bool = False
    historical_similarity: float = 0.0
    factors: List[AttributionFactor] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class ErrorAttributionEngine:
    """错误归因分析引擎.
    
    基于历史数据和当前错误特征进行归因分析：
    1. 基于历史数据归因 - 查找相似历史错误
    2. 知识缺口识别 - 分析知识点掌握情况
    3. 粗心 vs 方法错误 vs 概念漏洞区分
    4. 归因置信度计算
    
    Example:
        >>> engine = ErrorAttributionEngine(memory_manager)
        >>> result = await engine.analyze(
        ...     student_id="stu_123",
        ...     problem_id="prob_456",
        ...     error_type=ErrorType.CALCULATION_ERROR,
        ...     concept_ids=["fraction_addition", "common_denominator"],
        ... )
    """
    
    # 归因类型
    CAUSE_TYPES = {
        "historical_pattern": "历史错误模式",
        "knowledge_gap": "知识缺口",
        "careless_habit": "粗心习惯",
        "method_error": "方法错误",
        "concept_misunderstanding": "概念误解",
        "situational_factor": "情境因素",
        "transfer_failure": "知识迁移失败",
    }
    
    def __init__(self, memory_manager: MemoryManager):
        """初始化归因引擎.
        
        Args:
            memory_manager: 记忆管理器
        """
        self.memory_manager = memory_manager
        self.logger = get_logger(__name__)
    
    async def analyze(
        self,
        student_id: str,
        problem_id: str,
        error_type: ErrorType,
        concept_ids: List[str],
        student_answer: Optional[str] = None,
        correct_answer: Optional[str] = None,
    ) -> ErrorAttributionResult:
        """分析错误归因.
        
        Args:
            student_id: 学生ID
            problem_id: 题目ID
            error_type: 错误类型
            concept_ids: 相关概念ID列表
            student_answer: 学生答案（可选）
            correct_answer: 正确答案（可选）
            
        Returns:
            归因分析结果
        """
        self.logger.info(
            "attribution_analysis_start",
            student_id=student_id,
            problem_id=problem_id,
            error_type=error_type.value,
        )
        
        # 获取学生记忆快照
        memory_snapshot = await self.memory_manager.get_snapshot(
            student_id=student_id,
            include_episodes=True,
            episode_hours=168,  # 最近7天
        )
        
        factors = []
        
        # 1. 分析历史模式
        historical_factor = await self._analyze_historical_pattern(
            student_id, error_type, concept_ids, memory_snapshot
        )
        if historical_factor:
            factors.append(historical_factor)
        
        # 2. 分析知识缺口
        knowledge_factor = await self._analyze_knowledge_gaps(
            student_id, concept_ids, memory_snapshot
        )
        if knowledge_factor:
            factors.append(knowledge_factor)
        
        # 3. 分析粗心模式
        careless_factor = await self._analyze_careless_pattern(
            student_id, error_type, student_answer, correct_answer, memory_snapshot
        )
        if careless_factor:
            factors.append(careless_factor)
        
        # 4. 分析方法错误
        method_factor = await self._analyze_method_error(
            student_id, error_type, concept_ids, memory_snapshot
        )
        if method_factor:
            factors.append(method_factor)
        
        # 5. 分析情境因素
        situational_factor = await self._analyze_situational_factors(
            student_id, memory_snapshot
        )
        if situational_factor:
            factors.append(situational_factor)
        
        # 综合归因
        primary_cause, secondary_causes = self._determine_primary_cause(
            factors, error_type
        )
        
        # 计算置信度
        confidence = self._calculate_attribution_confidence(
            factors, error_type, memory_snapshot
        )
        
        # 识别知识缺口
        knowledge_gaps = self._extract_knowledge_gaps(factors, concept_ids)
        
        # 检查是否为粗心模式
        is_careless_pattern = self._check_careless_pattern(factors)
        
        # 计算历史相似度
        historical_similarity = self._calculate_historical_similarity(factors)
        
        # 生成建议
        recommendations = self._generate_recommendations(
            primary_cause, factors, knowledge_gaps, is_careless_pattern
        )
        
        result = ErrorAttributionResult(
            problem_id=problem_id,
            student_id=student_id,
            primary_cause=primary_cause,
            secondary_causes=secondary_causes,
            error_type=error_type,
            confidence=confidence,
            knowledge_gaps=knowledge_gaps,
            is_careless_pattern=is_careless_pattern,
            historical_similarity=historical_similarity,
            factors=factors,
            recommendations=recommendations,
        )
        
        self.logger.info(
            "attribution_analysis_complete",
            student_id=student_id,
            problem_id=problem_id,
            primary_cause=primary_cause,
            confidence=confidence,
        )
        
        return result
    
    async def _analyze_historical_pattern(
        self,
        student_id: str,
        error_type: ErrorType,
        concept_ids: List[str],
        memory_snapshot: Any,
    ) -> Optional[AttributionFactor]:
        """分析历史错误模式.
        
        Args:
            student_id: 学生ID
            error_type: 错误类型
            concept_ids: 概念ID列表
            memory_snapshot: 记忆快照
            
        Returns:
            归因因子
        """
        if not memory_snapshot.recent_episodes:
            return None
        
        # 查找相似历史错误
        similar_errors = []
        
        for episode in memory_snapshot.recent_episodes:
            if episode.final_result != "correct" and episode.error_type:
                # 检查错误类型是否相同
                if episode.error_type == error_type.value:
                    similar_errors.append(episode)
                # 检查是否有相同概念
                elif concept_ids and episode.concept_ids:
                    if set(concept_ids) & set(episode.concept_ids):
                        similar_errors.append(episode)
        
        if not similar_errors:
            return None
        
        # 计算模式强度
        pattern_strength = min(1.0, len(similar_errors) / 5.0)  # 最多5次为满分
        
        evidence = [
            f"最近7天内类似错误{len(similar_errors)}次",
        ]
        
        # 添加具体例子
        for i, err in enumerate(similar_errors[:3]):
            evidence.append(f"  - {err.timestamp.strftime('%m-%d')}: {err.error_type}")
        
        return AttributionFactor(
            factor_type="historical_pattern",
            description=self.CAUSE_TYPES["historical_pattern"],
            weight=0.3 * pattern_strength,
            evidence=evidence,
        )
    
    async def _analyze_knowledge_gaps(
        self,
        student_id: str,
        concept_ids: List[str],
        memory_snapshot: Any,
    ) -> Optional[AttributionFactor]:
        """分析知识缺口.
        
        Args:
            student_id: 学生ID
            concept_ids: 概念ID列表
            memory_snapshot: 记忆快照
            
        Returns:
            归因因子
        """
        gaps = []
        evidence = []
        
        # 从知识图谱检查概念掌握度
        if memory_snapshot.knowledge_graph:
            for concept in memory_snapshot.knowledge_graph.concepts:
                if concept.id in concept_ids:
                    if concept.mastery_level < 0.6:
                        gaps.append(concept.id)
                        evidence.append(
                            f"{concept.name}: 掌握度{concept.mastery_level:.0%}"
                        )
        
        # 从待处理缺口检查
        if memory_snapshot.pending_gaps:
            for gap in memory_snapshot.pending_gaps:
                if any(cid in gap.related_knowledge for cid in concept_ids):
                    gaps.append(gap.gap_type)
                    evidence.append(f"待验证缺口: {gap.gap_type}")
        
        if not gaps:
            return None
        
        gap_weight = min(1.0, len(gaps) / 3.0)
        
        return AttributionFactor(
            factor_type="knowledge_gap",
            description=self.CAUSE_TYPES["knowledge_gap"],
            weight=0.35 * gap_weight,
            evidence=evidence,
        )
    
    async def _analyze_careless_pattern(
        self,
        student_id: str,
        error_type: ErrorType,
        student_answer: Optional[str],
        correct_answer: Optional[str],
        memory_snapshot: Any,
    ) -> Optional[AttributionFactor]:
        """分析粗心模式.
        
        Args:
            student_id: 学生ID
            error_type: 错误类型
            student_answer: 学生答案
            correct_answer: 正确答案
            memory_snapshot: 记忆快照
            
        Returns:
            归因因子
        """
        evidence = []
        weight = 0.0
        
        # 检查错误类型是否为粗心
        if error_type == ErrorType.CARELESS_MISTAKE:
            weight += 0.4
            evidence.append("错误类型标记为粗心")
        
        # 检查答案差异是否为细小差异
        if student_answer and correct_answer:
            similarity = self._calculate_similarity(student_answer, correct_answer)
            if similarity > 0.8:
                weight += 0.3
                evidence.append(f"答案相似度{similarity:.0%}，可能是粗心")
        
        # 检查历史粗心频率
        if memory_snapshot.recent_episodes:
            careless_count = sum(
                1 for ep in memory_snapshot.recent_episodes
                if ep.error_type == ErrorType.CARELESS_MISTAKE.value
            )
            if careless_count >= 3:
                weight += 0.2
                evidence.append(f"最近粗心错误{careless_count}次")
        
        if weight == 0:
            return None
        
        return AttributionFactor(
            factor_type="careless_habit",
            description=self.CAUSE_TYPES["careless_habit"],
            weight=weight,
            evidence=evidence,
        )
    
    async def _analyze_method_error(
        self,
        student_id: str,
        error_type: ErrorType,
        concept_ids: List[str],
        memory_snapshot: Any,
    ) -> Optional[AttributionFactor]:
        """分析方法错误.
        
        Args:
            student_id: 学生ID
            error_type: 错误类型
            concept_ids: 概念ID列表
            memory_snapshot: 记忆快照
            
        Returns:
            归因因子
        """
        evidence = []
        weight = 0.0
        
        # 逻辑错误通常是方法问题
        if error_type == ErrorType.LOGICAL_FLAW:
            weight += 0.4
            evidence.append("逻辑推理错误")
        
        # 计算错误可能是方法不熟练
        if error_type == ErrorType.CALCULATION_ERROR:
            weight += 0.2
            evidence.append("计算错误可能是方法不熟练")
        
        # 检查ZPD边界
        if memory_snapshot.profile:
            zpd = memory_snapshot.profile.zpd_boundary
            # 如果题目难度刚好在ZPD边缘，可能是方法应用困难
            weight += 0.1
            evidence.append(f"当前ZPD边界: {zpd.lower_bound:.1f}-{zpd.upper_bound:.1f}")
        
        if weight == 0:
            return None
        
        return AttributionFactor(
            factor_type="method_error",
            description=self.CAUSE_TYPES["method_error"],
            weight=weight,
            evidence=evidence,
        )
    
    async def _analyze_situational_factors(
        self,
        student_id: str,
        memory_snapshot: Any,
    ) -> Optional[AttributionFactor]:
        """分析情境因素.
        
        Args:
            student_id: 学生ID
            memory_snapshot: 记忆快照
            
        Returns:
            归因因子
        """
        evidence = []
        
        # 检查最近活动强度
        if memory_snapshot.recent_episodes:
            recent_count = len(memory_snapshot.recent_episodes)
            if recent_count > 10:
                evidence.append(f"最近7天答题{recent_count}次，可能疲劳")
            
            # 检查时间分布
            timestamps = [ep.timestamp for ep in memory_snapshot.recent_episodes]
            if timestamps:
                time_spread = max(timestamps) - min(timestamps)
                if time_spread.days < 1:
                    evidence.append("答题时间集中，可能赶时间")
        
        if not evidence:
            return None
        
        return AttributionFactor(
            factor_type="situational_factor",
            description=self.CAUSE_TYPES["situational_factor"],
            weight=0.15,
            evidence=evidence,
        )
    
    def _determine_primary_cause(
        self,
        factors: List[AttributionFactor],
        error_type: ErrorType,
    ) -> Tuple[str, List[str]]:
        """确定主要原因.
        
        Args:
            factors: 归因因子列表
            error_type: 错误类型
            
        Returns:
            (主要原因, 次要原因列表)
        """
        if not factors:
            return "未知原因", []
        
        # 按权重排序
        sorted_factors = sorted(factors, key=lambda f: f.weight, reverse=True)
        
        primary = sorted_factors[0].description
        secondary = [f.description for f in sorted_factors[1:3]]
        
        return primary, secondary
    
    def _calculate_attribution_confidence(
        self,
        factors: List[AttributionFactor],
        error_type: ErrorType,
        memory_snapshot: Any,
    ) -> float:
        """计算归因置信度.
        
        Args:
            factors: 归因因子
            error_type: 错误类型
            memory_snapshot: 记忆快照
            
        Returns:
            置信度
        """
        if not factors:
            return 0.3
        
        # 基础置信度
        base_confidence = 0.5
        
        # 因子数量加成
        factor_bonus = min(0.2, len(factors) * 0.05)
        
        # 权重总和加成
        total_weight = sum(f.weight for f in factors)
        weight_bonus = min(0.3, total_weight * 0.3)
        
        # 历史数据充足度
        data_bonus = 0.0
        if memory_snapshot.recent_episodes:
            episode_count = len(memory_snapshot.recent_episodes)
            data_bonus = min(0.2, episode_count / 50.0)
        
        confidence = base_confidence + factor_bonus + weight_bonus + data_bonus
        return min(1.0, round(confidence, 4))
    
    def _extract_knowledge_gaps(
        self,
        factors: List[AttributionFactor],
        concept_ids: List[str],
    ) -> List[str]:
        """提取知识缺口.
        
        Args:
            factors: 归因因子
            concept_ids: 概念ID
            
        Returns:
            知识缺口列表
        """
        gaps = []
        
        for factor in factors:
            if factor.factor_type == "knowledge_gap":
                for ev in factor.evidence:
                    # 提取概念名称
                    if ":" in ev:
                        gap_name = ev.split(":")[0].strip()
                        if gap_name not in gaps:
                            gaps.append(gap_name)
        
        # 如果没有提取到，使用概念ID
        if not gaps and concept_ids:
            gaps = [cid.replace("_", " ") for cid in concept_ids[:3]]
        
        return gaps[:5]  # 最多5个
    
    def _check_careless_pattern(self, factors: List[AttributionFactor]) -> bool:
        """检查是否为粗心模式.
        
        Args:
            factors: 归因因子
            
        Returns:
            是否是粗心模式
        """
        for factor in factors:
            if factor.factor_type == "careless_habit":
                return factor.weight > 0.5
        return False
    
    def _calculate_historical_similarity(
        self,
        factors: List[AttributionFactor],
    ) -> float:
        """计算历史相似度.
        
        Args:
            factors: 归因因子
            
        Returns:
            相似度分数
        """
        for factor in factors:
            if factor.factor_type == "historical_pattern":
                return min(1.0, factor.weight / 0.3)
        return 0.0
    
    def _generate_recommendations(
        self,
        primary_cause: str,
        factors: List[AttributionFactor],
        knowledge_gaps: List[str],
        is_careless_pattern: bool,
    ) -> List[str]:
        """生成建议.
        
        Args:
            primary_cause: 主要原因
            factors: 归因因子
            knowledge_gaps: 知识缺口
            is_careless_pattern: 是否是粗心模式
            
        Returns:
            建议列表
        """
        recommendations = []
        
        # 基于主要原因的建议
        if "粗心" in primary_cause:
            recommendations.append("建议做题时放慢速度，仔细审题")
            recommendations.append("可以尝试做完后反向验算")
        elif "知识" in primary_cause or "概念" in primary_cause:
            if knowledge_gaps:
                recommendations.append(f"重点复习：{', '.join(knowledge_gaps[:2])}")
            recommendations.append("建议先巩固基础知识再做变式练习")
        elif "方法" in primary_cause:
            recommendations.append("建议回顾标准解题步骤")
            recommendations.append("可以尝试一题多解，加深理解")
        
        # 针对粗心的特殊建议
        if is_careless_pattern and "粗心" not in primary_cause:
            recommendations.append("注意：你最近粗心错误较多，请保持专注")
        
        # 添加通用建议
        if len(recommendations) < 3:
            recommendations.append("建议整理错题本，定期复习")
        
        return recommendations[:3]
    
    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """计算两个字符串的相似度.
        
        使用简单的编辑距离比例。
        
        Args:
            s1: 字符串1
            s2: 字符串2
            
        Returns:
            相似度(0-1)
        """
        # 简化实现：基于共同字符比例
        set1 = set(s1.lower())
        set2 = set(s2.lower())
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
