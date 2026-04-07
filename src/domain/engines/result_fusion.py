"""结果融合算法.

将多模型结果融合为统一的诊断输出。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from src.infrastructure.logging import get_logger
from src.domain.models.arbitration import ArbitrationResult, ModelResult
from src.domain.models.diagnosis import ErrorType, DiagnosisStatus, DiagnosisResult, WrongProblem

logger = get_logger(__name__)


@dataclass
class FusionConfig:
    """融合配置.
    
    Attributes:
        field_confidence_threshold: 字段置信度阈值
        enable_source_tracking: 是否启用来源追踪
        conflict_resolution_strategy: 冲突解决策略
        field_merge_strategy: 字段合并策略 (union/intersection/weighted)
        conflict_resolution: 冲突解决策略 (majority/confidence)
        include_sources: 是否包含来源标记
        min_field_agreement: 字段最小同意比例
    """
    field_confidence_threshold: float = 0.6
    enable_source_tracking: bool = True
    conflict_resolution_strategy: str = "weighted_vote"  # weighted_vote, priority, merge
    field_merge_strategy: str = "union"  # union, intersection, weighted
    conflict_resolution: str = "majority"  # majority, confidence
    include_sources: bool = True
    min_field_agreement: float = 0.5


@dataclass
class FieldSource:
    """字段来源.
    
    Attributes:
        field_name: 字段名
        model_id: 来源模型
        confidence: 置信度
        value: 字段值
    """
    field_name: str
    model_id: str
    confidence: float
    value: Any


@dataclass
class FusedDiagnosis:
    """融合后的诊断结果.
    
    Attributes:
        is_wrong: 是否错误
        error_type: 错误类型
        root_cause: 根本原因
        concept_gaps: 概念缺口列表
        confidence: 整体置信度
        field_sources: 各字段来源
        conflict_flags: 冲突标记
    """
    is_wrong: bool = False
    error_type: Optional[ErrorType] = None
    root_cause: str = ""
    concept_gaps: List[str] = field(default_factory=list)
    confidence: float = 0.0
    field_sources: Dict[str, FieldSource] = field(default_factory=dict)
    conflict_flags: List[str] = field(default_factory=list)


@dataclass
class FusionResult:
    """融合结果 (向后兼容).
    
    Attributes:
        problem_id: 题目ID
        fused_fields: 融合后的字段
        field_sources: 字段来源映射
        conflicts: 检测到的冲突
        fusion_confidence: 融合置信度
    """
    problem_id: str = ""
    fused_fields: Dict[str, Any] = field(default_factory=dict)
    field_sources: Dict[str, FieldSource] = field(default_factory=dict)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    fusion_confidence: float = 0.0


class ResultFusion:
    """结果融合算法.
    
    合并多模型结果，处理冲突字段，生成统一诊断输出。
    
    Example:
        >>> fusion = ResultFusion(config)
        >>> diagnosis = fusion.fuse_results(
        ...     arbitration_result=arbitration_result,
        ...     model_results=[result_a, result_b, result_c],
        ... )
    """
    
    # 字段优先级配置（用于解决冲突）
    FIELD_PRIORITY = {
        "error_type": ["model_c", "model_a", "model_b"],  # 概念模型优先
        "root_cause": ["model_c", "model_a", "model_b"],
        "steps": ["model_b", "model_a", "model_c"],      # 逻辑模型优先
        "knowledge_points": ["model_a", "model_c", "model_b"],
    }
    
    def __init__(self, config: Optional[FusionConfig] = None):
        """初始化融合器.
        
        Args:
            config: 融合配置
        """
        self.config = config or FusionConfig()
        self.logger = get_logger(__name__)
    
    def fuse(
        self,
        arbitration_result: ArbitrationResult,
        model_results: List[ModelResult],
        problem_id: str = "",
    ) -> FusionResult:
        """执行结果融合 (向后兼容).
        
        Args:
            arbitration_result: 仲裁结果
            model_results: 原始模型结果列表
            problem_id: 题目ID
            
        Returns:
            融合后的结果
        """
        fused = self.fuse_results(arbitration_result, model_results, problem_id)
        
        # 转换为FusionResult
        return FusionResult(
            problem_id=problem_id or arbitration_result.problem_id,
            fused_fields={
                "is_wrong": fused.is_wrong,
                "error_type": fused.error_type,
                "root_cause": fused.root_cause,
                "concept_gaps": fused.concept_gaps,
                "confidence": fused.confidence,
            },
            field_sources=fused.field_sources,
            conflicts=[{"flag": f} for f in fused.conflict_flags],
            fusion_confidence=fused.confidence,
        )
    
    def fuse_results(
        self,
        arbitration_result: ArbitrationResult,
        model_results: List[ModelResult],
        problem_id: str = "",
    ) -> FusedDiagnosis:
        """融合多模型结果.
        
        Args:
            arbitration_result: 仲裁结果
            model_results: 原始模型结果列表
            problem_id: 题目ID
            
        Returns:
            融合后的诊断结果
        """
        self.logger.info(
            "fusion_start",
            problem_id=problem_id or arbitration_result.problem_id,
            model_count=len(model_results),
        )
        
        if not model_results:
            return FusedDiagnosis(
                is_wrong=not arbitration_result.is_correct,
                confidence=arbitration_result.confidence,
            )
        
        # 提取各模型的诊断字段
        field_candidates = self._extract_field_candidates(model_results)
        
        # 融合各字段
        fused = FusedDiagnosis()
        fused.is_wrong = not arbitration_result.is_correct
        fused.error_type = arbitration_result.error_type
        fused.confidence = arbitration_result.confidence
        
        # 融合根本原因
        fused.root_cause = self._fuse_root_cause(
            field_candidates.get("root_cause", []),
            model_results,
        )
        
        # 融合概念缺口
        fused.concept_gaps = self._fuse_concept_gaps(
            field_candidates.get("concept_gaps", []),
            model_results,
        )
        
        # 记录字段来源
        if self.config.enable_source_tracking:
            fused.field_sources = self._track_field_sources(
                fused, field_candidates, model_results
            )
        
        # 检测冲突
        fused.conflict_flags = self._detect_field_conflicts(
            field_candidates, model_results
        )
        
        self.logger.info(
            "fusion_complete",
            problem_id=problem_id or arbitration_result.problem_id,
            concept_gaps_count=len(fused.concept_gaps),
            conflict_count=len(fused.conflict_flags),
        )
        
        return fused
    
    def _extract_field_candidates(
        self,
        model_results: List[ModelResult],
    ) -> Dict[str, List[Tuple[Any, str, float]]]:
        """提取各字段的候选值.
        
        Args:
            model_results: 模型结果列表
            
        Returns:
            字段到候选值列表的映射
        """
        candidates: Dict[str, List[Tuple[Any, str, float]]] = {
            "root_cause": [],
            "concept_gaps": [],
            "steps": [],
            "knowledge_points": [],
        }
        
        for result in model_results:
            if not result.diagnosis:
                continue
            
            diag = result.diagnosis
            if isinstance(diag, dict):
                # 根本原因
                if "root_cause" in diag and diag["root_cause"]:
                    candidates["root_cause"].append(
                        (diag["root_cause"], result.model_id, result.confidence)
                    )
                elif "analysis" in diag and diag["analysis"]:
                    candidates["root_cause"].append(
                        (diag["analysis"], result.model_id, result.confidence)
                    )
                elif "error_analysis" in diag and diag["error_analysis"]:
                    candidates["root_cause"].append(
                        (diag["error_analysis"], result.model_id, result.confidence)
                    )
                
                # 概念缺口
                if "concept_gaps" in diag and diag["concept_gaps"]:
                    for gap in diag["concept_gaps"]:
                        candidates["concept_gaps"].append(
                            (gap, result.model_id, result.confidence)
                        )
                
                # 解题步骤
                if "steps" in diag and diag["steps"]:
                    candidates["steps"].append(
                        (diag["steps"], result.model_id, result.confidence)
                    )
                
                # 知识点
                if "knowledge_points" in diag and diag["knowledge_points"]:
                    for kp in diag["knowledge_points"]:
                        candidates["knowledge_points"].append(
                            (kp, result.model_id, result.confidence)
                        )
        
        return candidates
    
    def _fuse_root_cause(
        self,
        candidates: List[Tuple[str, str, float]],
        model_results: List[ModelResult],
    ) -> str:
        """融合根本原因.
        
        采用加权选择策略，选择置信度最高的描述。
        
        Args:
            candidates: 候选描述列表
            model_results: 模型结果列表
            
        Returns:
            融合后的根本原因
        """
        if not candidates:
            return "未能确定具体原因"
        
        # 按置信度排序，选择最高的
        sorted_candidates = sorted(
            candidates,
            key=lambda x: x[2],
            reverse=True
        )
        
        # 优先选择优先级高的模型
        priority_order = self.FIELD_PRIORITY.get("root_cause", [])
        
        for priority_model in priority_order:
            for value, model_id, confidence in sorted_candidates:
                if model_id == priority_model and confidence >= self.config.field_confidence_threshold:
                    return value
        
        # 如果没有满足条件的，返回置信度最高的
        return sorted_candidates[0][0]
    
    def _fuse_concept_gaps(
        self,
        candidates: List[Tuple[str, str, float]],
        model_results: List[ModelResult],
    ) -> List[str]:
        """融合概念缺口.
        
        合并各模型提出的概念缺口，去重并排序。
        
        Args:
            candidates: 候选缺口列表
            model_results: 模型结果列表
            
        Returns:
            融合后的概念缺口列表
        """
        if not candidates:
            return []
        
        # 统计每个缺口的加权出现次数
        gap_scores: Dict[str, float] = {}
        
        for gap, model_id, confidence in candidates:
            gap_key = gap.lower().strip()
            weight = confidence
            gap_scores[gap_key] = gap_scores.get(gap_key, 0.0) + weight
        
        # 按分数排序，选择前5个
        sorted_gaps = sorted(
            gap_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 保留原始大小写（从candidates中找）
        result = []
        for gap_key, score in sorted_gaps[:5]:
            # 找到对应的原始gap
            for gap, _, _ in candidates:
                if gap.lower().strip() == gap_key:
                    result.append(gap)
                    break
            else:
                result.append(gap_key)
        
        return result
    
    def _track_field_sources(
        self,
        fused: FusedDiagnosis,
        candidates: Dict[str, List[Tuple[Any, str, float]]],
        model_results: List[ModelResult],
    ) -> Dict[str, FieldSource]:
        """追踪字段来源.
        
        Args:
            fused: 融合后的诊断
            candidates: 字段候选值
            model_results: 模型结果列表
            
        Returns:
            字段来源映射
        """
        sources = {}
        
        # 根本原因来源
        root_cause_candidates = candidates.get("root_cause", [])
        for value, model_id, confidence in root_cause_candidates:
            if value == fused.root_cause:
                sources["root_cause"] = FieldSource(
                    field_name="root_cause",
                    model_id=model_id,
                    confidence=confidence,
                    value=value,
                )
                break
        
        # 错误类型来源
        for result in model_results:
            if result.error_type == fused.error_type:
                sources["error_type"] = FieldSource(
                    field_name="error_type",
                    model_id=result.model_id,
                    confidence=result.confidence,
                    value=result.error_type,
                )
                break
        
        # 概念缺口来源（多来源）
        gap_sources = []
        for gap in fused.concept_gaps:
            for value, model_id, confidence in candidates.get("concept_gaps", []):
                if value.lower().strip() == gap.lower().strip():
                    gap_sources.append(FieldSource(
                        field_name=f"concept_gap",
                        model_id=model_id,
                        confidence=confidence,
                        value=value,
                    ))
                    break
        
        if gap_sources:
            sources["concept_gaps"] = gap_sources
        
        return sources
    
    def _detect_field_conflicts(
        self,
        candidates: Dict[str, List[Tuple[Any, str, float]]],
        model_results: List[ModelResult],
    ) -> List[str]:
        """检测字段冲突.
        
        Args:
            candidates: 字段候选值
            model_results: 模型结果列表
            
        Returns:
            冲突标记列表
        """
        conflicts = []
        
        # 检查根本原因的冲突
        root_cause_candidates = candidates.get("root_cause", [])
        if len(root_cause_candidates) >= 2:
            # 检查描述是否差异过大
            descriptions = [c[0].lower()[:50] for c in root_cause_candidates]
            unique_descriptions = set(descriptions)
            if len(unique_descriptions) > 1:
                conflicts.append("root_cause_divergence")
        
        # 检查错误类型的冲突
        error_types = [r.error_type for r in model_results if r.error_type]
        if len(set(error_types)) > 1:
            conflicts.append("error_type_conflict")
        
        # 检查置信度冲突
        confidences = [r.confidence for r in model_results]
        if confidences:
            confidence_range = max(confidences) - min(confidences)
            if confidence_range > 0.4:
                conflicts.append("high_confidence_variance")
        
        return conflicts
    
    def create_diagnosis_result(
        self,
        task_id: str,
        arbitration_result: ArbitrationResult,
        fused_diagnosis: FusedDiagnosis,
        problem_id: str = "",
    ) -> DiagnosisResult:
        """创建诊断结果对象.
        
        Args:
            task_id: 任务ID
            arbitration_result: 仲裁结果
            fused_diagnosis: 融合后的诊断
            problem_id: 题目ID
            
        Returns:
            诊断结果对象
        """
        wrong_problems = []
        
        if fused_diagnosis.is_wrong:
            wrong_problems.append(WrongProblem(
                problem_id=problem_id or arbitration_result.problem_id,
                error_type=fused_diagnosis.error_type or ErrorType.KNOWLEDGE_GAP,
                root_cause=fused_diagnosis.root_cause,
                concept_gap=fused_diagnosis.concept_gaps,
                confidence=fused_diagnosis.confidence,
            ))
        
        return DiagnosisResult(
            task_id=task_id,
            status=DiagnosisStatus.COMPLETED,
            wrong_problems=wrong_problems,
            knowledge_update={
                "concept_gaps": fused_diagnosis.concept_gaps,
                "field_sources": {
                    k: v.__dict__ if hasattr(v, '__dict__') else v
                    for k, v in fused_diagnosis.field_sources.items()
                } if fused_diagnosis.field_sources else {},
                "conflict_flags": fused_diagnosis.conflict_flags,
            },
        )


    def fuse_concept_scores(
        self,
        model_results: List[ModelResult],
    ) -> Dict[str, float]:
        """专门融合概念分数.
        
        Args:
            model_results: 模型结果列表
            
        Returns:
            融合后的概念分数
        """
        all_scores: Dict[str, List[float]] = {}
        
        # 收集所有概念分数
        for result in model_results:
            for concept, score in result.concept_scores.items():
                if concept not in all_scores:
                    all_scores[concept] = []
                all_scores[concept].append(score)
        
        # 融合分数（取平均）
        fused_scores = {
            concept: sum(scores) / len(scores)
            for concept, scores in all_scores.items()
        }
        
        return fused_scores

    def fuse_knowledge_points(
        self,
        model_results: List[ModelResult],
    ) -> List[Dict[str, Any]]:
        """融合知识点.
        
        Args:
            model_results: 模型结果列表
            
        Returns:
            融合后的知识点列表
        """
        all_points: Dict[str, Dict[str, Any]] = {}
        
        for result in model_results:
            if not result.diagnosis:
                continue
            
            knowledge_points = result.diagnosis.get("knowledge_points", [])
            if isinstance(knowledge_points, list):
                for point in knowledge_points:
                    if isinstance(point, str):
                        point_id = point
                        point_data = {"name": point, "sources": [result.model_id]}
                    else:
                        point_id = point.get("id", str(point))
                        point_data = {**point, "sources": [result.model_id]}
                    
                    if point_id in all_points:
                        all_points[point_id]["sources"].append(result.model_id)
                        all_points[point_id]["frequency"] = all_points[point_id].get("frequency", 1) + 1
                    else:
                        all_points[point_id] = {**point_data, "frequency": 1}
        
        # 按频率排序
        sorted_points = sorted(
            all_points.values(),
            key=lambda x: x.get("frequency", 1),
            reverse=True
        )
        
        return sorted_points[:10]  # 最多返回10个
