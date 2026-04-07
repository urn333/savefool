"""记忆系统相关领域模型.

定义学生认知画像、学习事件、知识掌握状态等核心业务模型。
参考OpenHarness记忆系统设计。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator

from src.domain.models.base import DomainModel, generate_id, now_timestamp
from src.domain.models.diagnosis import ErrorType


class LearningEventType(str, Enum):
    """学习事件类型枚举."""

    PROBLEM_ATTEMPT = "attempt"
    VARIANT_PRACTICE = "variant"
    HINT_REQUEST = "hint"
    CONCEPT_REVIEW = "review"


class LearningStyle(DomainModel):
    """学习风格.

    学生的多维度学习偏好。
    """

    visual: float = Field(
        default=0.33,
        ge=0.0,
        le=1.0,
        description="视觉型偏好",
    )
    auditory: float = Field(
        default=0.33,
        ge=0.0,
        le=1.0,
        description="听觉型偏好",
    )
    kinesthetic: float = Field(
        default=0.34,
        ge=0.0,
        le=1.0,
        description="动觉型偏好",
    )

    @property
    def preference(self) -> str:
        """主要学习风格偏好."""
        scores = {
            "visual": self.visual,
            "auditory": self.auditory,
            "kinesthetic": self.kinesthetic,
        }
        max_style = max(scores.items(), key=lambda x: x[1])
        # 如果最高分和次高分差距很小，返回混合类型
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_scores) > 1 and sorted_scores[0][1] - sorted_scores[1][1] < 0.1:
            return "mixed"
        return max_style[0]


class CognitiveLevel(DomainModel):
    """认知水平.

    布鲁姆认知分类的量化评估。
    """

    overall: float = Field(
        default=5.0,
        ge=1.0,
        le=10.0,
        description="整体认知水平",
    )
    comprehension: float = Field(
        default=5.0,
        ge=1.0,
        le=10.0,
        description="理解能力",
    )
    application: float = Field(
        default=5.0,
        ge=1.0,
        le=10.0,
        description="应用能力",
    )
    analysis: float = Field(
        default=5.0,
        ge=1.0,
        le=10.0,
        description="分析能力",
    )
    synthesis: float = Field(
        default=5.0,
        ge=1.0,
        le=10.0,
        description="综合能力",
    )
    evaluation: float = Field(
        default=5.0,
        ge=1.0,
        le=10.0,
        description="评价能力",
    )


class ConceptStrength(DomainModel):
    """概念掌握强度.

    单个知识点的掌握情况。
    """

    concept_id: str = Field(..., description="概念ID")
    concept_name: str = Field(..., description="概念名称")
    mastery_level: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="掌握程度",
    )
    attempt_count: int = Field(
        default=0,
        ge=0,
        description="尝试次数",
    )
    success_count: int = Field(
        default=0,
        ge=0,
        description="成功次数",
    )
    success_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="成功率",
    )
    last_attempt_at: Optional[datetime] = Field(
        None,
        description="最后尝试时间",
    )

    @property
    def failure_count(self) -> int:
        """失败次数."""
        return self.attempt_count - self.success_count

    def record_attempt(self, success: bool) -> None:
        """记录一次尝试.

        Args:
            success: 是否成功
        """
        self.attempt_count += 1
        if success:
            self.success_count += 1
        # 更新成功率
        self.success_rate = self.success_count / self.attempt_count
        self.last_attempt_at = now_timestamp()
        # 使用贝叶斯更新掌握程度（简化版）
        alpha = 2 if success else 1
        beta = 1 if success else 2
        self.mastery_level = (self.mastery_level * alpha) / (
            self.mastery_level * alpha + (1 - self.mastery_level) * beta
        )


class MistakePattern(DomainModel):
    """错误模式.

    学生的典型错误特征。
    """

    error_type: ErrorType = Field(..., description="错误类型")
    occurrence_count: int = Field(
        default=1,
        ge=1,
        description="发生次数",
    )
    related_concepts: List[str] = Field(
        default_factory=list,
        description="相关概念",
    )
    first_occurred_at: datetime = Field(
        default_factory=now_timestamp,
        description="首次发生时间",
    )
    last_occurred_at: datetime = Field(
        default_factory=now_timestamp,
        description="最近发生时间",
    )


class StudentProfile(DomainModel):
    """学生认知画像.

    Profile层记忆：长期认知画像。
    """

    student_id: str = Field(..., description="学生ID")
    version: int = Field(
        default=1,
        ge=1,
        description="版本号",
    )
    cognitive_level: CognitiveLevel = Field(
        default_factory=CognitiveLevel,
        description="认知水平",
    )
    learning_style: LearningStyle = Field(
        default_factory=LearningStyle,
        description="学习风格",
    )
    weak_concepts: List[ConceptStrength] = Field(
        default_factory=list,
        description="薄弱概念",
    )
    strong_concepts: List[ConceptStrength] = Field(
        default_factory=list,
        description="强势概念",
    )
    recent_mistakes: List[MistakePattern] = Field(
        default_factory=list,
        description="近期错误模式",
    )
    last_updated: datetime = Field(
        default_factory=now_timestamp,
        description="最后更新时间",
    )

    def get_concept_mastery(self, concept_id: str) -> Optional[ConceptStrength]:
        """获取指定概念的掌握情况.

        Args:
            concept_id: 概念ID

        Returns:
            概念掌握情况，不存在则返回None
        """
        for concept in (*self.weak_concepts, *self.strong_concepts):
            if concept.concept_id == concept_id:
                return concept
        return None

    def update_concept_mastery(self, concept: ConceptStrength) -> None:
        """更新概念掌握情况.

        Args:
            concept: 概念掌握情况
        """
        # 根据掌握程度分类
        if concept.mastery_level < 0.6:
            target_list = self.weak_concepts
        else:
            target_list = self.strong_concepts

        # 查找并更新或添加
        for i, existing in enumerate(target_list):
            if existing.concept_id == concept.concept_id:
                target_list[i] = concept
                break
        else:
            target_list.append(concept)

        self.last_updated = now_timestamp()
        self.version += 1


class LearningEpisode(DomainModel):
    """学习事件.

    Episodic层记忆：作业事件流。
    """

    episode_id: str = Field(default_factory=lambda: generate_id("ep"))
    student_id: str = Field(..., description="学生ID")
    timestamp: datetime = Field(
        default_factory=now_timestamp,
        description="发生时间",
    )
    event_type: LearningEventType = Field(..., description="事件类型")
    homework_id: Optional[str] = Field(None, description="作业ID")
    problem_id: Optional[str] = Field(None, description="题目ID")
    subject: Optional[str] = Field(None, description="学科")
    difficulty: Optional[int] = Field(None, description="难度")
    concept_ids: List[str] = Field(
        default_factory=list,
        description="相关概念ID",
    )
    time_spent: int = Field(
        default=0,
        ge=0,
        description="耗时（秒）",
    )
    attempts: int = Field(
        default=1,
        ge=1,
        description="尝试次数",
    )
    hints_used: int = Field(
        default=0,
        ge=0,
        description="使用提示次数",
    )
    final_result: str = Field(
        default="unknown",
        description="最终结果 (correct/incorrect/abandoned)",
    )
    error_type: Optional[ErrorType] = Field(None, description="错误类型")
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="当时自信度",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="额外元数据",
    )


class ConceptMastery(DomainModel):
    """概念掌握详情.

    Semantic层记忆：概念掌握详情。
    """

    concept_id: str = Field(..., description="概念ID")
    concept_name: str = Field(..., description="概念名称")
    mastery_level: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="掌握程度",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="置信度",
    )
    evidence: List[str] = Field(
        default_factory=list,
        description="支持证据（episode_id列表）",
    )
    related_concepts: List[str] = Field(
        default_factory=list,
        description="关联概念",
    )
    last_updated: datetime = Field(
        default_factory=now_timestamp,
        description="最后更新时间",
    )


class KnowledgePath(DomainModel):
    """知识路径.

    知识点之间的迁移关系。
    """

    from_concept: str = Field(..., description="源概念ID")
    to_concept: str = Field(..., description="目标概念ID")
    transfer_strength: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="迁移强度",
    )
    evidence_count: int = Field(
        default=0,
        ge=0,
        description="证据数量",
    )


class WeakPoint(DomainModel):
    """薄弱点.

    学生知识薄弱环节。
    """

    concept_id: str = Field(..., description="概念ID")
    severity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="严重程度",
    )
    occurrence_count: int = Field(
        ...,
        ge=1,
        description="发生次数",
    )
    last_occurrence: datetime = Field(..., description="最近发生时间")
    related_errors: List[ErrorType] = Field(
        default_factory=list,
        description="相关错误类型",
    )


class SemanticKnowledge(DomainModel):
    """结构化知识.

    Semantic层记忆：概念掌握图谱和知识路径。
    """

    student_id: str = Field(..., description="学生ID")
    concept_mastery: List[ConceptMastery] = Field(
        default_factory=list,
        description="概念掌握详情",
    )
    knowledge_paths: List[KnowledgePath] = Field(
        default_factory=list,
        description="知识路径",
    )
    weak_points: List[WeakPoint] = Field(
        default_factory=list,
        description="薄弱点",
    )
    last_updated: datetime = Field(
        default_factory=now_timestamp,
        description="最后更新时间",
    )

    def get_concept(self, concept_id: str) -> Optional[ConceptMastery]:
        """获取指定概念.

        Args:
            concept_id: 概念ID

        Returns:
            概念掌握详情，不存在则返回None
        """
        for concept in self.concept_mastery:
            if concept.concept_id == concept_id:
                return concept
        return None

    def update_concept(self, concept: ConceptMastery) -> None:
        """更新概念.

        Args:
            concept: 概念掌握详情
        """
        for i, existing in enumerate(self.concept_mastery):
            if existing.concept_id == concept.concept_id:
                self.concept_mastery[i] = concept
                break
        else:
            self.concept_mastery.append(concept)

        self.last_updated = now_timestamp()


class CompetencyMatrix(DomainModel):
    """能力维度矩阵.

    学生在各能力维度的表现。
    """

    concept_id: str = Field(..., description="概念ID")
    mastery_level: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="掌握程度",
    )
    stability: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="稳定性",
    )
    last_assessed: datetime = Field(
        default_factory=now_timestamp,
        description="最后评估时间",
    )
