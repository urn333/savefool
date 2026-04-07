"""存储基础设施包.

本模块提供数据库连接管理和Repository实现.
"""

from src.infrastructure.storage.database import (DATABASE_URL,
                                                 DEFAULT_DATABASE_URL,
                                                 DatabaseManager, db_manager,
                                                 get_async_session)
from src.infrastructure.storage.repositories import (
    AnswerTraceRepository, CognitiveGapRepository, CognitiveProfileRepository,
    DescriptionParseRepository, DiagnosisPathRepository,
    ErrorDiagnosisRepository, GapEvidenceRepository,
    HomeworkAnalysisRepository, HomeworkRepository,
    KnowledgeDependencyRepository, KnowledgePointRepository,
    MisconceptionRepository, ParentDescriptionRepository,
    QuestionKnowledgeTagRepository, QuestionRepository,
    StudentAnswerRepository, StudentKnowledgeMasteryRepository,
    StudentRepository, VariantAnswerRepository, VariantQuestionRepository)
from src.infrastructure.storage.repository import (BaseRepository, PageResult,
                                                   Pagination)

__all__ = [
    # Database
    "DatabaseManager",
    "db_manager",
    "get_async_session",
    "DATABASE_URL",
    "DEFAULT_DATABASE_URL",
    # Repository Base
    "BaseRepository",
    "Pagination",
    "PageResult",
    # Repositories
    "StudentRepository",
    "CognitiveProfileRepository",
    "HomeworkRepository",
    "QuestionRepository",
    "HomeworkAnalysisRepository",
    "StudentAnswerRepository",
    "AnswerTraceRepository",
    "ErrorDiagnosisRepository",
    "DiagnosisPathRepository",
    "VariantQuestionRepository",
    "VariantAnswerRepository",
    "KnowledgePointRepository",
    "KnowledgeDependencyRepository",
    "StudentKnowledgeMasteryRepository",
    "QuestionKnowledgeTagRepository",
    "MisconceptionRepository",
    "CognitiveGapRepository",
    "GapEvidenceRepository",
    "ParentDescriptionRepository",
    "DescriptionParseRepository",
]
