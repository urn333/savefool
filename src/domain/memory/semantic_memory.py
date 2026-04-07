"""Semantic记忆层实现.

结构化知识存储：
- 知识点掌握度管理
- 概念误解记录
- 前置知识链

功能追溯ID: F-MEM-003
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import Field, field_validator

from src.domain.models.base import DomainModel, generate_id, now_timestamp
from src.domain.models.diagnosis import ErrorType
from src.domain.models.memory import (
    CompetencyMatrix,
    ConceptMastery,
    KnowledgePath,
    SemanticKnowledge,
    WeakPoint,
)
from src.infrastructure.db.enums import GapStatus
from src.infrastructure.db.knowledge import (
    KnowledgeDependency,
    KnowledgePoint,
    Misconception,
    StudentKnowledgeMastery,
)
from src.infrastructure.storage.repositories import (
    KnowledgeDependencyRepository,
    KnowledgePointRepository,
    MisconceptionRepository,
    StudentKnowledgeMasteryRepository,
)


class KnowledgeConcept(DomainModel):
    """知识概念.
    
    知识点的详细表示。
    """
    
    concept_id: str = Field(..., description="概念ID")
    name: str = Field(..., description="概念名称")
    subject: str = Field(..., description="学科")
    grade_level: str = Field(..., description="年级")
    description: Optional[str] = Field(None, description="描述")
    parent_id: Optional[str] = Field(None, description="父概念ID")
    
    # 个人掌握情况
    mastery_level: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="掌握程度",
    )
    practice_count: int = Field(
        default=0,
        ge=0,
        description="练习次数",
    )
    last_practiced: Optional[datetime] = Field(
        None,
        description="最后练习时间",
    )
    
    # 依赖关系
    prerequisites: List[str] = Field(
        default_factory=list,
        description="前置知识ID列表",
    )
    dependents: List[str] = Field(
        default_factory=list,
        description="后置知识ID列表",
    )


class MisconceptionRecord(DomainModel):
    """概念误解记录.
    
    记录学生对某个概念的具体误解模式。
    """
    
    record_id: str = Field(default_factory=lambda: generate_id("misc"))
    student_id: str = Field(..., description="学生ID")
    concept_id: str = Field(..., description="概念ID")
    
    # 误解详情
    pattern: str = Field(..., description="误解模式描述")
    correct_concept: str = Field(..., description="正确概念描述")
    
    # 验证状态
    verified_count: int = Field(
        default=1,
        ge=0,
        description="验证次数",
    )
    is_corrected: bool = Field(
        default=False,
        description="是否已纠正",
    )
    
    # 时间记录
    first_observed: datetime = Field(
        default_factory=now_timestamp,
        description="首次观察时间",
    )
    last_observed: datetime = Field(
        default_factory=now_timestamp,
        description="最近观察时间",
    )
    corrected_at: Optional[datetime] = Field(
        None,
        description="纠正时间",
    )
    
    def verify(self) -> None:
        """验证误解(再次出现)."""
        self.verified_count += 1
        self.last_observed = now_timestamp()
    
    def mark_corrected(self) -> None:
        """标记为已纠正."""
        self.is_corrected = True
        self.corrected_at = now_timestamp()


class PrerequisiteChain(DomainModel):
    """前置知识链.
    
    描述知识点之间的依赖关系链。
    """
    
    chain_id: str = Field(default_factory=lambda: generate_id("chain"))
    target_concept_id: str = Field(..., description="目标概念ID")
    
    # 链结构
    chain: List[str] = Field(
        default_factory=list,
        description="前置知识链(从基础到直接前置)",
    )
    
    # 掌握情况
    mastered_count: int = Field(
        default=0,
        ge=0,
        description="已掌握数量",
    )
    total_count: int = Field(
        default=0,
        ge=0,
        description="总数量",
    )
    
    # 阻塞点
    blockers: List[str] = Field(
        default_factory=list,
        description="阻塞掌握的前置知识",
    )
    
    @property
    def readiness_score(self) -> float:
        """学习准备度.
        
        Returns:
            准备度分数(0-1)
        """
        if self.total_count == 0:
            return 1.0
        return self.mastered_count / self.total_count
    
    @property
    def is_ready(self) -> bool:
        """是否准备好学习目标概念.
        
        Returns:
            是否准备就绪
        """
        return self.readiness_score >= 0.8 and len(self.blockers) == 0


class MasteryUpdate(DomainModel):
    """掌握度更新.
    
    记录掌握度的变化。
    """
    
    concept_id: str = Field(..., description="概念ID")
    old_level: float = Field(..., ge=0.0, le=1.0, description="原掌握度")
    new_level: float = Field(..., ge=0.0, le=1.0, description="新掌握度")
    reason: str = Field(..., description="更新原因")
    evidence: List[str] = Field(
        default_factory=list,
        description="证据ID列表",
    )
    updated_at: datetime = Field(
        default_factory=now_timestamp,
        description="更新时间",
    )
    
    @property
    def delta(self) -> float:
        """掌握度变化量.
        
        Returns:
            变化量
        """
        return self.new_level - self.old_level


class KnowledgeGraph(DomainModel):
    """个人知识图谱.
    
    学生的结构化知识网络。
    """
    
    student_id: str = Field(..., description="学生ID")
    version: int = Field(default=1, ge=1, description="版本号")
    
    # 节点和边
    concepts: Dict[str, KnowledgeConcept] = Field(
        default_factory=dict,
        description="概念节点",
    )
    paths: List[KnowledgePath] = Field(
        default_factory=list,
        description="知识路径",
    )
    
    # 薄弱点
    weak_points: List[WeakPoint] = Field(
        default_factory=list,
        description="薄弱点",
    )
    
    # 元数据
    last_updated: datetime = Field(
        default_factory=now_timestamp,
        description="最后更新时间",
    )
    
    def add_concept(self, concept: KnowledgeConcept) -> None:
        """添加概念节点.
        
        Args:
            concept: 知识概念
        """
        self.concepts[concept.concept_id] = concept
        self.last_updated = now_timestamp()
    
    def update_mastery(
        self,
        concept_id: str,
        new_level: float,
        reason: str = "",
    ) -> Optional[MasteryUpdate]:
        """更新概念掌握度.
        
        Args:
            concept_id: 概念ID
            new_level: 新掌握度
            reason: 更新原因
            
        Returns:
            更新记录
        """
        concept = self.concepts.get(concept_id)
        if not concept:
            return None
        
        old_level = concept.mastery_level
        concept.mastery_level = new_level
        concept.last_practiced = now_timestamp()
        concept.practice_count += 1
        
        self.last_updated = now_timestamp()
        
        return MasteryUpdate(
            concept_id=concept_id,
            old_level=old_level,
            new_level=new_level,
            reason=reason,
        )
    
    def identify_weak_points(self, threshold: float = 0.6) -> List[WeakPoint]:
        """识别薄弱点.
        
        Args:
            threshold: 掌握度阈值
            
        Returns:
            薄弱点列表
        """
        weak_points = []
        
        for concept_id, concept in self.concepts.items():
            if concept.mastery_level < threshold:
                # 查找相关错误类型
                related_errors = []
                
                weak_point = WeakPoint(
                    concept_id=concept_id,
                    severity=1.0 - concept.mastery_level,
                    occurrence_count=concept.practice_count,
                    last_occurrence=concept.last_practiced or now_timestamp(),
                    related_errors=related_errors,
                )
                weak_points.append(weak_point)
        
        # 按严重程度排序
        weak_points.sort(key=lambda wp: wp.severity, reverse=True)
        self.weak_points = weak_points
        
        return weak_points
    
    def get_prerequisite_chain(
        self,
        target_concept_id: str,
    ) -> Optional[PrerequisiteChain]:
        """获取前置知识链.
        
        Args:
            target_concept_id: 目标概念ID
            
        Returns:
            前置知识链
        """
        target = self.concepts.get(target_concept_id)
        if not target:
            return None
        
        chain = PrerequisiteChain(target_concept_id=target_concept_id)
        
        # 收集所有前置知识
        visited = set()
        queue = list(target.prerequisites)
        
        while queue:
            prereq_id = queue.pop(0)
            if prereq_id in visited:
                continue
            visited.add(prereq_id)
            chain.chain.append(prereq_id)
            
            prereq = self.concepts.get(prereq_id)
            if prereq:
                if prereq.mastery_level >= 0.7:
                    chain.mastered_count += 1
                else:
                    chain.blockers.append(prereq_id)
                queue.extend(prereq.prerequisites)
        
        chain.total_count = len(chain.chain)
        chain.chain.reverse()  # 从基础到直接前置
        
        return chain


class SemanticMemory:
    """Semantic记忆层管理器.
    
    管理结构化知识的存储和查询。
    """
    
    def __init__(
        self,
        knowledge_repo: KnowledgePointRepository,
        mastery_repo: StudentKnowledgeMasteryRepository,
        dependency_repo: KnowledgeDependencyRepository,
        misconception_repo: MisconceptionRepository,
    ):
        """初始化Semantic记忆层.
        
        Args:
            knowledge_repo: 知识点Repository
            mastery_repo: 学生知识掌握度Repository
            dependency_repo: 知识依赖Repository
            misconception_repo: 概念误解Repository
        """
        self._knowledge_repo = knowledge_repo
        self._mastery_repo = mastery_repo
        self._dependency_repo = dependency_repo
        self._misconception_repo = misconception_repo
    
    async def get_knowledge_graph(
        self,
        student_id: str,
    ) -> KnowledgeGraph:
        """获取学生知识图谱.
        
        Args:
            student_id: 学生ID
            
        Returns:
            知识图谱
        """
        graph = KnowledgeGraph(student_id=student_id)
        
        # 加载所有知识点
        all_knowledge = await self._knowledge_repo.get_all()
        
        # 加载学生掌握度
        masteries = await self._mastery_repo.find_many(student_id=student_id)
        mastery_map = {m.knowledge_id: m for m in masteries}
        
        # 加载依赖关系
        dependencies = await self._dependency_repo.get_all()
        
        # 构建概念节点
        for knowledge in all_knowledge:
            mastery = mastery_map.get(knowledge.knowledge_id)
            
            concept = KnowledgeConcept(
                concept_id=knowledge.knowledge_id,
                name=knowledge.knowledge_name,
                subject=knowledge.subject,
                grade_level=knowledge.grade_level,
                description=knowledge.description,
                parent_id=knowledge.parent_knowledge_id,
                mastery_level=mastery.mastery_level if mastery else 0.0,
                practice_count=mastery.practice_count if mastery else 0,
                last_practiced=mastery.last_practiced if mastery else None,
            )
            graph.add_concept(concept)
        
        # 建立依赖关系
        for dep in dependencies:
            concept = graph.concepts.get(dep.knowledge_id)
            prereq = graph.concepts.get(dep.prerequisite_id)
            
            if concept and prereq:
                concept.prerequisites.append(dep.prerequisite_id)
                prereq.dependents.append(dep.knowledge_id)
                
                # 添加知识路径
                path = KnowledgePath(
                    from_concept=dep.prerequisite_id,
                    to_concept=dep.knowledge_id,
                    transfer_strength=dep.dependency_strength,
                )
                graph.paths.append(path)
        
        # 识别薄弱点
        graph.identify_weak_points()
        
        return graph
    
    async def update_mastery(
        self,
        student_id: str,
        concept_id: str,
        new_level: float,
        reason: str = "",
    ) -> Optional[MasteryUpdate]:
        """更新知识掌握度.
        
        Args:
            student_id: 学生ID
            concept_id: 概念ID
            new_level: 新掌握度
            reason: 更新原因
            
        Returns:
            更新记录
        """
        # 查找现有记录
        existing = await self._mastery_repo.find_one(
            student_id=student_id,
            knowledge_id=concept_id,
        )
        
        old_level = existing.mastery_level if existing else 0.0
        
        if existing:
            existing.mastery_level = new_level
            existing.practice_count += 1
            existing.last_practiced = now_timestamp()
            await self._mastery_repo.update(existing)
        else:
            # 创建新记录
            new_mastery = StudentKnowledgeMastery(
                mastery_id=generate_id("mastery"),
                student_id=student_id,
                knowledge_id=concept_id,
                mastery_level=new_level,
                practice_count=1,
                last_practiced=now_timestamp(),
            )
            await self._mastery_repo.create(new_mastery)
        
        return MasteryUpdate(
            concept_id=concept_id,
            old_level=old_level,
            new_level=new_level,
            reason=reason,
        )
    
    async def record_misconception(
        self,
        student_id: str,
        concept_id: str,
        pattern: str,
        correct_concept: str,
    ) -> MisconceptionRecord:
        """记录概念误解.
        
        Args:
            student_id: 学生ID
            concept_id: 概念ID
            pattern: 误解模式
            correct_concept: 正确概念
            
        Returns:
            误解记录
        """
        # 检查是否已有相同误解记录
        existing = await self._misconception_repo.find_one(
            knowledge_id=concept_id,
        )
        
        if existing:
            # 更新验证次数
            existing.verified_count += 1
            await self._misconception_repo.update(existing)
            
            return MisconceptionRecord(
                record_id=existing.misconception_id,
                student_id=student_id,
                concept_id=concept_id,
                pattern=existing.misconception_pattern,
                correct_concept=existing.correct_concept,
                verified_count=existing.verified_count,
            )
        else:
            # 创建新记录
            new_misc = Misconception(
                misconception_id=generate_id("misc"),
                knowledge_id=concept_id,
                misconception_pattern=pattern,
                correct_concept=correct_concept,
                verified_count=1,
            )
            await self._misconception_repo.create(new_misc)
            
            return MisconceptionRecord(
                record_id=new_misc.misconception_id,
                student_id=student_id,
                concept_id=concept_id,
                pattern=pattern,
                correct_concept=correct_concept,
            )
    
    async def get_misconceptions(
        self,
        student_id: Optional[str] = None,
        concept_id: Optional[str] = None,
    ) -> List[MisconceptionRecord]:
        """获取概念误解记录.
        
        Args:
            student_id: 学生ID(可选)
            concept_id: 概念ID(可选)
            
        Returns:
            误解记录列表
        """
        records = []
        
        if concept_id:
            misc = await self._misconception_repo.find_one(knowledge_id=concept_id)
            if misc:
                records.append(MisconceptionRecord(
                    record_id=misc.misconception_id,
                    student_id=student_id or "",
                    concept_id=misc.knowledge_id,
                    pattern=misc.misconception_pattern,
                    correct_concept=misc.correct_concept,
                    verified_count=misc.verified_count,
                ))
        else:
            all_miscs = await self._misconception_repo.get_all()
            for misc in all_miscs:
                records.append(MisconceptionRecord(
                    record_id=misc.misconception_id,
                    student_id=student_id or "",
                    concept_id=misc.knowledge_id,
                    pattern=misc.misconception_pattern,
                    correct_concept=misc.correct_concept,
                    verified_count=misc.verified_count,
                ))
        
        return records
    
    async def get_prerequisite_chain(
        self,
        student_id: str,
        target_concept_id: str,
    ) -> Optional[PrerequisiteChain]:
        """获取前置知识链.
        
        Args:
            student_id: 学生ID
            target_concept_id: 目标概念ID
            
        Returns:
            前置知识链
        """
        graph = await self.get_knowledge_graph(student_id)
        return graph.get_prerequisite_chain(target_concept_id)
    
    async def get_weak_points(
        self,
        student_id: str,
        limit: int = 5,
    ) -> List[WeakPoint]:
        """获取薄弱点.
        
        Args:
            student_id: 学生ID
            limit: 返回数量限制
            
        Returns:
            薄弱点列表
        """
        graph = await self.get_knowledge_graph(student_id)
        return graph.weak_points[:limit]
    
    async def get_mastery_trend(
        self,
        student_id: str,
        concept_id: str,
        days: int = 30,
    ) -> List[Tuple[datetime, float]]:
        """获取掌握度趋势.
        
        Args:
            student_id: 学生ID
            concept_id: 概念ID
            days: 天数
            
        Returns:
            (时间,掌握度)列表
        """
        # 简化为返回当前掌握度
        # 实际实现需要查询历史记录表
        mastery = await self._mastery_repo.find_one(
            student_id=student_id,
            knowledge_id=concept_id,
        )
        
        if mastery:
            return [(mastery.last_practiced or now_timestamp(), mastery.mastery_level)]
        
        return []
