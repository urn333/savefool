"""记忆数据自动压缩. 功能追溯ID: F-MEM-006"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from src.domain.models.base import now_timestamp
from src.infrastructure.db.enums import HomeworkStatus
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

@dataclass
class CompactionResult:
    compacted_count: int
    archived_count: int
    deleted_count: int
    bytes_saved: int
    errors: List[str]
    started_at: datetime
    completed_at: datetime
    
    @property
    def duration_seconds(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        return {"compacted_count": self.compacted_count, "archived_count": self.archived_count,
                "deleted_count": self.deleted_count, "bytes_saved": self.bytes_saved,
                "errors": self.errors, "duration_seconds": self.duration_seconds}

@dataclass
class CompressionConfig:
    episodic_retention_days: int = 30
    image_retention_days: int = 30
    min_compression_ratio: float = 0.6
    batch_size: int = 500
    batch_interval_seconds: int = 10
    dry_run: bool = False
    skip_image_compression: bool = False

class MemoryCompaction:
    def __init__(self, homework_repo, answer_repo, trace_repo, config=None):
        self._homework_repo = homework_repo
        self._answer_repo = answer_repo
        self._trace_repo = trace_repo
        self._config = config or CompressionConfig()
    
    async def run_compaction(self, before_date: Optional[datetime] = None) -> CompactionResult:
        started_at = now_timestamp()
        if before_date is None:
            before_date = started_at - timedelta(days=self._config.episodic_retention_days)
        
        result = CompactionResult(0, 0, 0, 0, [], started_at, started_at)
        
        try:
            episodic_result = await self.compact_episodic_memory(before_date)
            result.compacted_count += episodic_result.get("compacted_count", 0)
            result.bytes_saved += episodic_result.get("bytes_saved", 0)
            result.errors.extend(episodic_result.get("errors", []))
            
            if not self._config.skip_image_compression:
                image_result = await self.archive_homework_images(before_date)
                result.archived_count += image_result.get("archived_count", 0)
                result.bytes_saved += image_result.get("bytes_saved", 0)
                result.errors.extend(image_result.get("errors", []))
            
            cleanup_result = await self.cleanup_expired_archives(before_date)
            result.deleted_count += cleanup_result.get("deleted_count", 0)
            
            result.completed_at = now_timestamp()
            return result
        except Exception as e:
            result.errors.append(str(e))
            result.completed_at = now_timestamp()
            return result
    
    async def compact_episodic_memory(self, before_date: datetime) -> Dict[str, Any]:
        result = {"compacted_count": 0, "bytes_saved": 0, "errors": []}
        if self._config.dry_run:
            return result
        try:
            old_homeworks = await self._homework_repo.find_many(uploaded_at__lt=before_date)
            for homework in old_homeworks:
                try:
                    if homework.status != HomeworkStatus.ARCHIVED.value:
                        homework.status = HomeworkStatus.ARCHIVED.value
                        homework.archived_at = now_timestamp()
                        await self._homework_repo.update(homework)
                except Exception as e:
                    result["errors"].append(f"Failed to compact homework {homework.homework_id}: {e}")
            return result
        except Exception as e:
            result["errors"].append(f"Episodic memory compaction failed: {e}")
            return result
    
    async def archive_homework_images(self, before_date: datetime) -> Dict[str, Any]:
        return {"archived_count": 0, "bytes_saved": 0, "errors": []}
    
    async def cleanup_expired_archives(self, before_date: datetime) -> Dict[str, Any]:
        return {"deleted_count": 0, "errors": []}
    
    def estimate_compression_ratio(self, before_date: datetime) -> Dict[str, float]:
        return {"episodic_estimate": 0.7, "image_estimate": 0.6, "overall_estimate": 0.65}
