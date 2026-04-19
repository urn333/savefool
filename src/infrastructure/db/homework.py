"""作业相关模型.

本模块包含作业、题目和作业分析的ORM模型.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (JSON, CheckConstraint, DateTime, ForeignKey, Index,
                        Integer, String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.base import Base
from src.infrastructure.db.enums import HomeworkStatus

if TYPE_CHECKING:
    from src.domain.models.answer import StudentAnswer
    from src.domain.models.student import Student


class Homework(Base):
    """作业记录表."""

    __tablename__ = "homework"

    homework_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    student_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(32), nullable=False, comment="学科")
    page_count: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="页数", info={"check": "page_count > 0"}
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, comment="上传时间"
    )
    image_urls: Mapped[list] = mapped_column(
        JSON, nullable=False, comment="原图URL列表"
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=HomeworkStatus.ACTIVE.value,
        comment="状态: active/archived/deleted",
    )
    processed_image_url: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True, comment="预处理后图片URL"
    )
    parent_description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="家长描述"
    )
    diagnosis_mode: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, comment="诊断模式"
    )
    diagnosis_result: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="诊断结果JSON"
    )
    error_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="错题数量"
    )
    total_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="总题数"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="完成时间"
    )
    raw_model_response: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="模型原始响应"
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="归档时间"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # 关系定义
    student: Mapped["Student"] = relationship("Student", back_populates="homeworks")
    questions: Mapped[List["Question"]] = relationship(
        "Question", back_populates="homework", cascade="all, delete-orphan"
    )
    analysis: Mapped[Optional["HomeworkAnalysis"]] = relationship(
        "HomeworkAnalysis",
        back_populates="homework",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # 约束和索引
    __table_args__ = (
        CheckConstraint("page_count > 0", name="ck_homework_page_count"),
        CheckConstraint(
            f"status IN ('{HomeworkStatus.PENDING.value}', '{HomeworkStatus.PROCESSING.value}', "
            f"'{HomeworkStatus.COMPLETED.value}', '{HomeworkStatus.FAILED.value}', "
            f"'{HomeworkStatus.ACTIVE.value}', '{HomeworkStatus.ARCHIVED.value}', '{HomeworkStatus.DELETED.value}')",
            name="ck_homework_status",
        ),
        Index("idx_homework_student", "student_id", "uploaded_at"),
        Index("idx_homework_status", "status", "archived_at"),
        Index("idx_homework_uploaded", "uploaded_at"),
    )


class Question(Base):
    """题目信息表."""

    __tablename__ = "question"

    question_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    homework_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("homework.homework_id", ondelete="CASCADE"),
        nullable=False,
    )
    original_image_url: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True, comment="原题图片URL"
    )
    ocr_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="OCR识别文本"
    )
    parsed_content: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="结构化解析内容"
    )
    question_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="题号"
    )
    difficulty_level: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, comment="难度等级"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # 关系定义
    homework: Mapped["Homework"] = relationship("Homework", back_populates="questions")
    answers: Mapped[List["StudentAnswer"]] = relationship(
        "StudentAnswer", back_populates="question", cascade="all, delete-orphan"
    )
    variant_questions: Mapped[List["VariantQuestion"]] = relationship(
        "VariantQuestion",
        back_populates="original_question",
        cascade="all, delete-orphan",
    )
    knowledge_tags: Mapped[List["QuestionKnowledgeTag"]] = relationship(
        "QuestionKnowledgeTag", back_populates="question", cascade="all, delete-orphan"
    )

    # 索引定义
    __table_args__ = (Index("idx_question_homework", "homework_id", "question_number"),)


class HomeworkAnalysis(Base):
    """作业分析结果表."""

    __tablename__ = "homework_analysis"

    analysis_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    homework_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("homework.homework_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    cognitive_features: Mapped[Optional[dict]] = mapped_column(
        JSON, default=dict, comment="提取的认知特征"
    )
    key_decisions: Mapped[Optional[list]] = mapped_column(
        JSON, default=list, comment="关键决策节点"
    )
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # 关系定义
    homework: Mapped["Homework"] = relationship("Homework", back_populates="analysis")

    # 索引定义
    __table_args__ = (Index("idx_analysis_homework", "homework_id"),)


from src.infrastructure.db.knowledge import QuestionKnowledgeTag  # noqa: E402
# 延迟导入以避免循环依赖
from src.infrastructure.db.variant import VariantQuestion
