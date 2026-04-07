"""家长描述相关模型.

本模块包含家长描述和描述解析结果的ORM模型.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (JSON, CheckConstraint, DateTime, Float, ForeignKey,
                        Index, String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.base import Base
from src.infrastructure.db.enums import SourceType

if TYPE_CHECKING:
    from src.domain.models.student import Student


class ParentDescription(Base):
    """家长描述表."""

    __tablename__ = "parent_description"

    description_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    student_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False
    )
    raw_text: Mapped[str] = mapped_column(
        Text, nullable=False, comment="原始描述文本，敏感数据"
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SourceType.TEXT.value, comment="来源类型"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # 关系定义
    student: Mapped["Student"] = relationship(
        "Student", back_populates="parent_descriptions"
    )
    parse_result: Mapped[Optional["DescriptionParse"]] = relationship(
        "DescriptionParse",
        back_populates="parent_description",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # 约束和索引
    __table_args__ = (
        CheckConstraint(
            f"source_type IN ('{SourceType.TEXT.value}', '{SourceType.VOICE.value}', '{SourceType.VIDEO.value}')",
            name="ck_description_source",
        ),
        Index("idx_description_student", "student_id", "submitted_at"),
    )


class DescriptionParse(Base):
    """描述解析结果表."""

    __tablename__ = "description_parse"

    parse_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    description_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("parent_description.description_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    explicit_statements: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, comment="显性声明"
    )
    implicit_observations: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, comment="隐性观察"
    )
    confidence_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5, comment="解析置信度"
    )
    parsed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # 关系定义
    parent_description: Mapped["ParentDescription"] = relationship(
        "ParentDescription", back_populates="parse_result"
    )

    # 约束和索引
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_parse_confidence",
        ),
        Index("idx_parse_description", "description_id"),
        Index("idx_parse_confidence", "confidence_score"),
    )
