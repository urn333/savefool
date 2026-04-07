"""学生相关模型.

本模块包含学生和学生认知画像的ORM模型.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.base import Base

if TYPE_CHECKING:
    from src.domain.models.answer import StudentAnswer
    from src.domain.models.cognitive_gap import CognitiveGap
    from src.domain.models.homework import Homework
    from src.domain.models.knowledge import StudentKnowledgeMastery
    from src.domain.models.parent import ParentDescription


class Student(Base):
    """学生基本信息表."""

    __tablename__ = "student"

    student_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="学生姓名，敏感数据"
    )
    grade: Mapped[str] = mapped_column(String(16), nullable=False, comment="年级")
    preferred_subjects: Mapped[Optional[list]] = mapped_column(
        JSON, default=list, comment="学科偏好列表"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # 关系定义
    cognitive_profile: Mapped[Optional["CognitiveProfile"]] = relationship(
        "CognitiveProfile",
        back_populates="student",
        uselist=False,
        cascade="all, delete-orphan",
    )
    homeworks: Mapped[List["Homework"]] = relationship(
        "Homework", back_populates="student", cascade="all, delete-orphan"
    )
    answers: Mapped[List["StudentAnswer"]] = relationship(
        "StudentAnswer", back_populates="student", cascade="all, delete-orphan"
    )
    knowledge_masteries: Mapped[List["StudentKnowledgeMastery"]] = relationship(
        "StudentKnowledgeMastery",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    cognitive_gaps: Mapped[List["CognitiveGap"]] = relationship(
        "CognitiveGap", back_populates="student", cascade="all, delete-orphan"
    )
    parent_descriptions: Mapped[List["ParentDescription"]] = relationship(
        "ParentDescription", back_populates="student", cascade="all, delete-orphan"
    )

    # 索引定义
    __table_args__ = (
        Index("idx_student_grade", "grade"),
        Index("idx_student_updated", "updated_at"),
    )


class CognitiveProfile(Base):
    """学生认知画像表."""

    __tablename__ = "cognitive_profile"

    profile_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    student_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("student.student_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    thinking_style: Mapped[Optional[dict]] = mapped_column(
        JSON, default=dict, comment="思维风格特征"
    )
    error_dna: Mapped[Optional[dict]] = mapped_column(
        JSON, default=dict, comment="错误DNA模式"
    )
    zpd_boundary: Mapped[Optional[dict]] = mapped_column(
        JSON, default=dict, comment="最近发展区边界"
    )
    cognitive_features: Mapped[Optional[dict]] = mapped_column(
        JSON, default=dict, comment="认知特征向量"
    )
    crystallized_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="固化时间"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # 关系定义
    student: Mapped["Student"] = relationship(
        "Student", back_populates="cognitive_profile"
    )

    # 索引定义
    __table_args__ = (
        Index("idx_profile_student", "student_id"),
        Index("idx_profile_crystallized", "crystallized_at"),
    )
