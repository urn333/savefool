"""答题相关模型.

本模块包含学生答案、答题路径和错题诊断的ORM模型.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (JSON, Boolean, CheckConstraint, DateTime, Float,
                        ForeignKey, Index, Integer, String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.base import Base
from src.infrastructure.db.enums import ErrorType

if TYPE_CHECKING:
    from src.domain.models.cognitive_gap import GapEvidence
    from src.domain.models.homework import Question
    from src.domain.models.student import Student


class StudentAnswer(Base):
    """学生答案表."""

    __tablename__ = "student_answer"

    answer_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    question_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("question.question_id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False
    )
    answer_content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="答案内容"
    )
    answered_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    is_correct: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, comment="是否正确"
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="置信度",
        info={"check": "confidence_score >= 0 AND confidence_score <= 1"},
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # 关系定义
    question: Mapped["Question"] = relationship("Question", back_populates="answers")
    student: Mapped["Student"] = relationship("Student", back_populates="answers")
    trace: Mapped[Optional["AnswerTrace"]] = relationship(
        "AnswerTrace",
        back_populates="answer",
        uselist=False,
        cascade="all, delete-orphan",
    )
    error_diagnoses: Mapped[List["ErrorDiagnosis"]] = relationship(
        "ErrorDiagnosis", back_populates="answer", cascade="all, delete-orphan"
    )

    # 约束和索引
    __table_args__ = (
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="ck_answer_confidence",
        ),
        Index("idx_answer_student", "student_id", "answered_at"),
        Index("idx_answer_question", "question_id"),
        Index("idx_answer_correct", "student_id", "is_correct", "answered_at"),
    )


class AnswerTrace(Base):
    """答题决策路径表."""

    __tablename__ = "answer_trace"

    trace_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    answer_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("student_answer.answer_id", ondelete="CASCADE"),
        nullable=False,
    )
    decision_path: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="决策路径详情"
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # 关系定义
    answer: Mapped["StudentAnswer"] = relationship(
        "StudentAnswer", back_populates="trace"
    )

    # 索引定义
    __table_args__ = (Index("idx_trace_answer", "answer_id"),)


class ErrorDiagnosis(Base):
    """错题诊断表."""

    __tablename__ = "error_diagnosis"

    diagnosis_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    answer_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("student_answer.answer_id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("question.question_id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False
    )
    error_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="错因类型"
    )
    knowledge_tags: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, comment="考点标签"
    )
    confidence_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5, comment="诊断置信度"
    )
    diagnosis_path: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="诊断选项路径摘要"
    )
    diagnosed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # 关系定义
    answer: Mapped["StudentAnswer"] = relationship(
        "StudentAnswer", back_populates="error_diagnoses"
    )
    diagnosis_paths: Mapped[List["DiagnosisPath"]] = relationship(
        "DiagnosisPath", back_populates="diagnosis", cascade="all, delete-orphan"
    )
    gap_evidences: Mapped[List["GapEvidence"]] = relationship(
        "GapEvidence", back_populates="diagnosis", cascade="all, delete-orphan"
    )

    # 约束和索引
    __table_args__ = (
        CheckConstraint(
            f"error_type IN ('{ErrorType.CARELESS.value}', '{ErrorType.METHOD_ERROR.value}', "
            f"'{ErrorType.CONCEPT_GAP.value}', '{ErrorType.CALCULATION_ERROR.value}', "
            f"'{ErrorType.READING_ERROR.value}', '{ErrorType.UNKNOWN.value}')",
            name="ck_diagnosis_error_type",
        ),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_diagnosis_confidence",
        ),
        Index("idx_diagnosis_student", "student_id", "diagnosed_at"),
        Index("idx_diagnosis_error_type", "student_id", "error_type", "diagnosed_at"),
        Index("idx_diagnosis_confidence", "confidence_score"),
    )


class DiagnosisPath(Base):
    """诊断选项路径详情表."""

    __tablename__ = "diagnosis_path"

    path_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    diagnosis_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("error_diagnosis.diagnosis_id", ondelete="CASCADE"),
        nullable=False,
    )
    step_number: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="步骤序号"
    )
    option_selected: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="选择的选项"
    )
    reasoning: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="选择理由"
    )

    # 关系定义
    diagnosis: Mapped["ErrorDiagnosis"] = relationship(
        "ErrorDiagnosis", back_populates="diagnosis_paths"
    )

    # 约束和索引
    __table_args__ = (
        CheckConstraint("step_number > 0", name="ck_path_step_number"),
        Index("idx_path_diagnosis", "diagnosis_id", "step_number"),
    )


# 延迟导入以避免循环依赖
from src.infrastructure.db.cognitive_gap import GapEvidence  # noqa: E402
