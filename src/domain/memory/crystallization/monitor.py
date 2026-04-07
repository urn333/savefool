"""结晶监控. 功能追溯ID: F-MEM-005, F-MEM-006"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from src.domain.models.base import now_timestamp
from src.infrastructure.db.enums import GapStatus
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

@dataclass
class CrystallizationMetrics:
    period_start: datetime
    period_end: datetime
    total_pending: int = 0
    total_crystallized: int = 0
    total_dismissed: int = 0
    crystallization_attempts: int = 0
    crystallization_successes: int = 0
    avg_observation_hours: float = 0.0
    max_observation_hours: float = 0.0
    evidence_per_gap: float = 0.0
    
    @property
    def success_rate(self) -> float:
        return self.crystallization_successes / max(self.crystallization_attempts, 1)
    
    def to_dict(self) -> Dict[str, Any]:
        return {"period_start": self.period_start.isoformat(), "period_end": self.period_end.isoformat(),
                "total_pending": self.total_pending, "total_crystallized": self.total_crystallized,
                "total_dismissed": self.total_dismissed, "success_rate": self.success_rate,
                "avg_observation_hours": self.avg_observation_hours, "max_observation_hours": self.max_observation_hours,
                "evidence_per_gap": self.evidence_per_gap}

@dataclass
class CompactionMetrics:
    period_start: datetime
    period_end: datetime
    total_compactions: int = 0
    total_compacted_records: int = 0
    total_archived_images: int = 0
    bytes_before: int = 0
    bytes_after: int = 0
    error_count: int = 0
    
    @property
    def compression_ratio(self) -> float:
        return 1 - (self.bytes_after / max(self.bytes_before, 1))
    
    @property
    def bytes_saved(self) -> int:
        return self.bytes_before - self.bytes_after
    
    def to_dict(self) -> Dict[str, Any]:
        return {"period_start": self.period_start.isoformat(), "period_end": self.period_end.isoformat(),
                "total_compactions": self.total_compactions, "total_compacted_records": self.total_compacted_records,
                "total_archived_images": self.total_archived_images, "compression_ratio": self.compression_ratio,
                "bytes_saved": self.bytes_saved, "error_count": self.error_count}

@dataclass
class AlertRule:
    name: str
    metric: str
    threshold: float
    operator: str
    severity: str
    message_template: str
    
    def check(self, value: float) -> bool:
        operators = {"<": lambda x, y: x < y, ">": lambda x, y: x > y, "<=": lambda x, y: x <= y,
                    ">=": lambda x, y: x >= y, "==": lambda x, y: x == y, "!=": lambda x, y: x != y}
        op = operators.get(self.operator)
        return op(value, self.threshold) if op else False

@dataclass
class Alert:
    alert_id: str
    rule_name: str
    severity: str
    message: str
    triggered_at: datetime
    metric_value: float
    threshold: float
    acknowledged: bool = False

class CrystallizationMonitor:
    DEFAULT_ALERT_RULES = [
        AlertRule("low_crystallization_rate", "crystallization_success_rate", 0.95, "<", "warning",
                 "Crystallization success rate is {value:.2%}, below threshold {threshold:.2%}"),
        AlertRule("high_pending_gaps", "pending_gaps_count", 1000, ">", "warning",
                 "Pending gaps count is {value}, above threshold {threshold}"),
        AlertRule("long_observation_time", "max_observation_hours", 72, ">", "info",
                 "Max observation time is {value:.1f} hours, consider manual review"),
        AlertRule("low_compression_ratio", "compression_ratio", 0.6, "<", "info",
                 "Compression ratio is {value:.2%}, below expected {threshold:.2%}"),
        AlertRule("high_error_rate", "error_rate", 0.05, ">", "critical",
                 "Error rate is {value:.2%}, above threshold {threshold:.2%}"),
    ]
    
    def __init__(self, gap_repo, evidence_repo, alert_rules=None):
        self._gap_repo = gap_repo
        self._evidence_repo = evidence_repo
        self._alert_rules = alert_rules or self.DEFAULT_ALERT_RULES.copy()
        self._alerts: List[Alert] = []
    
    async def collect_crystallization_metrics(self, period_hours: int = 24) -> CrystallizationMetrics:
        end_time = now_timestamp()
        start_time = end_time - timedelta(hours=period_hours)
        metrics = CrystallizationMetrics(period_start=start_time, period_end=end_time)
        
        try:
            pending_gaps = await self._gap_repo.find_many(status=GapStatus.PENDING.value)
            crystallized_gaps = await self._gap_repo.find_many(status=GapStatus.CRYSTALLIZED.value)
            dismissed_gaps = await self._gap_repo.find_many(status=GapStatus.DISMISSED.value)
            
            metrics.total_pending = len(pending_gaps)
            metrics.total_crystallized = len(crystallized_gaps)
            metrics.total_dismissed = len(dismissed_gaps)
            
            observation_hours = [(end_time - gap.discovered_at).total_seconds() / 3600 for gap in pending_gaps]
            if observation_hours:
                metrics.avg_observation_hours = sum(observation_hours) / len(observation_hours)
                metrics.max_observation_hours = max(observation_hours)
            
            total_evidence = 0
            for gap in pending_gaps:
                evidences = await self._evidence_repo.find_many(gap_id=gap.gap_id)
                total_evidence += len(evidences)
            if pending_gaps:
                metrics.evidence_per_gap = total_evidence / len(pending_gaps)
            
            metrics.crystallization_attempts = len(crystallized_gaps) + len(dismissed_gaps)
            metrics.crystallization_successes = len(crystallized_gaps)
        except Exception as e:
            logger.error(f"Failed to collect crystallization metrics: {e}")
        return metrics
    
    async def collect_compaction_metrics(self, period_days: int = 7) -> CompactionMetrics:
        end_time = now_timestamp()
        start_time = end_time - timedelta(days=period_days)
        return CompactionMetrics(period_start=start_time, period_end=end_time)
    
    async def check_alerts(self) -> List[Alert]:
        triggered_alerts = []
        crystallization_metrics = await self.collect_crystallization_metrics()
        compaction_metrics = await self.collect_compaction_metrics()
        
        metrics_dict = {"crystallization_success_rate": crystallization_metrics.success_rate,
                       "pending_gaps_count": crystallization_metrics.total_pending,
                       "avg_observation_hours": crystallization_metrics.avg_observation_hours,
                       "max_observation_hours": crystallization_metrics.max_observation_hours,
                       "compression_ratio": compaction_metrics.compression_ratio, "error_rate": 0.0}
        
        for rule in self._alert_rules:
            value = metrics_dict.get(rule.metric, 0)
            if rule.check(value):
                alert = Alert(f"alert_{now_timestamp().strftime('%Y%m%d_%H%M%S')}_{rule.name}",
                             rule.name, rule.severity, rule.message_template.format(value=value, threshold=rule.threshold),
                             now_timestamp(), value, rule.threshold)
                triggered_alerts.append(alert)
                self._alerts.append(alert)
                log_method = getattr(logger, rule.severity, logger.info)
                log_method(f"Alert triggered: {alert.message}")
        return triggered_alerts
    
    async def get_health_status(self) -> Dict[str, Any]:
        crystallization_metrics = await self.collect_crystallization_metrics()
        compaction_metrics = await self.collect_compaction_metrics()
        
        health_score = 1.0
        health_score *= 0.6 + 0.4 * crystallization_metrics.success_rate
        if crystallization_metrics.total_pending > 1000:
            health_score *= 0.8
        if crystallization_metrics.max_observation_hours > 72:
            health_score *= 0.9
        health_score *= 0.8 + 0.2 * compaction_metrics.compression_ratio
        
        status = "healthy" if health_score >= 0.9 else "degraded" if health_score >= 0.7 else "unhealthy"
        return {"status": status, "health_score": health_score,
                "crystallization": crystallization_metrics.to_dict(),
                "compaction": compaction_metrics.to_dict(),
                "active_alerts": len([a for a in self._alerts if not a.acknowledged])}
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False
    
    def get_active_alerts(self, severity: Optional[str] = None) -> List[Alert]:
        alerts = [a for a in self._alerts if not a.acknowledged]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return alerts
    
    async def generate_report(self, period_days: int = 7) -> Dict[str, Any]:
        crystallization_metrics = await self.collect_crystallization_metrics(period_hours=period_days * 24)
        compaction_metrics = await self.collect_compaction_metrics(period_days)
        health_status = await self.get_health_status()
        
        return {"generated_at": now_timestamp().isoformat(), "period_days": period_days,
                "health": health_status, "crystallization": crystallization_metrics.to_dict(),
                "compaction": compaction_metrics.to_dict(),
                "alerts": [{"alert_id": a.alert_id, "rule_name": a.rule_name, "severity": a.severity,
                           "message": a.message, "triggered_at": a.triggered_at.isoformat(),
                           "acknowledged": a.acknowledged} for a in self.get_active_alerts()]}
