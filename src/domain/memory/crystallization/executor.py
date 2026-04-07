"""结晶执行器. 功能追溯ID: F-MEM-005"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from src.domain.memory.crystallization.conditions import CrystallizationConditions
from src.domain.memory.meta_memory import CrystallizationResult
from src.domain.memory.profile_memory import ProfileMemory
from src.domain.models.base import generate_id, now_timestamp
from src.domain.models.diagnosis import ErrorType
from src.domain.models.memory import MistakePattern
from src.infrastructure.db.cognitive_gap import CognitiveGap, GapEvidence
from src.infrastructure.db.enums import EvidenceType, GapStatus
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

@dataclass
class CrystallizationContext:
    gap: CognitiveGap
    evidences: List[GapEvidence]
    student_id: str
    triggered_by: str
    force: bool = False

class CrystallizationExecutor:
    def __init__(self, gap_repo, evidence_repo, profile_memory=None, conditions=None):
        self._gap_repo = gap_repo
        self._evidence_repo = evidence_repo
        self._profile_memory = profile_memory
        self._conditions = conditions or CrystallizationConditions()
    
    async def crystallize(self, gap_id: str, force: bool = False) -> Optional[CrystallizationResult]:
        try:
            context = await self._prepare_context(gap_id)
            if not context:
                return None
            if not force:
                check = self._conditions.check_crystallization(context.gap, [e.evidence_type for e in context.evidences])
                if not check.can_crystallize:
                    return CrystallizationResult(gap_id=gap_id, student_id=context.student_id, success=False, new_status=context.gap.status, reason=check.reason)
            return await self._execute_crystallization(context)
        except Exception as e:
            logger.error(f"Crystallization failed: {e}")
            return CrystallizationResult(gap_id=gap_id, student_id="", success=False, new_status=GapStatus.PENDING.value, reason=str(e))
    
    async def dismiss(self, gap_id: str, reason: str = "") -> Optional[CrystallizationResult]:
        try:
            db_gap = await self._gap_repo.get_by_id(gap_id)
            if not db_gap or db_gap.status != GapStatus.PENDING.value:
                return None
            db_gap.status = GapStatus.DISMISSED.value
            db_gap.updated_at = now_timestamp()
            await self._gap_repo.update(db_gap)
            return CrystallizationResult(gap_id=gap_id, student_id=db_gap.student_id, success=True, new_status=GapStatus.DISMISSED.value, reason=reason or "Gap dismissed")
        except Exception as e:
            return CrystallizationResult(gap_id=gap_id, student_id="", success=False, new_status=GapStatus.PENDING.value, reason=str(e))
    
    async def _prepare_context(self, gap_id: str) -> Optional[CrystallizationContext]:
        gap = await self._gap_repo.get_by_id(gap_id)
        if not gap:
            return None
        evidences = await self._evidence_repo.find_many(gap_id=gap_id)
        return CrystallizationContext(gap=gap, evidences=list(evidences), student_id=gap.student_id, triggered_by="scheduler")
    
    async def _execute_crystallization(self, context: CrystallizationContext) -> CrystallizationResult:
        gap = context.gap
        crystallized_at = now_timestamp()
        gap.status = GapStatus.CRYSTALLIZED.value
        gap.crystallized_at = crystallized_at
        gap.updated_at = crystallized_at
        await self._gap_repo.update(gap)
        feature_id = await self._update_error_dna(context) if self._profile_memory else None
        return CrystallizationResult(gap_id=gap.gap_id, student_id=context.student_id, success=True, new_status=GapStatus.CRYSTALLIZED.value, crystallized_at=crystallized_at, feature_id=feature_id, reason="Crystallized successfully")
    
    async def _update_error_dna(self, context: CrystallizationContext) -> Optional[str]:
        try:
            profile = await self._profile_memory.get_profile(context.student_id)
            if not profile:
                profile = await self._profile_memory.create_profile(context.student_id)
            type_mapping = {"careless": ErrorType.CARELESS, "method_error": ErrorType.METHOD_ERROR, "concept_gap": ErrorType.CONCEPT_GAP, "calculation_error": ErrorType.CALCULATION_ERROR, "reading_error": ErrorType.READING_ERROR}
            pattern = MistakePattern(error_type=type_mapping.get(context.gap.gap_type, ErrorType.UNKNOWN), related_concepts=context.gap.related_knowledge or [], occurrence_count=context.gap.occurrence_count)
            profile.error_dna.add_pattern(pattern)
            await self._profile_memory.update_profile(profile)
            return generate_id("feature")
        except Exception as e:
            logger.error(f"Failed to update error_dna: {e}")
            return None
    
    async def batch_crystallize(self, gap_ids: List[str], force: bool = False) -> List[CrystallizationResult]:
        return [r for r in [await self.crystallize(gid, force) for gid in gap_ids] if r]
