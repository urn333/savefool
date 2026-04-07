"""结晶条件判定器.

实现24小时结晶机制的条件判定逻辑.

功能追溯ID: F-MEM-005
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from enum import Enum

from src.domain.models.base import now_timestamp
from src.infrastructure.db.cognitive_gap import CognitiveGap
from src.infrastructure.db.enums import EvidenceType, GapStatus


@dataclass
class CrystallizationCheckResult:
    """结晶条件检查结果."""
    
    can_crystallize: bool
    reason: str
    confidence: float = 0.0
    evidence_types: List[str] = None
    
    def __post_init__(self):
        if self.evidence_types is None:
            self.evidence_types = []


class CrystallizationTrigger(Enum):
    """结晶触发条件类型."""
    
    REPEAT_ERROR_24H = "repeat_error_24h"  # 24小时内重复错误
    VARIANT_FAILED = "variant_failed"       # 变形题验证失败
    CROSS_HOMEWORK_3 = "cross_homework_3"  # 跨3次作业
    OBSERVATION_EXPIRED = "observation_expired"  # 观察期满无新证据


class CrystallizationConditions:
    """结晶条件判定器.
    
    根据以下条件判定认知缺口是否应该结晶:
    1. 24小时内再次出现同类错误
    2. 变形题验证失败  
    3. 跨3次作业共现
    
    满足任一条件 → crystallized
    观察期满无证据 → dismissed
    """
    
    # 结晶条件阈值
    REPEAT_ERROR_HOURS = 24  # 重复错误时间窗口
    CROSS_HOMEWORK_THRESHOLD = 3  # 跨作业共现阈值
    MIN_OCCURRENCE_COUNT = 2  # 最小出现次数
    
    def __init__(
        self,
        observation_period_hours: int = 24,
    ):
        """初始化条件判定器.
        
        Args:
            observation_period_hours: 观察期时长(小时)
        """
        self.observation_period_hours = observation_period_hours
        self._triggered_conditions: Set[CrystallizationTrigger] = set()
    
    def check_crystallization(
        self,
        gap: CognitiveGap,
        evidences: Optional[List[EvidenceType]] = None,
    ) -> CrystallizationCheckResult:
        """检查是否应该结晶.
        
        Args:
            gap: 认知缺口
            evidences: 证据类型列表(可选)
            
        Returns:
            检查结果
        """
        # 检查状态
        if gap.status != GapStatus.PENDING.value:
            return CrystallizationCheckResult(
                can_crystallize=False,
                reason=f"Gap status is {gap.status}, not pending",
                confidence=0.0,
            )
        
        # 检查观察期是否结束
        if not self._is_observation_complete(gap):
            remaining = self._get_remaining_hours(gap)
            return CrystallizationCheckResult(
                can_crystallize=False,
                reason=f"Observation period not complete, {remaining:.1f} hours remaining",
                confidence=0.0,
            )
        
        # 检查结晶条件
        checks = [
            self._check_repeat_error(gap, evidences or []),
            self._check_variant_failure(gap, evidences or []),
            self._check_cross_homework(gap),
        ]
        
        # 满足任一条件即可结晶
        for check in checks:
            if check.can_crystallize:
                return check
        
        # 检查是否应该排除
        dismiss_check = self._check_should_dismiss(gap, evidences or [])
        if "should dismiss" in dismiss_check.reason.lower():
            return CrystallizationCheckResult(
                can_crystallize=False,
                reason="No new evidence during observation period - should dismiss",
                confidence=0.0,
            )
        
        # 继续观察
        return CrystallizationCheckResult(
            can_crystallize=False,
            reason="Insufficient evidence for crystallization, continuing observation",
            confidence=0.3,
        )
    
    def _is_observation_complete(self, gap: CognitiveGap) -> bool:
        """检查观察期是否结束.
        
        Args:
            gap: 认知缺口
            
        Returns:
            观察期是否结束
        """
        cutoff_time = gap.discovered_at + timedelta(hours=self.observation_period_hours)
        return now_timestamp() >= cutoff_time
    
    def _get_remaining_hours(self, gap: CognitiveGap) -> float:
        """获取剩余观察时间.
        
        Args:
            gap: 认知缺口
            
        Returns:
            剩余小时数
        """
        end_time = gap.discovered_at + timedelta(hours=self.observation_period_hours)
        remaining = (end_time - now_timestamp()).total_seconds() / 3600
        return max(0, remaining)
    
    def _check_repeat_error(
        self,
        gap: CognitiveGap,
        evidences: List[EvidenceType],
    ) -> CrystallizationCheckResult:
        """检查24小时内重复错误条件.
        
        条件: 在24小时内再次出现同类错误
        
        Args:
            gap: 认知缺口
            evidences: 证据列表
            
        Returns:
            检查结果
        """
        # 检查是否有重复错误证据
        evidence_values = [
            e.value if isinstance(e, EvidenceType) else e for e in evidences
        ]
        has_repeat_error = EvidenceType.REPEAT_ERROR.value in evidence_values
        
        # 检查出现次数
        sufficient_occurrences = gap.occurrence_count >= self.MIN_OCCURRENCE_COUNT
        
        if has_repeat_error and sufficient_occurrences:
            return CrystallizationCheckResult(
                can_crystallize=True,
                reason=f"Repeat error within {self.REPEAT_ERROR_HOURS} hours "
                       f"(occurrence count: {gap.occurrence_count})",
                confidence=min(1.0, 0.6 + gap.occurrence_count * 0.1),
                evidence_types=["repeat_error"],
            )
        
        return CrystallizationCheckResult(
            can_crystallize=False,
            reason="No repeat error evidence",
            confidence=0.0,
        )
    
    def _check_variant_failure(
        self,
        gap: CognitiveGap,
        evidences: List[EvidenceType],
    ) -> CrystallizationCheckResult:
        """检查变形题验证失败条件.
        
        条件: 变形题验证失败
        
        Args:
            gap: 认知缺口
            evidences: 证据列表
            
        Returns:
            检查结果
        """
        # 检查是否有变形题失败证据
        evidence_values = [
            e.value if isinstance(e, EvidenceType) else e for e in evidences
        ]
        has_variant_failed = EvidenceType.VARIANT_FAILED.value in evidence_values
        
        if has_variant_failed:
            return CrystallizationCheckResult(
                can_crystallize=True,
                reason="Variant validation failed - indicates deep misconception",
                confidence=0.9,
                evidence_types=["variant_failed"],
            )
        
        return CrystallizationCheckResult(
            can_crystallize=False,
            reason="No variant failure evidence",
            confidence=0.0,
        )
    
    def _check_cross_homework(self, gap: CognitiveGap) -> CrystallizationCheckResult:
        """检查跨作业共现条件.
        
        条件: 跨3次作业共现
        
        Args:
            gap: 认知缺口
            
        Returns:
            检查结果
        """
        # 检查出现次数是否达到阈值
        if gap.occurrence_count >= self.CROSS_HOMEWORK_THRESHOLD:
            return CrystallizationCheckResult(
                can_crystallize=True,
                reason=f"Cross-homework occurrence: {gap.occurrence_count} times "
                       f"(threshold: {self.CROSS_HOMEWORK_THRESHOLD})",
                confidence=min(1.0, 0.5 + gap.occurrence_count * 0.15),
                evidence_types=["cross_homework"],
            )
        
        return CrystallizationCheckResult(
            can_crystallize=False,
            reason=f"Occurrence count {gap.occurrence_count} below threshold "
                   f"{self.CROSS_HOMEWORK_THRESHOLD}",
            confidence=0.0,
        )
    
    def _check_should_dismiss(
        self,
        gap: CognitiveGap,
        evidences: List[EvidenceType],
    ) -> CrystallizationCheckResult:
        """检查是否应该排除.
        
        条件: 观察期结束且没有新证据
        
        Args:
            gap: 认知缺口
            evidences: 证据列表
            
        Returns:
            检查结果
        """
        # 观察期必须已结束
        if not self._is_observation_complete(gap):
            return CrystallizationCheckResult(
                can_crystallize=False,
                reason="Observation period not complete",
                confidence=0.0,
            )
        
        # 只有初始诊断,没有额外证据
        evidence_values = [
            e.value if isinstance(e, EvidenceType) else e for e in evidences
        ]
        has_only_initial = (
            len(evidences) == 1 and
            EvidenceType.INITIAL_DIAGNOSIS.value in evidence_values
        ) or len(evidences) == 0
        
        # 出现次数少
        low_occurrence = gap.occurrence_count < self.MIN_OCCURRENCE_COUNT
        
        if has_only_initial and low_occurrence:
            return CrystallizationCheckResult(
                can_crystallize=False,
                reason="No new evidence during observation period - should dismiss",
                confidence=0.0,
            )
        
        return CrystallizationCheckResult(
            can_crystallize=False,
            reason="Has some evidence, continue observation",
            confidence=0.0,
        )
    
    def evaluate_crystallization_priority(
        self,
        gap: CognitiveGap,
    ) -> int:
        """评估结晶优先级.
        
        用于批处理时的排序。
        
        Args:
            gap: 认知缺口
            
        Returns:
            优先级分数(越高越优先)
        """
        priority = 0
        
        # 观察期已结束的优先级更高
        if self._is_observation_complete(gap):
            priority += 10
        
        # 出现次数多的优先级更高
        priority += gap.occurrence_count * 2
        
        # 时间越久的优先级越高(防止积压)
        days_pending = (now_timestamp() - gap.discovered_at).days
        priority += days_pending
        
        return priority
    
    def get_condition_summary(self) -> Dict[str, Any]:
        """获取条件配置摘要.
        
        Returns:
            配置摘要
        """
        return {
            "repeat_error_hours": self.REPEAT_ERROR_HOURS,
            "cross_homework_threshold": self.CROSS_HOMEWORK_THRESHOLD,
            "observation_period_hours": self.observation_period_hours,
        }
