"""结晶调度器. 功能追溯ID: F-MEM-005"""
import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional
from src.domain.memory.crystallization.conditions import CrystallizationConditions
from src.domain.memory.crystallization.executor import CrystallizationExecutor
from src.domain.memory.meta_memory import CrystallizationResult
from src.domain.models.base import now_timestamp
from src.infrastructure.db.cognitive_gap import CognitiveGap
from src.infrastructure.db.enums import GapStatus
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

@dataclass
class SchedulerConfig:
    start_hour: int = 2
    start_minute: int = 0
    end_hour: int = 4
    end_minute: int = 0
    batch_size: int = 100
    batch_interval_seconds: int = 30
    max_retries: int = 3
    retry_interval_seconds: int = 300
    dry_run: bool = False
    force_crystallization: bool = False

@dataclass
class SchedulerRunResult:
    run_id: str
    started_at: datetime
    completed_at: datetime
    total_gaps: int
    crystallized: int
    dismissed: int
    failed: int
    skipped: int
    details: List[CrystallizationResult]
    
    @property
    def success_rate(self) -> float:
        return (self.crystallized + self.dismissed) / max(self.total_gaps, 1)
    
    @property
    def duration_seconds(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()

class CrystallizationScheduler:
    def __init__(self, gap_repo, evidence_repo, executor=None, conditions=None, config=None):
        self._gap_repo = gap_repo
        self._evidence_repo = evidence_repo
        self._executor = executor
        self._conditions = conditions or CrystallizationConditions()
        self._config = config or SchedulerConfig()
    
    async def run_daily_crystallization(self, student_id: Optional[str] = None) -> SchedulerRunResult:
        run_id = f"run_{now_timestamp().strftime('%Y%m%d_%H%M%S')}"
        started_at = now_timestamp()
        
        try:
            pending_gaps = await self._get_pending_gaps(student_id)
            if not pending_gaps:
                return SchedulerRunResult(run_id, started_at, now_timestamp(), 0, 0, 0, 0, 0, [])
            
            sorted_gaps = self._sort_by_priority(pending_gaps)
            results = await self._process_gaps(sorted_gaps)
            
            stats = self._calculate_stats(results)
            return SchedulerRunResult(run_id, started_at, now_timestamp(), len(pending_gaps),
                                     stats["crystallized"], stats["dismissed"], stats["failed"], stats["skipped"], results)
        except Exception as e:
            logger.error(f"Daily crystallization failed: {e}")
            raise
    
    async def run_immediate_crystallization(self, gap_id: str, force: bool = False):
        if not self._executor:
            self._executor = CrystallizationExecutor(self._gap_repo, self._evidence_repo)
        return await self._executor.crystallize(gap_id, force=force)
    
    def is_in_execution_window(self, current_time: Optional[datetime] = None) -> bool:
        current = current_time or now_timestamp()
        current_time_only = current.time()
        start_time = time(self._config.start_hour, self._config.start_minute)
        end_time = time(self._config.end_hour, self._config.end_minute)
        
        if start_time <= end_time:
            return start_time <= current_time_only <= end_time
        else:
            return current_time_only >= start_time or current_time_only <= end_time
    
    def get_next_run_time(self, from_time: Optional[datetime] = None) -> datetime:
        base = from_time or now_timestamp()
        next_run = base.replace(hour=self._config.start_hour, minute=self._config.start_minute, second=0, microsecond=0)
        if next_run <= base:
            next_run += timedelta(days=1)
        next_run += timedelta(minutes=random.randint(0, 30))
        return next_run
    
    async def _get_pending_gaps(self, student_id: Optional[str] = None) -> List[CognitiveGap]:
        filters = {"status": GapStatus.PENDING.value}
        if student_id:
            filters["student_id"] = student_id
        return list(await self._gap_repo.find_many(**filters))
    
    def _sort_by_priority(self, gaps: List[CognitiveGap]) -> List[CognitiveGap]:
        def priority_score(gap: CognitiveGap) -> int:
            score = 0
            cutoff_time = gap.discovered_at + timedelta(hours=self._conditions.observation_period_hours)
            if now_timestamp() >= cutoff_time:
                score += 1000
            score += gap.occurrence_count * 100
            score += (now_timestamp() - gap.discovered_at).days * 10
            return score
        return sorted(gaps, key=priority_score, reverse=True)
    
    async def _process_gaps(self, gaps: List[CognitiveGap]) -> List[CrystallizationResult]:
        if not self._executor:
            self._executor = CrystallizationExecutor(self._gap_repo, self._evidence_repo)
        
        results = []
        batch_size = self._config.batch_size
        
        for i in range(0, len(gaps), batch_size):
            batch = gaps[i:i + batch_size]
            for gap in batch:
                result = await self._process_single_gap(gap)
                if result:
                    results.append(result)
            if i + batch_size < len(gaps):
                import asyncio
                await asyncio.sleep(self._config.batch_interval_seconds)
        return results
    
    async def _process_single_gap(self, gap: CognitiveGap) -> Optional[CrystallizationResult]:
        try:
            evidences = await self._evidence_repo.find_many(gap_id=gap.gap_id)
            evidence_types = [e.evidence_type for e in evidences]
            check_result = self._conditions.check_crystallization(gap, evidence_types)
            
            if self._config.dry_run:
                new_status = GapStatus.CRYSTALLIZED.value if check_result.can_crystallize else GapStatus.PENDING.value
                return CrystallizationResult(gap_id=gap.gap_id, student_id=gap.student_id, success=True,
                                            new_status=new_status, reason=f"[DRY RUN] {check_result.reason}")
            
            if check_result.can_crystallize:
                return await self._executor.crystallize(gap.gap_id, force=self._config.force_crystallization)
            elif "should dismiss" in check_result.reason.lower():
                return await self._executor.dismiss(gap.gap_id, reason="No evidence during observation period")
            else:
                return CrystallizationResult(gap_id=gap.gap_id, student_id=gap.student_id, success=False,
                                            new_status=GapStatus.PENDING.value, reason=check_result.reason)
        except Exception as e:
            return CrystallizationResult(gap_id=gap.gap_id, student_id=gap.student_id, success=False,
                                        new_status=GapStatus.PENDING.value, reason=f"Processing error: {str(e)}")
    
    def _calculate_stats(self, results: List[CrystallizationResult]) -> Dict[str, int]:
        stats = {"crystallized": 0, "dismissed": 0, "failed": 0, "skipped": 0}
        for r in results:
            if r.success:
                if r.new_status == GapStatus.CRYSTALLIZED.value:
                    stats["crystallized"] += 1
                elif r.new_status == GapStatus.DISMISSED.value:
                    stats["dismissed"] += 1
                else:
                    stats["skipped"] += 1
            else:
                stats["failed"] += 1
        return stats
