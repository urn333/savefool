"""Meta记忆层实现.

元认知层管理：
- 待验证缺口(pending gaps, 24小时观察期)
- 已固化认知特征(crystallized, ≥30天)

功能追溯ID: F-MEM-004, F-MEM-005
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from pydantic import Field

from src.domain.models.base import DomainModel, generate_id, now_timestamp
from src.domain.models.diagnosis import ErrorType
from src.infrastructure.db.cognitive_gap import CognitiveGap, GapEvidence
from src.infrastructure.db.enums import EvidenceType, GapStatus
from src.infrastructure.storage.repositories import (
    CognitiveGapRepository,
    ErrorDiagnosisRepository,
    GapEvidenceRepository,
)


# 结晶相关常量
CRYSTALLIZATION_PERIOD_HOURS = 24  # 待验证观察期
CRYSTALLIZATION_CONFIRMATION_DAYS = 30  # 完全固化天数


class PendingGap(DomainModel):
    """待验证认知缺口.
    
    处于24小时观察期的认知缺口。
    """
    
    gap_id: str = Field(default_factory=lambda: generate_id("gap"))
    student_id: str = Field(..., description="学生ID")
    
    # 缺口类型
    gap_type: str = Field(..., description="缺口类型")
    related_knowledge: List[str] = Field(
        default_factory=list,
        description="相关知识点",
    )
    
    # 观察期
    discovered_at: datetime = Field(
        default_factory=now_timestamp,
        description="发现时间",
    )
    observation_period_hours: int = Field(
        default=CRYSTALLIZATION_PERIOD_HOURS,
        description="观察期(小时)",
    )
    
    # 证据
    evidence_count: int = Field(
        default=1,
        ge=1,
        description="证据数量",
    )
    evidences: List[str] = Field(
        default_factory=list,
        description="证据ID列表",
    )
    
    # 状态
    status: str = Field(
        default=GapStatus.PENDING.value,
        description="状态",
    )
    
    @property
    def observation_end_time(self) -> datetime:
        """观察期结束时间.
        
        Returns:
            结束时间
        """
        return self.discovered_at + timedelta(hours=self.observation_period_hours)
    
    @property
    def is_observation_complete(self) -> bool:
        """观察期是否结束.
        
        Returns:
            是否结束
        """
        return now_timestamp() >= self.observation_end_time
    
    @property
    def remaining_hours(self) -> float:
        """剩余观察时间(小时).
        
        Returns:
            剩余小时数
        """
        remaining = (self.observation_end_time - now_timestamp()).total_seconds() / 3600
        return max(0, remaining)
    
    def add_evidence(self, evidence_id: str, evidence_type: EvidenceType) -> None:
        """添加证据.
        
        Args:
            evidence_id: 证据ID
            evidence_type: 证据类型
        """
        if evidence_id not in self.evidences:
            self.evidences.append(evidence_id)
            self.evidence_count += 1


class CrystallizedFeature(DomainModel):
    """已固化认知特征.
    
    经过验证并固化的认知特征(≥30天)。
    """
    
    feature_id: str = Field(default_factory=lambda: generate_id("feat"))
    student_id: str = Field(..., description="学生ID")
    
    # 特征类型
    feature_type: str = Field(..., description="特征类型")
    feature_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="特征数据",
    )
    
    # 时间线
    first_observed: datetime = Field(..., description="首次观察")
    crystallized_at: datetime = Field(
        default_factory=now_timestamp,
        description="固化时间",
    )
    
    # 置信度
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="置信度",
    )
    
    # 证据支持
    supporting_evidence: int = Field(
        default=1,
        ge=1,
        description="支持证据数量",
    )
    contradicting_evidence: int = Field(
        default=0,
        ge=0,
        description="矛盾证据数量",
    )
    
    @property
    def days_since_crystallization(self) -> int:
        """固化后天数.
        
        Returns:
            天数
        """
        return (now_timestamp() - self.crystallized_at).days
    
    @property
    def is_fully_crystallized(self) -> bool:
        """是否完全固化(≥30天).
        
        Returns:
            是否完全固化
        """
        return self.days_since_crystallization >= CRYSTALLIZATION_CONFIRMATION_DAYS
    
    def get_stability_score(self) -> float:
        """获取稳定性评分.
        
        Returns:
            稳定性分数(0-1)
        """
        total = self.supporting_evidence + self.contradicting_evidence
        if total == 0:
            return 0.5
        
        base_stability = self.supporting_evidence / total
        
        # 时间衰减：早期证据权重降低
        time_factor = min(1.0, self.days_since_crystallization / 30)
        
        return base_stability * 0.7 + time_factor * 0.3


class CrystallizationResult(DomainModel):
    """结晶结果.
    
    记录结晶过程的结果。
    """
    
    gap_id: str = Field(..., description="缺口ID")
    student_id: str = Field(..., description="学生ID")
    
    # 结果
    success: bool = Field(..., description="是否成功")
    new_status: str = Field(..., description="新状态")
    
    # 详情
    crystallized_at: datetime = Field(
        default_factory=now_timestamp,
        description="结晶时间",
    )
    feature_id: Optional[str] = Field(
        None,
        description="生成的特征ID",
    )
    reason: str = Field(..., description="原因/说明")


class MetaMemory:
    """Meta记忆层管理器.
    
    管理元认知数据，包括待验证缺口和已固化特征。
    实现24小时结晶机制。
    """
    
    def __init__(
        self,
        gap_repo: CognitiveGapRepository,
        evidence_repo: GapEvidenceRepository,
        diagnosis_repo: ErrorDiagnosisRepository,
    ):
        """初始化Meta记忆层.
        
        Args:
            gap_repo: 认知缺口Repository
            evidence_repo: 缺口证据Repository
            diagnosis_repo: 诊断Repository
        """
        self._gap_repo = gap_repo
        self._evidence_repo = evidence_repo
        self._diagnosis_repo = diagnosis_repo
        
        # 内存缓存
        self._pending_cache: Dict[str, PendingGap] = {}
        self._crystallized_cache: Dict[str, CrystallizedFeature] = {}
    
    async def create_pending_gap(
        self,
        student_id: str,
        gap_type: str,
        related_knowledge: List[str],
        diagnosis_id: str,
    ) -> PendingGap:
        """创建待验证缺口.
        
        Args:
            student_id: 学生ID
            gap_type: 缺口类型
            related_knowledge: 相关知识点
            diagnosis_id: 诊断ID
            
        Returns:
            待验证缺口
        """
        # 检查是否已有相同缺口
        existing = await self._gap_repo.find_one(
            student_id=student_id,
            gap_type=gap_type,
            status=GapStatus.PENDING.value,
        )
        
        if existing:
            # 更新现有缺口
            existing.occurrence_count += 1
            existing.updated_at = now_timestamp()
            await self._gap_repo.update(existing)
            
            # 添加证据
            evidence = GapEvidence(
                evidence_id=generate_id("evidence"),
                gap_id=existing.gap_id,
                diagnosis_id=diagnosis_id,
                evidence_type=EvidenceType.REPEAT_ERROR.value,
            )
            await self._evidence_repo.create(evidence)
            
            return PendingGap(
                gap_id=existing.gap_id,
                student_id=student_id,
                gap_type=gap_type,
                related_knowledge=related_knowledge,
                discovered_at=existing.discovered_at,
                evidence_count=existing.occurrence_count,
                status=existing.status,
            )
        
        # 创建新缺口
        gap = CognitiveGap(
            gap_id=generate_id("gap"),
            student_id=student_id,
            gap_type=gap_type,
            status=GapStatus.PENDING.value,
            related_knowledge=related_knowledge,
            occurrence_count=1,
        )
        await self._gap_repo.create(gap)
        
        # 添加初始证据
        evidence = GapEvidence(
            evidence_id=generate_id("evidence"),
            gap_id=gap.gap_id,
            diagnosis_id=diagnosis_id,
            evidence_type=EvidenceType.INITIAL_DIAGNOSIS.value,
        )
        await self._evidence_repo.create(evidence)
        
        pending_gap = PendingGap(
            gap_id=gap.gap_id,
            student_id=student_id,
            gap_type=gap_type,
            related_knowledge=related_knowledge,
            discovered_at=gap.discovered_at,
            evidences=[evidence.evidence_id],
        )
        
        # 缓存
        self._pending_cache[gap.gap_id] = pending_gap
        
        return pending_gap
    
    async def get_pending_gaps(
        self,
        student_id: Optional[str] = None,
    ) -> List[PendingGap]:
        """获取待验证缺口.
        
        Args:
            student_id: 学生ID(可选)
            
        Returns:
            待验证缺口列表
        """
        gaps = []
        
        if student_id:
            db_gaps = await self._gap_repo.find_many(
                student_id=student_id,
                status=GapStatus.PENDING.value,
            )
        else:
            # 获取所有待验证缺口
            db_gaps = await self._gap_repo.find_many(status=GapStatus.PENDING.value)
        
        for gap in db_gaps:
            # 获取证据
            evidences = await self._evidence_repo.find_many(gap_id=gap.gap_id)
            
            pending = PendingGap(
                gap_id=gap.gap_id,
                student_id=gap.student_id,
                gap_type=gap.gap_type,
                related_knowledge=gap.related_knowledge,
                discovered_at=gap.discovered_at,
                evidence_count=gap.occurrence_count,
                evidences=[e.evidence_id for e in evidences],
                status=gap.status,
            )
            gaps.append(pending)
        
        return gaps
    
    async def crystallize_gap(
        self,
        gap_id: str,
        force: bool = False,
    ) -> Optional[CrystallizationResult]:
        """结晶化认知缺口.
        
        Args:
            gap_id: 缺口ID
            force: 是否强制结晶(跳过观察期)
            
        Returns:
            结晶结果
        """
        # 获取缺口
        db_gap = await self._gap_repo.get_by_id(gap_id)
        if not db_gap:
            return None
        
        if db_gap.status != GapStatus.PENDING.value and not force:
            return CrystallizationResult(
                gap_id=gap_id,
                student_id=db_gap.student_id,
                success=False,
                new_status=db_gap.status,
                reason="Gap is not in pending status",
            )
        
        # 检查观察期
        pending_gap = self._pending_cache.get(gap_id)
        if not pending_gap:
            pending_gap = PendingGap(
                gap_id=db_gap.gap_id,
                student_id=db_gap.student_id,
                gap_type=db_gap.gap_type,
                related_knowledge=db_gap.related_knowledge,
                discovered_at=db_gap.discovered_at,
                evidence_count=db_gap.occurrence_count,
            )
        
        if not pending_gap.is_observation_complete and not force:
            return CrystallizationResult(
                gap_id=gap_id,
                student_id=db_gap.student_id,
                success=False,
                new_status=GapStatus.PENDING.value,
                reason=f"Observation period not complete, {pending_gap.remaining_hours:.1f} hours remaining",
            )
        
        # 执行结晶
        db_gap.status = GapStatus.CRYSTALLIZED.value
        db_gap.crystallized_at = now_timestamp()
        await self._gap_repo.update(db_gap)
        
        # 创建固化特征
        feature = CrystallizedFeature(
            student_id=db_gap.student_id,
            feature_type=f"cognitive_gap_{db_gap.gap_type}",
            feature_data={
                "gap_id": db_gap.gap_id,
                "gap_type": db_gap.gap_type,
                "related_knowledge": db_gap.related_knowledge,
                "occurrence_count": db_gap.occurrence_count,
            },
            first_observed=db_gap.discovered_at,
            crystallized_at=now_timestamp(),
            confidence=min(1.0, 0.5 + db_gap.occurrence_count * 0.1),
            supporting_evidence=db_gap.occurrence_count,
        )
        
        # 缓存并清理pending缓存
        self._crystallized_cache[feature.feature_id] = feature
        if gap_id in self._pending_cache:
            del self._pending_cache[gap_id]
        
        return CrystallizationResult(
            gap_id=gap_id,
            student_id=db_gap.student_id,
            success=True,
            new_status=GapStatus.CRYSTALLIZED.value,
            crystallized_at=now_timestamp(),
            feature_id=feature.feature_id,
            reason="Gap crystallized after observation period",
        )
    
    async def dismiss_gap(
        self,
        gap_id: str,
        reason: str = "",
    ) -> Optional[CrystallizationResult]:
        """排除认知缺口.
        
        Args:
            gap_id: 缺口ID
            reason: 排除原因
            
        Returns:
            处理结果
        """
        db_gap = await self._gap_repo.get_by_id(gap_id)
        if not db_gap:
            return None
        
        db_gap.status = GapStatus.DISMISSED.value
        await self._gap_repo.update(db_gap)
        
        # 清理缓存
        if gap_id in self._pending_cache:
            del self._pending_cache[gap_id]
        
        return CrystallizationResult(
            gap_id=gap_id,
            student_id=db_gap.student_id,
            success=True,
            new_status=GapStatus.DISMISSED.value,
            reason=reason or "Gap dismissed",
        )
    
    async def run_crystallization_batch(
        self,
        student_id: Optional[str] = None,
    ) -> List[CrystallizationResult]:
        """批量执行结晶.
        
        Args:
            student_id: 学生ID(可选，None则处理所有)
            
        Returns:
            结晶结果列表
        """
        results = []
        
        # 获取所有待验证缺口
        pending_gaps = await self.get_pending_gaps(student_id)
        
        for gap in pending_gaps:
            if gap.is_observation_complete:
                result = await self.crystallize_gap(gap.gap_id)
                if result:
                    results.append(result)
        
        return results
    
    async def get_crystallized_features(
        self,
        student_id: Optional[str] = None,
        min_days: int = 0,
    ) -> List[CrystallizedFeature]:
        """获取已固化特征.
        
        Args:
            student_id: 学生ID(可选)
            min_days: 最小固话天数
            
        Returns:
            固化特征列表
        """
        features = []
        
        # 从数据库获取已固化的缺口
        if student_id:
            db_gaps = await self._gap_repo.find_many(
                student_id=student_id,
                status=GapStatus.CRYSTALLIZED.value,
            )
        else:
            db_gaps = await self._gap_repo.find_many(
                status=GapStatus.CRYSTALLIZED.value,
            )
        
        for gap in db_gaps:
            if not gap.crystallized_at:
                continue
            
            days_since = (now_timestamp() - gap.crystallized_at).days
            if days_since < min_days:
                continue
            
            feature = CrystallizedFeature(
                student_id=gap.student_id,
                feature_type=f"cognitive_gap_{gap.gap_type}",
                feature_data={
                    "gap_id": gap.gap_id,
                    "gap_type": gap.gap_type,
                    "related_knowledge": gap.related_knowledge,
                },
                first_observed=gap.discovered_at,
                crystallized_at=gap.crystallized_at,
                supporting_evidence=gap.occurrence_count,
            )
            features.append(feature)
        
        return features
    
    async def get_crystallization_summary(
        self,
        student_id: str,
    ) -> Dict[str, Any]:
        """获取结晶状态摘要.
        
        Args:
            student_id: 学生ID
            
        Returns:
            状态摘要
        """
        pending = await self.get_pending_gaps(student_id)
        crystallized = await self.get_crystallized_features(student_id)
        
        fully_crystallized = [f for f in crystallized if f.is_fully_crystallized]
        
        return {
            "student_id": student_id,
            "pending_gaps_count": len(pending),
            "crystallized_features_count": len(crystallized),
            "fully_crystallized_count": len(fully_crystallized),
            "pending_details": [
                {
                    "gap_id": g.gap_id,
                    "gap_type": g.gap_type,
                    "remaining_hours": g.remaining_hours,
                    "evidence_count": g.evidence_count,
                }
                for g in pending
            ],
            "recent_crystallized": [
                {
                    "feature_id": f.feature_id,
                    "feature_type": f.feature_type,
                    "days_since": f.days_since_crystallization,
                    "confidence": f.confidence,
                }
                for f in sorted(
                    crystallized,
                    key=lambda x: x.crystallized_at,
                    reverse=True,
                )[:5]
            ],
        }
    
    def validate_data_flow(
        self,
        diagnosis_time: datetime,
        current_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """验证数据流完整性.
        
        根据设计的数据流向：
        诊断结果 → Episodic记录 → 24小时后 → Semantic汇总 → Meta结晶 → Profile更新
        
        Args:
            diagnosis_time: 诊断时间
            current_time: 当前时间(默认now)
            
        Returns:
            验证结果
        """
        current = current_time or now_timestamp()
        elapsed_hours = (current - diagnosis_time).total_seconds() / 3600
        
        status = {
            "diagnosis_recorded": True,
            "episodic_available": True,
            "semantic_pending": elapsed_hours < CRYSTALLIZATION_PERIOD_HOURS,
            "crystallization_ready": elapsed_hours >= CRYSTALLIZATION_PERIOD_HOURS,
            "profile_update_ready": elapsed_hours >= CRYSTALLIZATION_PERIOD_HOURS + 24,
            "elapsed_hours": elapsed_hours,
            "next_stage_in_hours": max(
                0,
                CRYSTALLIZATION_PERIOD_HOURS - elapsed_hours,
            ),
        }
        
        return status
