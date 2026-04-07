"""知识图谱相关模型.

本模块包含知识点、知识依赖、学生知识掌握度等ORM模型.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (JSON, CheckConstraint, DateTime, Float, ForeignKey,
                        Index, Integer, String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.base import Base

if TYPE_CHECKING:
    from src.domain.models.homework import Question
    from src.domain.models.student import Student


class KnowledgePoint(Base):
    """知识点表."""

    __tablename__ = "knowledge_point"

    knowledge_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    subject: Mapped[str] = mapped_column(String(32), nullable=False, comment="所属学科")
    grade_level: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="适用年级"
    )
    knowledge_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="知识点名称"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="知识点描述"
    )
    parent_knowledge_id: Mapped[Optional[str]] = mapped_column(
        String(32),
        ForeignKey("knowledge_point.knowledge_id", ondelete="SET NULL"),
        nullable=True,
        comment="父知识点ID",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # 关系定义
    parent: Mapped[Optional["KnowledgePoint"]] = relationship(
        "KnowledgePoint",
        remote_side="KnowledgePoint.knowledge_id",
        back_populates="children",
    )
    children: Mapped[List["KnowledgePoint"]] = relationship(
        "KnowledgePoint", back_populates="parent"
    )
    dependencies: Mapped[List["KnowledgeDependency"]] = relationship(
        "KnowledgeDependency",
        foreign_keys="KnowledgeDependency.knowledge_id",
        back_populates="knowledge",
        cascade="all, delete-orphan",
    )
    prerequisites: Mapped[List["KnowledgeDependency"]] = relationship(
        "KnowledgeDependency",
        foreign_keys="KnowledgeDependency.prerequisite_id",
        back_populates="prerequisite",
        cascade="all, delete-orphan",
    )
    student_masteries: Mapped[List["StudentKnowledgeMastery"]] = relationship(
        "StudentKnowledgeMastery",
        back_populates="knowledge",
        cascade="all, delete-orphan",
    )
    question_tags: Mapped[List["QuestionKnowledgeTag"]] = relationship(
        "QuestionKnowledgeTag", back_populates="knowledge", cascade="all, delete-orphan"
    )
    misconceptions: Mapped[List["Misconception"]] = relationship(
        "Misconception", back_populates="knowledge", cascade="all, delete-orphan"
    )

    # 索引定义
    __table_args__ = (
        Index("idx_knowledge_subject_grade", "subject", "grade_level"),
        Index("idx_knowledge_parent", "parent_knowledge_id"),
    )


class KnowledgeDependency(Base):
    """知识依赖关系表."""

    __tablename__ = "knowledge_dependency"

    dependency_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    knowledge_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("knowledge_point.knowledge_id", ondelete="CASCADE"),
        nullable=False,
    )
    prerequisite_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("knowledge_point.knowledge_id", ondelete="CASCADE"),
        nullable=False,
    )
    dependency_strength: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5, comment="依赖强度"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # 关系定义
    knowledge: Mapped["KnowledgePoint"] = relationship(
        "KnowledgePoint", foreign_keys=[knowledge_id], back_populates="dependencies"
    )
    prerequisite: Mapped["KnowledgePoint"] = relationship(
        "KnowledgePoint", foreign_keys=[prerequisite_id], back_populates="prerequisites"
    )

    # 约束和索引
    __table_args__ = (
        CheckConstraint(
            "dependency_strength >= 0 AND dependency_strength <= 1",
            name="ck_dependency_strength",
        ),
        CheckConstraint(
            "knowledge_id != prerequisite_id", name="ck_dependency_no_self_ref"
        ),
        UniqueConstraint("knowledge_id", "prerequisite_id", name="uq_dependency"),
        Index("idx_dependency_knowledge", "knowledge_id"),
        Index("idx_dependency_prereq", "prerequisite_id"),
    )


class StudentKnowledgeMastery(Base):
    """学生知识掌握度表."""

    __tablename__ = "student_knowledge_mastery"

    mastery_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    student_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False
    )
    knowledge_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("knowledge_point.knowledge_id", ondelete="CASCADE"),
        nullable=False,
    )
    mastery_level: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="掌握度(0-1)"
    )
    practice_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="练习次数"
    )
    last_practiced: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="最后练习时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # 关系定义
    student: Mapped["Student"] = relationship(
        "Student", back_populates="knowledge_masteries"
    )
    knowledge: Mapped["KnowledgePoint"] = relationship(
        "KnowledgePoint", back_populates="student_masteries"
    )

    # 约束和索引
    __table_args__ = (
        CheckConstraint(
            "mastery_level >= 0 AND mastery_level <= 1", name="ck_mastery_level"
        ),
        CheckConstraint("practice_count >= 0", name="ck_mastery_practice_count"),
        UniqueConstraint("student_id", "knowledge_id", name="uq_student_knowledge"),
        Index("idx_mastery_student", "student_id", "mastery_level"),
        Index("idx_mastery_level", "mastery_level", "practice_count"),
    )


class QuestionKnowledgeTag(Base):
    """题目知识点标签表."""

    __tablename__ = "question_knowledge_tag"

    tag_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    question_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("question.question_id", ondelete="CASCADE"),
        nullable=False,
    )
    knowledge_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("knowledge_point.knowledge_id", ondelete="CASCADE"),
        nullable=False,
    )
    relevance_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, comment="相关度分数"
    )

    # 关系定义
    question: Mapped["Question"] = relationship(
        "Question", back_populates="knowledge_tags"
    )
    knowledge: Mapped["KnowledgePoint"] = relationship(
        "KnowledgePoint", back_populates="question_tags"
    )

    # 约束和索引
    __table_args__ = (
        CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1", name="ck_tag_relevance"
        ),
        UniqueConstraint(
            "question_id", "knowledge_id", name="uq_question_knowledge_tag"
        ),
        Index("idx_tag_knowledge", "knowledge_id"),
    )


class Misconception(Base):
    """概念误解表."""

    __tablename__ = "misconception"

    misconception_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    knowledge_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("knowledge_point.knowledge_id", ondelete="CASCADE"),
        nullable=False,
    )
    misconception_pattern: Mapped[str] = mapped_column(
        Text, nullable=False, comment="误解模式描述"
    )
    correct_concept: Mapped[str] = mapped_column(
        Text, nullable=False, comment="正确概念描述"
    )
    verified_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="验证次数"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # 关系定义
    knowledge: Mapped["KnowledgePoint"] = relationship(
        "KnowledgePoint", back_populates="misconceptions"
    )

    # 约束和索引
    __table_args__ = (
        CheckConstraint("verified_count >= 0", name="ck_misconception_verified"),
        Index("idx_misconception_knowledge", "knowledge_id"),
    )
