"""变形题相关模型.

本模块包含变形题和变形题答题记录的ORM模型.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKey, Index,
                        String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.base import Base
from src.infrastructure.db.enums import ValidationStatus, VariantType

if TYPE_CHECKING:
    from src.domain.models.homework import Question
    from src.domain.models.student import Student


class VariantQuestion(Base):
    """变形题表."""

    __tablename__ = "variant_question"

    variant_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    original_question_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("question.question_id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="变形类型"
    )
    variant_content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="变形题内容"
    )
    validation_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=ValidationStatus.PENDING.value,
        comment="验证状态",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # 关系定义
    original_question: Mapped["Question"] = relationship(
        "Question", back_populates="variant_questions"
    )
    variant_answers: Mapped[List["VariantAnswer"]] = relationship(
        "VariantAnswer", back_populates="variant_question", cascade="all, delete-orphan"
    )

    # 约束和索引
    __table_args__ = (
        CheckConstraint(
            f"variant_type IN ('{VariantType.NUMERIC_CHANGE.value}', '{VariantType.INVERSE_OPERATION.value}', "
            f"'{VariantType.CONTEXT_TRANSFER.value}', '{VariantType.DIFFICULTY_ADJUST.value}', "
            f"'{VariantType.FORMAT_CHANGE.value}')",
            name="ck_variant_type",
        ),
        CheckConstraint(
            f"validation_status IN ('{ValidationStatus.PENDING.value}', '{ValidationStatus.VALIDATED.value}', "
            f"'{ValidationStatus.FAILED.value}', '{ValidationStatus.EXPIRED.value}')",
            name="ck_validation_status",
        ),
        Index("idx_variant_original", "original_question_id"),
        Index("idx_variant_status", "validation_status", "created_at"),
    )


class VariantAnswer(Base):
    """变形题答题记录表."""

    __tablename__ = "variant_answer"

    variant_answer_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    variant_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("variant_question.variant_id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False
    )
    answer_content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="答案内容"
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # 关系定义
    variant_question: Mapped["VariantQuestion"] = relationship(
        "VariantQuestion", back_populates="variant_answers"
    )
    student: Mapped["Student"] = relationship("Student")

    # 索引定义
    __table_args__ = (
        Index("idx_variant_answer_student", "student_id", "variant_id"),
        Index("idx_variant_answer_result", "variant_id", "is_correct"),
    )
