"""定时任务配置. 功能追溯ID: F-MEM-005, F-MEM-006"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from src.domain.memory.crystallization.compaction import CompactionResult, MemoryCompaction
from src.domain.memory.crystallization.monitor import CrystallizationMonitor
from src.domain.memory.crystallization.scheduler import SchedulerConfig, SchedulerRunResult
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

class CrystallizationJobManager:
    DEFAULT_CRON_CONFIG = {
        "daily_crystallization": {"hour": 2, "minute": 0, "day_of_week": "*"},
        "weekly_compaction": {"hour": 3, "minute": 0, "day_of_week": 0},
        "hourly_monitor": {"minute": 0},
    }
    
    def __init__(self, scheduler, compactor: Optional[MemoryCompaction] = None, monitor: Optional[CrystallizationMonitor] = None):
        self._scheduler = scheduler
        self._compactor = compactor
        self._monitor = monitor
        self._job_history: List[Dict[str, Any]] = []
    
    async def daily_crystallization_job(self) -> SchedulerRunResult:
        try:
            result = await self._scheduler.run_daily_crystallization()
            self._log_job_result("daily_crystallization", result)
            return result
        except Exception as e:
            logger.error(f"Daily crystallization job failed: {e}")
            raise
    
    async def weekly_compaction_job(self) -> CompactionResult:
        if not self._compactor:
            return CompactionResult(0, 0, 0, 0, ["Compactor not configured"], datetime.now(), datetime.now())
        try:
            result = await self._compactor.run_compaction()
            self._log_job_result("weekly_compaction", result)
            return result
        except Exception as e:
            logger.error(f"Weekly compaction job failed: {e}")
            raise
    
    async def hourly_monitor_job(self) -> Dict[str, Any]:
        if not self._monitor:
            return {"status": "skipped", "reason": "Monitor not configured"}
        try:
            alerts = await self._monitor.check_alerts()
            health = await self._monitor.get_health_status()
            result = {"timestamp": datetime.now().isoformat(), "health": health, "alerts_triggered": len(alerts)}
            self._log_job_result("hourly_monitor", result)
            return result
        except Exception as e:
            logger.error(f"Hourly monitor job failed: {e}")
            raise
    
    def get_job_definitions(self) -> Dict[str, Dict[str, Any]]:
        return {
            "daily_crystallization": {"name": "每日结晶任务", "schedule": self.DEFAULT_CRON_CONFIG["daily_crystallization"],
                                     "handler": self.daily_crystallization_job, "timeout_seconds": 7200},
            "weekly_compaction": {"name": "每周数据压缩", "schedule": self.DEFAULT_CRON_CONFIG["weekly_compaction"],
                                 "handler": self.weekly_compaction_job, "timeout_seconds": 14400},
            "hourly_monitor": {"name": "每小时监控", "schedule": self.DEFAULT_CRON_CONFIG["hourly_monitor"],
                              "handler": self.hourly_monitor_job, "timeout_seconds": 300},
        }
    
    def get_cron_expressions(self) -> Dict[str, str]:
        configs = self.DEFAULT_CRON_CONFIG
        return {
            "daily_crystallization": f"{configs['daily_crystallization']['minute']} {configs['daily_crystallization']['hour']} * * *",
            "weekly_compaction": f"{configs['weekly_compaction']['minute']} {configs['weekly_compaction']['hour']} * * {configs['weekly_compaction']['day_of_week']}",
            "hourly_monitor": f"{configs['hourly_monitor']['minute']} * * * *",
        }
    
    def _log_job_result(self, job_name: str, result: Any):
        log_entry = {"job_name": job_name, "executed_at": datetime.now().isoformat(),
                    "result_type": type(result).__name__,
                    "data": result.to_dict() if hasattr(result, "to_dict") else result.__dict__ if hasattr(result, "__dict__") else result}
        self._job_history.append(log_entry)
        if len(self._job_history) > 1000:
            self._job_history = self._job_history[-500:]
    
    def get_job_history(self, job_name: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        history = self._job_history
        if job_name:
            history = [h for h in history if h["job_name"] == job_name]
        return history[-limit:]
