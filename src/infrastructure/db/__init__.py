"""数据库ORM模型包.

本模块包含所有SQLAlchemy ORM模型定义.
"""

from src.infrastructure.db.answer import (AnswerTrace, DiagnosisPath,
                                          ErrorDiagnosis, StudentAnswer)
from src.infrastructure.db.base import Base
from src.infrastructure.db.cognitive_gap import CognitiveGap, GapEvidence
from src.infrastructure.db.enums import (ErrorType, EvidenceType, GapStatus,
                                         HomeworkStatus, SourceType,
                                         ValidationStatus, VariantType)
from src.infrastructure.db.homework import Homework, HomeworkAnalysis, Question
from src.infrastructure.db.knowledge import (KnowledgeDependency,
                                             KnowledgePoint, Misconception,
                                             QuestionKnowledgeTag,
                                             StudentKnowledgeMastery)
from src.infrastructure.db.parent import DescriptionParse, ParentDescription
from src.infrastructure.db.student import CognitiveProfile, Student
from src.infrastructure.db.variant import VariantAnswer, VariantQuestion

__all__ = [
    # Base
    "Base",
    # Enums
    "ErrorType",
    "VariantType",
    "GapStatus",
    "ValidationStatus",
    "HomeworkStatus",
    "EvidenceType",
    "SourceType",
    # Student
    "Student",
    "CognitiveProfile",
    # Homework
    "Homework",
    "Question",
    "HomeworkAnalysis",
    # Answer
    "StudentAnswer",
    "AnswerTrace",
    "ErrorDiagnosis",
    "DiagnosisPath",
    # Variant
    "VariantQuestion",
    "VariantAnswer",
    # Knowledge
    "KnowledgePoint",
    "KnowledgeDependency",
    "StudentKnowledgeMastery",
    "QuestionKnowledgeTag",
    "Misconception",
    # Cognitive Gap
    "CognitiveGap",
    "GapEvidence",
    # Parent
    "ParentDescription",
    "DescriptionParse",
]
