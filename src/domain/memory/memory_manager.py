"""记忆管理器.

统一接口：
- 分层写入
- 智能查询
- 记忆压缩

功能追溯ID: F-MEM-007
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel, Field

from src.domain.memory.episodic_memory import (
    DecisionTrace,
    EpisodeQuery,
    EpisodicMemory,
    VariantLineage,
)
from src.domain.memory.meta_memory import (
    CRYSTALLIZATION_PERIOD_HOURS,
    CrystallizationResult,
    CrystallizedFeature,
    MetaMemory,
    PendingGap,
)
from src.domain.memory.profile_memory import (
    CognitiveFeatureVector,
    ErrorDNA,
    ProfileMemory,
    StudentCognitiveProfile,
    ThinkingStyle,
    ZPDBoundary,
)
from src.domain.memory.semantic_memory import (
    KnowledgeGraph,
    MasteryUpdate,
    MisconceptionRecord,
    PrerequisiteChain,
    SemanticMemory,
)
from src.domain.models.base import now_timestamp
from src.domain.models.diagnosis import ErrorType
from src.domain.models.memory import LearningEpisode, WeakPoint
from src.infrastructure.storage.repositories import (
    AnswerTraceRepository,
    CognitiveGapRepository,
    CognitiveProfileRepository,
    ErrorDiagnosisRepository,
    GapEvidenceRepository,
    KnowledgeDependencyRepository,
    KnowledgePointRepository,
    MisconceptionRepository,
    StudentAnswerRepository,
    StudentKnowledgeMasteryRepository,
    VariantAnswerRepository,
    VariantQuestionRepository,
)


class MemoryQuery(BaseModel):
    """统一记忆查询条件."""
    
    student_id: str = Field(..., description="学生ID")
    
    # 时间范围
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # 内容筛选
    subjects: List[str] = Field(default_factory=list)
    concept_ids: List[str] = Field(default_factory=list)
    
    # 层次筛选
    include_episodic: bool = True
    include_semantic: bool = True
    include_profile: bool = True
    include_meta: bool = True


class MemorySnapshot(BaseModel):
    """记忆快照.
    
    某一时刻学生完整记忆状态。
    """
    
    student_id: str = Field(..., description="学生ID")
    snapshot_time: datetime = Field(
        default_factory=now_timestamp,
        description="快照时间",
    )
    
    # 各层记忆
    profile: Optional[StudentCognitiveProfile] = None
    recent_episodes: List[LearningEpisode] = Field(default_factory=list)
    knowledge_graph: Optional[KnowledgeGraph] = None
    pending_gaps: List[PendingGap] = Field(default_factory=list)
    crystallized_features: List[CrystallizedFeature] = Field(default_factory=list)
    
    # 汇总信息
    summary: Dict[str, Any] = Field(default_factory=dict)


class CompressionResult(BaseModel):
    """记忆压缩结果."""
    
    original_size: int = Field(..., description="原始大小(条目数)")
    compressed_size: int = Field(..., description="压缩后大小(条目数)")
    compression_ratio: float = Field(..., description="压缩率")
    compressed_data: Dict[str, Any] = Field(default_factory=dict)


class MemoryManager:
    """记忆管理器.
    
    提供统一的记忆系统接口，管理四层记忆的协调和数据流。
    
    数据流向：
    诊断结果 → Episodic记录 → 24小时后 → Semantic汇总 → Meta结晶 → Profile更新
    """
    
    def __init__(
        self,
        # Profile层依赖
        profile_repo: CognitiveProfileRepository,
        # Episodic层依赖
        answer_repo: StudentAnswerRepository,
        trace_repo: AnswerTraceRepository,
        variant_repo: VariantQuestionRepository,
        variant_answer_repo: VariantAnswerRepository,
        # Semantic层依赖
        knowledge_repo: KnowledgePointRepository,
        mastery_repo: StudentKnowledgeMasteryRepository,
        dependency_repo: KnowledgeDependencyRepository,
        misconception_repo: MisconceptionRepository,
        # Meta层依赖
        gap_repo: CognitiveGapRepository,
        evidence_repo: GapEvidenceRepository,
        diagnosis_repo: ErrorDiagnosisRepository,
    ):
        """初始化记忆管理器.
        
        Args:
            profile_repo: 认知画像Repository
            answer_repo: 学生答案Repository
            trace_repo: 答题路径Repository
            variant_repo: 变形题Repository
            variant_answer_repo: 变形题答案Repository
            knowledge_repo: 知识点Repository
            mastery_repo: 学生知识掌握度Repository
            dependency_repo: 知识依赖Repository
            misconception_repo: 概念误解Repository
            gap_repo: 认知缺口Repository
            evidence_repo: 缺口证据Repository
            diagnosis_repo: 诊断Repository
        """
        # 初始化各层记忆
        self._profile = ProfileMemory(profile_repo, gap_repo)
        self._episodic = EpisodicMemory(
            answer_repo, trace_repo, variant_repo, variant_answer_repo
        )
        self._semantic = SemanticMemory(
            knowledge_repo, mastery_repo, dependency_repo, misconception_repo
        )
        self._meta = MetaMemory(gap_repo, evidence_repo, diagnosis_repo)
        
        # 保存repos供直接访问
        self._gap_repo = gap_repo
    
    # ==================== 统一写入接口 ====================
    
    async def record_problem_attempt(
        self,
        student_id: str,
        question_id: str,
        answer_content: str,
        is_correct: Optional[bool],
        time_spent: int = 0,
        confidence: float = 0.5,
        error_type: Optional[ErrorType] = None,
        decision_path: Optional[Dict[str, Any]] = None,
        concept_ids: List[str] = [],
    ) -> Dict[str, Any]:
        """记录解题尝试(统一入口).
        
        写入Episodic层，触发后续处理。
        
        Args:
            student_id: 学生ID
            question_id: 题目ID
            answer_content: 答案内容
            is_correct: 是否正确
            time_spent: 耗时(秒)
            confidence: 自信度
            error_type: 错误类型
            decision_path: 决策路径
            concept_ids: 相关概念ID
            
        Returns:
            记录结果
        """
        # 1. 记录到Episodic层
        episode = await self._episodic.record_attempt(
            student_id=student_id,
            question_id=question_id,
            answer_content=answer_content,
            is_correct=is_correct,
            time_spent=time_spent,
            confidence=confidence,
            error_type=error_type,
        )
        
        # 2. 记录决策路径
        if decision_path and episode.metadata.get("answer_id"):
            trace = await self._episodic.record_decision_trace(
                answer_id=episode.metadata["answer_id"],
                decision_path=decision_path,
            )
        else:
            trace = None
        
        # 3. 更新Semantic层(知识点掌握度)
        if is_correct is not None and concept_ids:
            for concept_id in concept_ids:
                await self._semantic.update_mastery(
                    student_id=student_id,
                    concept_id=concept_id,
                    new_level=1.0 if is_correct else 0.3,
                    reason="problem_attempt",
                )
        
        # 4. 如果有错误，创建待验证缺口
        pending_gap = None
        if error_type and not is_correct:
            pending_gap = await self._meta.create_pending_gap(
                student_id=student_id,
                gap_type=error_type.value,
                related_knowledge=concept_ids,
                diagnosis_id=episode.metadata.get("answer_id", ""),
            )
        
        return {
            "episode_id": episode.episode_id,
            "trace_id": trace.trace_id if trace else None,
            "pending_gap_id": pending_gap.gap_id if pending_gap else None,
            "status": "recorded",
            "crystallization_due": now_timestamp() + timedelta(
                hours=CRYSTALLIZATION_PERIOD_HOURS
            ),
        }
    
    async def record_variant_attempt(
        self,
        student_id: str,
        original_question_id: str,
        variant_id: str,
        variant_type: str,
        is_correct: bool,
    ) -> Dict[str, Any]:
        """记录变形题尝试.
        
        Args:
            student_id: 学生ID
            original_question_id: 原题ID
            variant_id: 变形题ID
            variant_type: 变形类型
            is_correct: 是否答对
            
        Returns:
            记录结果
        """
        # 1. 创建/更新血缘关系
        lineage = await self._episodic.create_variant_lineage(
            original_question_id=original_question_id,
            variant_id=variant_id,
            student_id=student_id,
            variant_type=variant_type,
        )
        
        # 2. 更新结果
        lineage = await self._episodic.update_variant_result(lineage, is_correct)
        
        # 3. 根据验证结果更新缺口状态
        if lineage.validation_outcome == "master":
            # 如果变形题也对了，可能是粗心，检查是否有对应缺口待关闭
            pass  # 实际实现需要查询并关闭相关缺口
        elif lineage.validation_outcome in ["needs_work", "misunderstanding"]:
            # 添加变形题作为额外证据
            gaps = await self._meta.get_pending_gaps(student_id)
            for gap in gaps:
                if any(kw in str(lineage.original_question_id) for kw in gap.related_knowledge):
                    gap.add_evidence(variant_id, "variant_failed")  # type: ignore
        
        return {
            "lineage_id": lineage.lineage_id,
            "validation_outcome": lineage.validation_outcome,
            "status": "recorded",
        }
    
    # ==================== 统一查询接口 ====================
    
    async def get_snapshot(
        self,
        student_id: str,
        include_episodes: bool = True,
        episode_hours: int = 24,
    ) -> MemorySnapshot:
        """获取学生记忆快照.
        
        Args:
            student_id: 学生ID
            include_episodes: 是否包含近期事件
            episode_hours: 事件时间范围
            
        Returns:
            记忆快照
        """
        snapshot = MemorySnapshot(student_id=student_id)
        
        # Profile层
        snapshot.profile = await self._profile.get_profile(student_id)
        
        # Episodic层
        if include_episodes:
            snapshot.recent_episodes = await self._episodic.get_recent_episodes(
                student_id, hours=episode_hours
            )
        
        # Semantic层
        snapshot.knowledge_graph = await self._semantic.get_knowledge_graph(student_id)
        
        # Meta层
        snapshot.pending_gaps = await self._meta.get_pending_gaps(student_id)
        snapshot.crystallized_features = await self._meta.get_crystallized_features(
            student_id
        )
        
        # 生成摘要
        snapshot.summary = self._generate_summary(snapshot)
        
        return snapshot
    
    async def query(
        self,
        query: MemoryQuery,
    ) -> Dict[str, Any]:
        """统一查询接口.
        
        Args:
            query: 查询条件
            
        Returns:
            查询结果
        """
        results = {
            "student_id": query.student_id,
            "query_time": now_timestamp().isoformat(),
        }
        
        # Profile层
        if query.include_profile:
            profile = await self._profile.get_profile(query.student_id)
            results["profile"] = {
                "exists": profile is not None,
                "thinking_style": profile.thinking_style.to_dict() if profile else None,
                "zpd_boundary": profile.zpd_boundary.to_dict() if profile else None,
            }
        
        # Episodic层
        if query.include_episodic:
            episodes = await self._episodic.get_episodes(
                EpisodeQuery(
                    student_id=query.student_id,
                    start_time=query.start_time,
                    end_time=query.end_time,
                ),
                limit=50,
            )
            results["episodes"] = {
                "count": len(episodes),
                "items": [ep.to_dict() for ep in episodes[:10]],  # 只返回前10个详情
            }
        
        # Semantic层
        if query.include_semantic:
            weak_points = await self._semantic.get_weak_points(
                query.student_id, limit=5
            )
            results["semantic"] = {
                "weak_points_count": len(weak_points),
                "top_weak_points": [
                    {
                        "concept_id": wp.concept_id,
                        "severity": wp.severity,
                    }
                    for wp in weak_points
                ],
            }
        
        # Meta层
        if query.include_meta:
            summary = await self._meta.get_crystallization_summary(query.student_id)
            results["meta"] = summary
        
        return results
    
    # ==================== 智能处理接口 ====================
    
    async def process_crystallization(
        self,
        student_id: Optional[str] = None,
    ) -> List[CrystallizationResult]:
        """处理记忆结晶.
        
        执行24小时结晶机制。
        
        Args:
            student_id: 学生ID(可选，None则处理所有)
            
        Returns:
            结晶结果列表
        """
        results = await self._meta.run_crystallization_batch(student_id)
        
        # 更新Profile层
        for result in results:
            if result.success and result.new_status == "crystallized":
                profile = await self._profile.get_profile(result.student_id)
                if profile:
                    profile.update_from_episodes([])
                    await self._profile.update_profile(profile)
        
        return results
    
    async def compress_episodic_memory(
        self,
        student_id: str,
        days: int = 30,
    ) -> CompressionResult:
        """压缩Episodic记忆.
        
        将旧的事件聚合并压缩。
        
        Args:
            student_id: 学生ID
            days: 压缩多少天以前的数据
            
        Returns:
            压缩结果
        """
        cutoff = now_timestamp() - timedelta(days=days)
        
        # 获取旧事件
        old_episodes = await self._episodic.get_episodes(
            EpisodeQuery(
                student_id=student_id,
                end_time=cutoff,
            ),
            limit=1000,
        )
        
        if not old_episodes:
            return CompressionResult(
                original_size=0,
                compressed_size=0,
                compression_ratio=0.0,
            )
        
        # 聚合统计
        aggregated = {
            "total_attempts": len(old_episodes),
            "correct_count": sum(
                1 for ep in old_episodes if ep.final_result == "correct"
            ),
            "incorrect_count": sum(
                1 for ep in old_episodes if ep.final_result == "incorrect"
            ),
            "subjects": list(set(ep.subject for ep in old_episodes if ep.subject)),
            "avg_confidence": sum(ep.confidence for ep in old_episodes)
            / len(old_episodes),
            "time_range": {
                "start": min(ep.timestamp for ep in old_episodes).isoformat(),
                "end": max(ep.timestamp for ep in old_episodes).isoformat(),
            },
        }
        
        return CompressionResult(
            original_size=len(old_episodes),
            compressed_size=1,  # 聚合为一条记录
            compression_ratio=(len(old_episodes) - 1) / len(old_episodes),
            compressed_data=aggregated,
        )
    
    # ==================== 辅助方法 ====================
    
    def _generate_summary(self, snapshot: MemorySnapshot) -> Dict[str, Any]:
        """生成记忆摘要.
        
        Args:
            snapshot: 记忆快照
            
        Returns:
            摘要信息
        """
        summary = {
            "student_id": snapshot.student_id,
            "snapshot_time": snapshot.snapshot_time.isoformat(),
        }
        
        # Profile摘要
        if snapshot.profile:
            summary["profile"] = {
                "cognitive_level": snapshot.profile.cognitive_level.overall,
                "thinking_style": snapshot.profile.thinking_style.get_dominant_style(),
                "zpd_optimal_difficulty": snapshot.profile.zpd_boundary.optimal_difficulty,
            }
        
        # Episodic摘要
        if snapshot.recent_episodes:
            summary["recent_activity"] = {
                "episode_count_24h": len(snapshot.recent_episodes),
                "accuracy_24h": sum(
                    1 for ep in snapshot.recent_episodes if ep.final_result == "correct"
                )
                / len(snapshot.recent_episodes),
            }
        
        # Semantic摘要
        if snapshot.knowledge_graph:
            weak_count = len(snapshot.knowledge_graph.weak_points)
            total_concepts = len(snapshot.knowledge_graph.concepts)
            summary["knowledge"] = {
                "total_concepts": total_concepts,
                "weak_points_count": weak_count,
                "mastery_rate": 1 - (weak_count / max(total_concepts, 1)),
            }
        
        # Meta摘要
        summary["crystallization"] = {
            "pending_gaps": len(snapshot.pending_gaps),
            "crystallized_features": len(snapshot.crystallized_features),
        }
        
        return summary
    
    # ==================== 直接访问各层 ====================
    
    @property
    def profile(self) -> ProfileMemory:
        """访问Profile层."""
        return self._profile
    
    @property
    def episodic(self) -> EpisodicMemory:
        """访问Episodic层."""
        return self._episodic
    
    @property
    def semantic(self) -> SemanticMemory:
        """访问Semantic层."""
        return self._semantic
    
    @property
    def meta(self) -> MetaMemory:
        """访问Meta层."""
        return self._meta
