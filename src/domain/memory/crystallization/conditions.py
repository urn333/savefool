"""结晶条件判定器. 功能追溯ID: F-MEM-005"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
from src.domain.models.base import now_timestamp
from src.infrastructure.db.cognitive_gap import CognitiveGap
from src.infrastructure.db.enums import EvidenceType, GapStatus

@dataclass
class CrystallizationCheckResult:
    can_crystallize: bool
    reason: str
    confidence: float = 0.0
    evidence_types: List[str] = None
    def __post_init__(self):
        if self.evidence_types is None:
            self.evidence_types = []

class CrystallizationConditions:
    REPEAT_ERROR_HOURS = 24
    CROSS_HOMEWORK_THRESHOLD = 3
    MIN_OCCURRENCE_COUNT = 2
    
    def __init__(self, observation_period_hours: int = 24):
        self.observation_period_hours = observation_period_hours
    
    def check_crystallization(self, gap: CognitiveGap, evidences: Optional[List] = None) -> CrystallizationCheckResult:
        if gap.status != GapStatus.PENDING.value:
            return CrystallizationCheckResult(False, f"Gap status is {gap.status}, not pending")
        if not self._is_observation_complete(gap):
            remaining = self._get_remaining_hours(gap)
            return CrystallizationCheckResult(False, f"Observation period not complete, {remaining:.1f} hours remaining")
        checks = [self._check_repeat_error(gap, evidences or []), self._check_variant_failure(gap, evidences or []), self._check_cross_homework(gap)]
        for check in checks:
            if check.can_crystallize:
                return check
        dismiss_check = self._check_should_dismiss(gap, evidences or [])
        if "should dismiss" in dismiss_check.reason.lower():
            return CrystallizationCheckResult(False, "No new evidence during observation period - should dismiss")
        return CrystallizationCheckResult(False, "Insufficient evidence for crystallization, continuing observation", 0.3)
    
    def _is_observation_complete(self, gap: CognitiveGap) -> bool:
        discovered_at = gap.discovered_at
        # 处理Mock对象的情况
        if isinstance(discovered_at, str):
            discovered_at = datetime.fromisoformat(discovered_at.replace('Z', '+00:00'))
        elif hasattr(discovered_at, 'timestamp'):
            # 已经是datetime对象
            pass
        return now_timestamp() >= discovered_at + timedelta(hours=self.observation_period_hours)
    
    def _get_remaining_hours(self, gap: CognitiveGap) -> float:
        discovered_at = gap.discovered_at
        # 处理Mock对象的情况
        if isinstance(discovered_at, str):
            discovered_at = datetime.fromisoformat(discovered_at.replace('Z', '+00:00'))
        return max(0, (discovered_at + timedelta(hours=self.observation_period_hours) - now_timestamp()).total_seconds() / 3600)
    
    def _check_repeat_error(self, gap: CognitiveGap, evidences: List) -> CrystallizationCheckResult:
        evidence_values = [e.value if isinstance(e, EvidenceType) else e for e in evidences]
        if EvidenceType.REPEAT_ERROR.value in evidence_values and gap.occurrence_count >= self.MIN_OCCURRENCE_COUNT:
            return CrystallizationCheckResult(True, f"Repeat error within {self.REPEAT_ERROR_HOURS} hours", min(1.0, 0.6 + gap.occurrence_count * 0.1), ["repeat_error"])
        return CrystallizationCheckResult(False, "No repeat error evidence")
    
    def _check_variant_failure(self, gap: CognitiveGap, evidences: List) -> CrystallizationCheckResult:
        evidence_values = [e.value if isinstance(e, EvidenceType) else e for e in evidences]
        if EvidenceType.VARIANT_FAILED.value in evidence_values:
            return CrystallizationCheckResult(True, "Variant validation failed", 0.9, ["variant_failed"])
        return CrystallizationCheckResult(False, "No variant failure evidence")
    
    def _check_cross_homework(self, gap: CognitiveGap) -> CrystallizationCheckResult:
        if gap.occurrence_count >= self.CROSS_HOMEWORK_THRESHOLD:
            return CrystallizationCheckResult(True, f"Cross-homework occurrence: {gap.occurrence_count} times", min(1.0, 0.5 + gap.occurrence_count * 0.15), ["cross_homework"])
        return CrystallizationCheckResult(False, f"Occurrence count {gap.occurrence_count} below threshold")
    
    def _check_should_dismiss(self, gap: CognitiveGap, evidences: List) -> CrystallizationCheckResult:
        if not self._is_observation_complete(gap):
            return CrystallizationCheckResult(False, "Observation period not complete")
        evidence_values = [e.value if isinstance(e, EvidenceType) else e for e in evidences]
        has_only_initial = (len(evidences) == 1 and EvidenceType.INITIAL_DIAGNOSIS.value in evidence_values) or len(evidences) == 0
        if has_only_initial and gap.occurrence_count < self.MIN_OCCURRENCE_COUNT:
            return CrystallizationCheckResult(False, "No new evidence during observation period - should dismiss")
        return CrystallizationCheckResult(False, "Has some evidence, continue observation")
    
    def evaluate_crystallization_priority(self, gap: CognitiveGap) -> int:
        priority = 10 if self._is_observation_complete(gap) else 0
        priority += gap.occurrence_count * 2 + (now_timestamp() - gap.discovered_at).days
        return priority
