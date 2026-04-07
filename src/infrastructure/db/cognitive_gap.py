"""认知缺口相关模型.

本模块包含认知缺口和缺口证据的ORM模型.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (JSON, CheckConstraint, DateTime, ForeignKey, Index,
                        Integer, String)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.base import Base
from src.infrastructure.db.enums import EvidenceType, GapStatus

if TYPE_CHECKING:
    from src.domain.models.answer import ErrorDiagnosis
    from src.domain.models.student import Student


class CognitiveGap(Base):
    """认知缺口表."""

    __tablename__ = "cognitive_gap"

    gap_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    student_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False
    )
    gap_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="缺口类型"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=GapStatus.PENDING.value, comment="状态"
    )
    related_knowledge: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, comment="相关知识点"
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    crystallized_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="固化时间"
    )
    occurrence_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="出现次数"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # 关系定义
    student: Mapped["Student"] = relationship(
        "Student", back_populates="cognitive_gaps"
    )
    evidences: Mapped[List["GapEvidence"]] = relationship(
        "GapEvidence", back_populates="cognitive_gap", cascade="all, delete-orphan"
    )

    # 约束和索引
    __table_args__ = (
        CheckConstraint(
            f"status IN ('{GapStatus.PENDING.value}', '{GapStatus.CRYSTALLIZED.value}', '{GapStatus.DISMISSED.value}')",
            name="ck_gap_status",
        ),
        CheckConstraint("occurrence_count >= 1", name="ck_gap_occurrence"),
        Index("idx_gap_student", "student_id", "status", "discovered_at"),
        Index("idx_gap_status", "status", "discovered_at"),
        Index("idx_gap_crystallized", "crystallized_at"),
    )


class GapEvidence(Base):
    """认知缺口证据表."""

    __tablename__ = "gap_evidence"

    evidence_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    gap_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("cognitive_gap.gap_id", ondelete="CASCADE"),
        nullable=False,
    )
    diagnosis_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("error_diagnosis.diagnosis_id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="证据类型"
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # 关系定义
    cognitive_gap: Mapped["CognitiveGap"] = relationship(
        "CognitiveGap", back_populates="evidences"
    )
    diagnosis: Mapped["ErrorDiagnosis"] = relationship(
        "ErrorDiagnosis", back_populates="gap_evidences"
    )

    # 约束和索引
    __table_args__ = (
        CheckConstraint(
            f"evidence_type IN ('{EvidenceType.INITIAL_DIAGNOSIS.value}', '{EvidenceType.REPEAT_ERROR.value}', "
            f"'{EvidenceType.VARIANT_FAILED.value}', '{EvidenceType.CROSS_HOMEWORK.value}')",
            name="ck_evidence_type",
        ),
        Index("idx_evidence_gap", "gap_id", "recorded_at"),
        Index("idx_evidence_diagnosis", "diagnosis_id"),
    )
