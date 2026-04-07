"""结晶监控模块.

监控结晶过程，提供告警和统计。

功能追溯ID: F-MEM-004
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from enum import Enum

from src.domain.models.base import now_timestamp


class AlertLevel(Enum):
    """告警级别."""
    
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class CrystallizationAlert:
    """结晶告警."""
    
    def __init__(
        self,
        alert_id: str,
        level: AlertLevel,
        message: str,
        gap_id: Optional[str] = None,
        student_id: Optional[str] = None,
    ):
        """初始化告警.
        
        Args:
            alert_id: 告警ID
            level: 级别
            message: 消息
            gap_id: 缺口ID
            student_id: 学生ID
        """
        self.alert_id = alert_id
        self.level = level
        self.message = message
        self.gap_id = gap_id
        self.student_id = student_id
        self.created_at = now_timestamp()
        self.acknowledged = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "alert_id": self.alert_id,
            "level": self.level.value,
            "message": self.message,
            "gap_id": self.gap_id,
            "student_id": self.student_id,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged,
        }


class CrystallizationMonitor:
    """结晶监控器.
    
    监控结晶过程，生成统计和告警。
    """
    
    # 告警阈值
    MAX_PENDING_HOURS = 48  # 待验证超过48小时告警
    MIN_CRYSTALLIZATION_RATE = 0.3  # 结晶率低于30%告警
    
    def __init__(self):
        """初始化监控器."""
        self._alerts: List[CrystallizationAlert] = []
        self._metrics_history: List[Dict[str, Any]] = []
        self._alert_handlers: List[Callable[[CrystallizationAlert], None]] = []
        self._alert_counter = 0
    
    def record_execution(self, execution_result: Dict[str, Any]) -> None:
        """记录执行结果.
        
        Args:
            execution_result: 执行结果
        """
        metric = {
            "timestamp": now_timestamp().isoformat(),
            "gaps_processed": execution_result.get("gaps_processed", 0),
            "success": execution_result.get("success", True),
        }
        
        self._metrics_history.append(metric)
        
        # 检查是否需要告警
        self._check_alerts(execution_result)
    
    def _check_alerts(self, result: Dict[str, Any]) -> None:
        """检查告警条件.
        
        Args:
            result: 执行结果
        """
        # 检查执行失败
        if not result.get("success", True):
            self._create_alert(
                level=AlertLevel.ERROR,
                message=f"Crystallization execution failed: {result.get('error', 'Unknown')}",
            )
        
        # 检查是否有长期pending的缺口
        gaps = result.get("gaps", [])
        for gap in gaps:
            pending_hours = gap.get("pending_hours", 0)
            if pending_hours > self.MAX_PENDING_HOURS:
                self._create_alert(
                    level=AlertLevel.WARNING,
                    message=f"Gap {gap.get('gap_id')} pending for {pending_hours:.1f} hours",
                    gap_id=gap.get("gap_id"),
                    student_id=gap.get("student_id"),
                )
    
    def _create_alert(
        self,
        level: AlertLevel,
        message: str,
        gap_id: Optional[str] = None,
        student_id: Optional[str] = None,
    ) -> CrystallizationAlert:
        """创建告警.
        
        Args:
            level: 级别
            message: 消息
            gap_id: 缺口ID
            student_id: 学生ID
            
        Returns:
            告警对象
        """
        self._alert_counter += 1
        alert = CrystallizationAlert(
            alert_id=f"alert_{self._alert_counter:04d}",
            level=level,
            message=message,
            gap_id=gap_id,
            student_id=student_id,
        )
        
        self._alerts.append(alert)
        
        # 通知处理器
        for handler in self._alert_handlers:
            handler(alert)
        
        return alert
    
    def add_alert_handler(
        self,
        handler: Callable[[CrystallizationAlert], None],
    ) -> None:
        """添加告警处理器.
        
        Args:
            handler: 处理器函数
        """
        self._alert_handlers.append(handler)
    
    def get_metrics(
        self,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """获取指标.
        
        Args:
            hours: 时间范围(小时)
            
        Returns:
            指标数据
        """
        cutoff = now_timestamp() - timedelta(hours=hours)
        
        recent_metrics = [
            m for m in self._metrics_history
            if datetime.fromisoformat(m["timestamp"]) > cutoff
        ]
        
        total = len(recent_metrics)
        successful = sum(1 for m in recent_metrics if m["success"])
        total_gaps = sum(m["gaps_processed"] for m in recent_metrics)
        
        return {
            "time_range_hours": hours,
            "total_executions": total,
            "successful_executions": successful,
            "failed_executions": total - successful,
            "total_gaps_processed": total_gaps,
            "avg_gaps_per_execution": total_gaps / total if total > 0 else 0,
            "success_rate": successful / total if total > 0 else 0,
        }
    
    def get_alerts(
        self,
        level: Optional[AlertLevel] = None,
        unacknowledged_only: bool = False,
    ) -> List[CrystallizationAlert]:
        """获取告警列表.
        
        Args:
            level: 级别过滤
            unacknowledged_only: 仅未确认
            
        Returns:
            告警列表
        """
        alerts = self._alerts
        
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]
        
        return alerts
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警.
        
        Args:
            alert_id: 告警ID
            
        Returns:
            是否成功
        """
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        
        return False
    
    def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态.
        
        Returns:
            健康状态
        """
        metrics = self.get_metrics(hours=24)
        
        # 确定状态
        if metrics["success_rate"] < 0.5:
            status = "critical"
        elif metrics["success_rate"] < 0.8:
            status = "warning"
        else:
            status = "healthy"
        
        # 未确认告警数
        unacknowledged = len(self.get_alerts(unacknowledged_only=True))
        
        return {
            "status": status,
            "success_rate_24h": metrics["success_rate"],
            "unacknowledged_alerts": unacknowledged,
            "last_execution": (
                self._metrics_history[-1]["timestamp"]
                if self._metrics_history else None
            ),
        }
