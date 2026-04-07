"""结晶执行器模块.

执行结晶过程:
- 状态流转
- Profile更新
- 证据链完整性保证

功能追溯ID: F-MEM-005
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.domain.models.base import generate_id, now_timestamp
from src.domain.memory.crystallization.conditions import CrystallizationConditions
from src.infrastructure.db.enums import EvidenceType, GapStatus


class CrystallizationRecord:
    """结晶执行记录.
    
    记录一次结晶执行的完整信息。
    """
    
    def __init__(
        self,
        gap_id: str,
        student_id: str,
        old_status: str,
        new_status: str,
        triggered_conditions: List[str],
        executed_at: Optional[datetime] = None,
    ):
        """初始化记录.
        
        Args:
            gap_id: 缺口ID
            student_id: 学生ID
            old_status: 旧状态
            new_status: 新状态
            triggered_conditions: 触发的条件
            executed_at: 执行时间
        """
        self.record_id = generate_id("crys_rec")
        self.gap_id = gap_id
        self.student_id = student_id
        self.old_status = old_status
        self.new_status = new_status
        self.triggered_conditions = triggered_conditions
        self.executed_at = executed_at or now_timestamp()
        self.evidence_chain: List[str] = []
        self.profile_updates: Dict[str, Any] = {}
    
    def add_evidence(self, evidence_id: str) -> None:
        """添加证据到链.
        
        Args:
            evidence_id: 证据ID
        """
        self.evidence_chain.append(evidence_id)
    
    def add_profile_update(self, field: str, old_value: Any, new_value: Any) -> None:
        """添加Profile更新记录.
        
        Args:
            field: 字段名
            old_value: 旧值
            new_value: 新值
        """
        self.profile_updates[field] = {
            "old": old_value,
            "new": new_value,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典.
        
        Returns:
            字典表示
        """
        return {
            "record_id": self.record_id,
            "gap_id": self.gap_id,
            "student_id": self.student_id,
            "old_status": self.old_status,
            "new_status": self.new_status,
            "triggered_conditions": self.triggered_conditions,
            "evidence_chain": self.evidence_chain,
            "profile_updates": self.profile_updates,
            "executed_at": self.executed_at.isoformat(),
        }


class CrystallizationExecutor:
    """结晶执行器.
    
    执行认知缺口的结晶过程。
    """
    
    def __init__(self):
        """初始化执行器."""
        self._conditions = CrystallizationConditions()
        self._execution_history: List[CrystallizationRecord] = []
    
    async def execute(
        self,
        gap_data: Dict[str, Any],
        evidences: List[Dict[str, Any]],
        profile_data: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> CrystallizationRecord:
        """执行结晶.
        
        Args:
            gap_data: 缺口数据
            evidences: 证据列表
            profile_data: 学生画像数据(可选)
            force: 是否强制结晶
            
        Returns:
            执行记录
        """
        current_time = now_timestamp()
        
        # 判定条件
        if not force:
            condition_result = self._conditions.check_all_conditions(
                gap_data, evidences, current_time
            )
        else:
            condition_result = {
                "should_crystallize": True,
                "should_dismiss": False,
                "conditions": {},
                "triggered": ["forced"],
                "reason": "Forced crystallization",
            }
        
        # 确定新状态
        old_status = gap_data.get("status", GapStatus.PENDING.value)
        
        if condition_result["should_crystallize"]:
            new_status = GapStatus.CRYSTALLIZED.value
        elif condition_result["should_dismiss"]:
            new_status = GapStatus.DISMISSED.value
        else:
            new_status = old_status
        
        # 创建执行记录
        record = CrystallizationRecord(
            gap_id=gap_data.get("gap_id", ""),
            student_id=gap_data.get("student_id", ""),
            old_status=old_status,
            new_status=new_status,
            triggered_conditions=condition_result.get("triggered", []),
            executed_at=current_time,
        )
        
        # 添加证据链
        for evidence in evidences:
            evidence_id = evidence.get("evidence_id")
            if evidence_id:
                record.add_evidence(evidence_id)
        
        # 如果状态改变，更新Profile
        if new_status != old_status and profile_data:
            profile_updates = self._update_profile(
                profile_data, gap_data, new_status, evidences
            )
            for field, update in profile_updates.items():
                record.add_profile_update(
                    field, update["old"], update["new"]
                )
        
        # 保存记录
        self._execution_history.append(record)
        
        return record
    
    def _update_profile(
        self,
        profile_data: Dict[str, Any],
        gap_data: Dict[str, Any],
        new_status: str,
        evidences: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """更新学生画像.
        
        Args:
            profile_data: 画像数据
            gap_data: 缺口数据
            new_status: 新状态
            evidences: 证据列表
            
        Returns:
            更新字段
        """
        updates = {}
        
        if new_status == GapStatus.CRYSTALLIZED.value:
            # 更新错误DNA
            error_dna = profile_data.get("error_dna", {})
            old_patterns = error_dna.get("error_patterns", [])
            
            gap_type = gap_data.get("gap_type", "unknown")
            new_pattern = {
                "error_type": gap_type,
                "occurrence_count": gap_data.get("occurrence_count", 1),
                "crystallized_at": now_timestamp().isoformat(),
            }
            
            updates["error_dna.error_patterns"] = {
                "old": old_patterns,
                "new": old_patterns + [new_pattern],
            }
            
            # 更新ZPD边界
            zpd = profile_data.get("zpd_boundary", {})
            old_independent = zpd.get("independent_level", 0.6)
            
            # 根据错误类型调整ZPD
            if gap_type in ["concept_gap", "method_error"]:
                new_independent = max(0.3, old_independent - 0.05)
                updates["zpd_boundary.independent_level"] = {
                    "old": old_independent,
                    "new": new_independent,
                }
        
        return updates
    
    def validate_evidence_chain(
        self,
        gap_data: Dict[str, Any],
        evidences: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """验证证据链完整性.
        
        Args:
            gap_data: 缺口数据
            evidences: 证据列表
            
        Returns:
            验证结果
        """
        validation = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "stats": {
                "total_evidences": len(evidences),
                "initial_diagnosis": 0,
                "repeat_errors": 0,
                "variant_failed": 0,
                "cross_homework": 0,
            },
        }
        
        # 检查是否有初始诊断证据
        has_initial = any(
            e.get("evidence_type") == EvidenceType.INITIAL_DIAGNOSIS.value
            for e in evidences
        )
        
        if not has_initial:
            validation["errors"].append("Missing initial diagnosis evidence")
            validation["is_valid"] = False
        
        # 统计各类型证据
        for evidence in evidences:
            evidence_type = evidence.get("evidence_type", "")
            if evidence_type == EvidenceType.INITIAL_DIAGNOSIS.value:
                validation["stats"]["initial_diagnosis"] += 1
            elif evidence_type == EvidenceType.REPEAT_ERROR.value:
                validation["stats"]["repeat_errors"] += 1
            elif evidence_type == EvidenceType.VARIANT_FAILED.value:
                validation["stats"]["variant_failed"] += 1
            elif evidence_type == EvidenceType.CROSS_HOMEWORK.value:
                validation["stats"]["cross_homework"] += 1
        
        # 检查证据关联
        gap_id = gap_data.get("gap_id", "")
        for evidence in evidences:
            if evidence.get("gap_id") != gap_id:
                validation["warnings"].append(
                    f"Evidence {evidence.get('evidence_id')} gap_id mismatch"
                )
        
        return validation
    
    def get_execution_history(
        self,
        student_id: Optional[str] = None,
        gap_id: Optional[str] = None,
    ) -> List[CrystallizationRecord]:
        """获取执行历史.
        
        Args:
            student_id: 学生ID过滤
            gap_id: 缺口ID过滤
            
        Returns:
            执行记录列表
        """
        records = self._execution_history
        
        if student_id:
            records = [r for r in records if r.student_id == student_id]
        
        if gap_id:
            records = [r for r in records if r.gap_id == gap_id]
        
        return records
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """获取执行摘要.
        
        Returns:
            执行摘要
        """
        total = len(self._execution_history)
        crystallized = len([
            r for r in self._execution_history
            if r.new_status == GapStatus.CRYSTALLIZED.value
        ])
        dismissed = len([
            r for r in self._execution_history
            if r.new_status == GapStatus.DISMISSED.value
        ])
        unchanged = total - crystallized - dismissed
        
        return {
            "total_executions": total,
            "crystallized": crystallized,
            "dismissed": dismissed,
            "unchanged": unchanged,
            "success_rate": crystallized / total if total > 0 else 0,
        }
