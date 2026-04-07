"""诊断相关领域模型.

定义诊断结果、错题、错误类型等核心业务模型。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator

from src.domain.models.base import DomainModel, generate_id, now_timestamp


class ErrorType(str, Enum):
    """错误类型枚举.

    根据系统设计文档定义的五类错误。
    """

    CONCEPT_MISUNDERSTANDING = "concept"
    CALCULATION_ERROR = "calculation"
    LOGICAL_FLAW = "logic"
    CARELESS_MISTAKE = "careless"
    KNOWLEDGE_GAP = "knowledge"


class DiagnosisStatus(str, Enum):
    """诊断状态枚举."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class Problem(DomainModel):
    """题目.

    表示作业中的单个题目。

    Attributes:
        id: 题目唯一ID
        content: 题目内容文本
        subject: 学科（math/physics/chemistry）
        difficulty: 难度等级（1-10）
        answer: 标准答案
        solution_steps: 标准解题步骤
        knowledge_points: 相关知识点ID列表
    """

    id: str = Field(default_factory=lambda: generate_id("prob"))
    content: str = Field(..., description="题目内容")
    subject: str = Field(..., description="学科")
    difficulty: int = Field(..., ge=1, le=10, description="难度等级")
    answer: Optional[str] = Field(None, description="标准答案")
    solution_steps: List[str] = Field(
        default_factory=list,
        description="标准解题步骤",
    )
    knowledge_points: List[str] = Field(
        default_factory=list,
        description="相关知识点ID列表",
    )
    image_url: Optional[str] = Field(None, description="题目图片URL")

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, v: str) -> str:
        """验证学科类型."""
        valid_subjects = {"math", "physics", "chemistry"}
        if v.lower() not in valid_subjects:
            raise ValueError(f"subject must be one of {valid_subjects}")
        return v.lower()


class RootCause(DomainModel):
    """错误根因.

    表示错误的根本原因分析结果。

    Attributes:
        error_type: 错误类型
        description: 原因描述
        concept_gaps: 相关概念缺口
        confidence: 分析置信度
    """

    error_type: ErrorType = Field(..., description="错误类型")
    description: str = Field(..., description="原因描述")
    concept_gaps: List[str] = Field(
        default_factory=list,
        description="概念缺口列表",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="分析置信度",
    )


class WrongProblem(DomainModel):
    """错题.

    表示被诊断出的错题信息。

    Attributes:
        problem_id: 题目ID
        error_type: 错误类型
        root_cause: 根本原因分析
        concept_gap: 概念缺口
        confidence: 诊断置信度
    """

    problem_id: str = Field(..., description="题目ID")
    error_type: ErrorType = Field(..., description="错误类型")
    root_cause: str = Field(..., description="根本原因分析")
    concept_gap: List[str] = Field(
        default_factory=list,
        description="概念缺口",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="诊断置信度",
    )
    student_answer: Optional[str] = Field(None, description="学生答案")
    error_position: Optional[Dict[str, Any]] = Field(
        None,
        description="错误位置坐标（图片中）",
    )


class ProblemDiagnosis(DomainModel):
    """单题诊断结果.

    Attributes:
        problem_id: 题目ID
        is_wrong: 是否错误
        error_type: 错误类型（如果是错题）
        root_cause: 根因分析（如果是错题）
        concept_gap: 概念缺口（如果是错题）
        confidence: 诊断置信度
    """

    problem_id: str = Field(..., description="题目ID")
    is_wrong: bool = Field(..., description="是否错误")
    error_type: Optional[ErrorType] = Field(
        None,
        description="错误类型",
    )
    root_cause: Optional[str] = Field(
        None,
        description="根因分析",
    )
    concept_gap: List[str] = Field(
        default_factory=list,
        description="概念缺口",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="诊断置信度",
    )


class DiagnosisResult(DomainModel):
    """诊断结果.

    表示完整作业诊断的结果。

    Attributes:
        task_id: 任务ID
        status: 诊断状态
        original_problems: 原题列表
        wrong_problems: 错题列表
        generated_variants: 生成的变形题
        knowledge_update: 知识图谱更新信息
        processing_time: 处理时间（秒）
        error: 错误信息（如果失败）
    """

    task_id: str = Field(..., description="任务ID")
    status: DiagnosisStatus = Field(
        default=DiagnosisStatus.COMPLETED,
        description="诊断状态",
    )
    original_problems: List[Problem] = Field(
        default_factory=list,
        description="原题列表",
    )
    wrong_problems: List[WrongProblem] = Field(
        default_factory=list,
        description="错题列表",
    )
    generated_variants: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="生成的变形题",
    )
    knowledge_update: Dict[str, Any] = Field(
        default_factory=dict,
        description="知识图谱更新信息",
    )
    processing_time: float = Field(
        default=0.0,
        description="处理时间（秒）",
    )
    error: Optional[Dict[str, Any]] = Field(
        None,
        description="错误信息（如果失败）",
    )
    created_at: datetime = Field(
        default_factory=now_timestamp,
        description="创建时间",
    )

    @property
    def has_wrong_problems(self) -> bool:
        """是否存在错题."""
        return len(self.wrong_problems) > 0

    @property
    def wrong_count(self) -> int:
        """错题数量."""
        return len(self.wrong_problems)

    @property
    def total_count(self) -> int:
        """总题数."""
        return len(self.original_problems)

    @property
    def accuracy_rate(self) -> float:
        """正确率."""
        if not self.original_problems:
            return 0.0
        return (self.total_count - self.wrong_count) / self.total_count
