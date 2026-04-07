"""仲裁决策引擎.

实现多模型结果的仲裁逻辑，包括共识判断和分歧处理。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.infrastructure.logging import get_logger
from src.domain.models.arbitration import ArbitrationResult, ModelResult, ModelVote
from src.domain.models.diagnosis import ErrorType

logger = get_logger(__name__)


class ArbitrationStatus(str, Enum):
    """仲裁状态."""
    CONSENSUS = "consensus"      # 达成共识
    DIVERGENCE = "divergence"    # 存在分歧
    PARTIAL = "partial"          # 部分模型失败
    FAILED = "failed"            # 仲裁失败


@dataclass
class ArbitrationConfig:
    """仲裁配置.
    
    Attributes:
        consensus_threshold: 共识阈值(≥2/3)
        weights: 各模型权重
        min_confidence: 最小置信度
        enable_conflict_utilization: 是否利用冲突信息
    """
    consensus_threshold: float = 2/3
    weights: Dict[str, float] = field(default_factory=lambda: {
        "model_a": 0.4,
        "model_b": 0.4,
        "model_c": 0.2,
    })
    min_confidence: float = 0.5
    enable_conflict_utilization: bool = True


@dataclass
class ConflictInfo:
    """冲突信息.
    
    Attributes:
        has_conflict: 是否存在冲突
        conflict_type: 冲突类型
        conflicting_models: 冲突的模型
        conflict_details: 冲突详情
    """
    has_conflict: bool = False
    conflict_type: Optional[str] = None
    conflicting_models: List[str] = field(default_factory=list)
    conflict_details: Dict[str, Any] = field(default_factory=dict)


class ArbitrationEngine:
    """仲裁决策引擎.
    
    根据三模型结果进行仲裁决策：
    - 共识判断：≥2/3模型一致 → 采用多数结果
    - 分歧处理：全部分歧 → 标记"待验证"
    - 权重应用：按配置权重计算
    - 冲突利用：将分歧本身作为诊断选项
    
    Example:
        >>> engine = ArbitrationEngine(config)
        >>> result = engine.arbitrate(
        ...     problem_id="prob_123",
        ...     model_results=[result_a, result_b, result_c],
        ... )
    """
    
    def __init__(self, config: Optional[ArbitrationConfig] = None):
        """初始化仲裁引擎.
        
        Args:
            config: 仲裁配置
        """
        self.config = config or ArbitrationConfig()
        self.logger = get_logger(__name__)
    
    def arbitrate(
        self,
        problem_id: str,
        model_results: List[ModelResult],
    ) -> ArbitrationResult:
        """执行仲裁决策.
        
        Args:
            problem_id: 题目ID
            model_results: 各模型结果列表
            
        Returns:
            仲裁结果
        """
        self.logger.info(
            "arbitration_start",
            problem_id=problem_id,
            model_count=len(model_results),
        )
        
        if not model_results:
            self.logger.error("no_model_results", problem_id=problem_id)
            return self._create_failed_result(problem_id, "No model results available")
        
        # 分析共识
        consensus_analysis = self._analyze_consensus(model_results)
        is_consensus = consensus_analysis["is_consensus"]
        majority_correct = consensus_analysis["majority_correct"]
        consensus_ratio = consensus_analysis["consensus_ratio"]
        
        # 检测冲突
        conflict_info = self._detect_conflict(model_results)
        
        # 计算加权置信度
        weighted_confidence = self._calculate_weighted_confidence(model_results)
        
        # 确定最终错误类型
        final_error_type = self._determine_error_type(model_results, consensus_analysis)
        
        # 构建模型投票
        model_votes = self._build_model_votes(model_results)
        
        # 确定仲裁状态
        if is_consensus:
            status = ArbitrationStatus.CONSENSUS
        elif consensus_ratio > 0:
            status = ArbitrationStatus.PARTIAL
        else:
            status = ArbitrationStatus.DIVERGENCE
        
        self.logger.info(
            "arbitration_complete",
            problem_id=problem_id,
            status=status.value,
            is_consensus=is_consensus,
            consensus_ratio=consensus_ratio,
            final_result=majority_correct,
        )
        
        return ArbitrationResult(
            problem_id=problem_id,
            is_correct=majority_correct,
            error_type=final_error_type,
            confidence=weighted_confidence,
            model_votes=model_votes,
            is_consensus=is_consensus,
            consensus_ratio=consensus_ratio,
            conflict_info=conflict_info.__dict__ if conflict_info.has_conflict else None,
            used_models=[r.model_id for r in model_results],
        )
    
    def _analyze_consensus(
        self,
        model_results: List[ModelResult],
    ) -> Dict[str, Any]:
        """分析模型共识.
        
        Args:
            model_results: 模型结果列表
            
        Returns:
            共识分析结果
        """
        if not model_results:
            return {
                "is_consensus": False,
                "majority_correct": True,
                "consensus_ratio": 0.0,
            }
        
        total = len(model_results)
        correct_count = sum(1 for r in model_results if r.is_correct)
        incorrect_count = total - correct_count
        
        # 判断是否达成共识（≥2/3）
        correct_ratio = correct_count / total
        incorrect_ratio = incorrect_count / total
        
        if correct_ratio >= self.config.consensus_threshold:
            is_consensus = True
            majority_correct = True
            consensus_ratio = correct_ratio
        elif incorrect_ratio >= self.config.consensus_threshold:
            is_consensus = True
            majority_correct = False
            consensus_ratio = incorrect_ratio
        else:
            is_consensus = False
            majority_correct = correct_count > incorrect_count
            consensus_ratio = max(correct_ratio, incorrect_ratio)
        
        return {
            "is_consensus": is_consensus,
            "majority_correct": majority_correct,
            "consensus_ratio": consensus_ratio,
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
        }
    
    def _detect_conflict(
        self,
        model_results: List[ModelResult],
    ) -> ConflictInfo:
        """检测模型间的冲突.
        
        Args:
            model_results: 模型结果列表
            
        Returns:
            冲突信息
        """
        if len(model_results) < 2:
            return ConflictInfo(has_conflict=False)
        
        # 检查判断冲突
        correct_set = set(r.is_correct for r in model_results)
        has_judgment_conflict = len(correct_set) > 1
        
        # 检查错误类型冲突
        error_types = [r.error_type for r in model_results if r.error_type]
        has_type_conflict = len(set(error_types)) > 1 if error_types else False
        
        # 检查置信度冲突（差异过大）
        confidences = [r.confidence for r in model_results]
        confidence_range = max(confidences) - min(confidences) if confidences else 0
        has_confidence_conflict = confidence_range > 0.3
        
        if has_judgment_conflict or has_type_conflict or has_confidence_conflict:
            conflicting_models = []
            
            # 找出判断冲突的模型
            if has_judgment_conflict:
                correct_models = [r.model_id for r in model_results if r.is_correct]
                incorrect_models = [r.model_id for r in model_results if not r.is_correct]
                conflicting_models = correct_models + incorrect_models
                conflict_type = "judgment"
            elif has_type_conflict:
                conflicting_models = [r.model_id for r in model_results if r.error_type]
                conflict_type = "error_type"
            else:
                conflicting_models = [r.model_id for r in model_results]
                conflict_type = "confidence"
            
            return ConflictInfo(
                has_conflict=True,
                conflict_type=conflict_type,
                conflicting_models=conflicting_models,
                conflict_details={
                    "judgment_conflict": has_judgment_conflict,
                    "type_conflict": has_type_conflict,
                    "confidence_conflict": has_confidence_conflict,
                    "confidence_range": confidence_range,
                },
            )
        
        return ConflictInfo(has_conflict=False)
    
    def _calculate_weighted_confidence(
        self,
        model_results: List[ModelResult],
    ) -> float:
        """计算加权置信度.
        
        Args:
            model_results: 模型结果列表
            
        Returns:
            加权置信度
        """
        if not model_results:
            return 0.0
        
        total_weight = 0.0
        weighted_sum = 0.0
        
        for result in model_results:
            weight = self.config.weights.get(result.model_id, 1.0 / len(model_results))
            weighted_sum += result.confidence * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        return round(weighted_sum / total_weight, 4)
    
    def _determine_error_type(
        self,
        model_results: List[ModelResult],
        consensus_analysis: Dict[str, Any],
    ) -> Optional[ErrorType]:
        """确定最终错误类型.
        
        基于共识和权重投票确定错误类型。
        
        Args:
            model_results: 模型结果列表
            consensus_analysis: 共识分析结果
            
        Returns:
            错误类型
        """
        majority_correct = consensus_analysis["majority_correct"]
        
        # 如果多数认为正确，则无错误类型
        if majority_correct:
            return None
        
        # 收集错误类型投票
        error_votes: Dict[ErrorType, float] = {}
        
        for result in model_results:
            if result.error_type and not result.is_correct:
                weight = self.config.weights.get(result.model_id, 1.0)
                error_votes[result.error_type] = error_votes.get(result.error_type, 0.0) + weight
        
        if not error_votes:
            return ErrorType.KNOWLEDGE_GAP
        
        # 返回权重最高的错误类型
        return max(error_votes.items(), key=lambda x: x[1])[0]
    
    def _build_model_votes(
        self,
        model_results: List[ModelResult],
    ) -> Dict[str, ModelVote]:
        """构建模型投票映射.
        
        Args:
            model_results: 模型结果列表
            
        Returns:
            模型ID到投票的映射
        """
        votes = {}
        
        for result in model_results:
            # 提取推理原因
            reason = ""
            if result.diagnosis:
                if isinstance(result.diagnosis, dict):
                    reason = result.diagnosis.get("analysis", "")
                    if not reason:
                        reason = result.diagnosis.get("root_cause", "")
                        if not reason:
                            reason = result.diagnosis.get("error_analysis", "")
            
            votes[result.model_id] = ModelVote(
                model_id=result.model_id,
                is_correct=result.is_correct,
                error_type=result.error_type,
                confidence=result.confidence,
                reason=reason,
            )
        
        return votes
    
    def _create_failed_result(
        self,
        problem_id: str,
        error_message: str,
    ) -> ArbitrationResult:
        """创建失败的仲裁结果.
        
        Args:
            problem_id: 题目ID
            error_message: 错误信息
            
        Returns:
            失败的仲裁结果
        """
        return ArbitrationResult(
            problem_id=problem_id,
            is_correct=False,
            confidence=0.0,
            is_consensus=False,
            consensus_ratio=0.0,
            conflict_info={"error": error_message},
            used_models=[],
        )
    
    def should_trigger_variant(
        self, result: ArbitrationResult) -> bool:
        """判断是否应该触发变形题.
        
        在以下情况触发变形题：
        - 存在分歧
        - 置信度较低
        - 错误类型不确定
        
        Args:
            result: 仲裁结果
            
        Returns:
            是否应该触发变形题
        """
        # 存在分歧
        if not result.is_consensus:
            return True
        
        # 置信度低于阈值
        if result.confidence < self.config.min_confidence:
            return True
        
        # 存在冲突信息
        if result.conflict_info:
            return True
        
        return False
