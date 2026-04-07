"""具体Repository实现.

本模块提供各实体的具体Repository实现.
"""

from sqlalchemy import String
from sqlalchemy.orm import InstrumentedAttribute

from src.infrastructure.db import (AnswerTrace, CognitiveGap, CognitiveProfile,
                                   DescriptionParse, DiagnosisPath,
                                   ErrorDiagnosis, GapEvidence, Homework,
                                   HomeworkAnalysis, KnowledgeDependency,
                                   KnowledgePoint, Misconception,
                                   ParentDescription, Question,
                                   QuestionKnowledgeTag, Student,
                                   StudentAnswer, StudentKnowledgeMastery,
                                   VariantAnswer, VariantQuestion)
from src.infrastructure.storage.repository import BaseRepository


class StudentRepository(BaseRepository[Student]):
    """学生Repository."""

    @property
    def model_class(self):
        return Student

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return Student.student_id


class CognitiveProfileRepository(BaseRepository[CognitiveProfile]):
    """认知画像Repository."""

    @property
    def model_class(self):
        return CognitiveProfile

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return CognitiveProfile.profile_id


class HomeworkRepository(BaseRepository[Homework]):
    """作业Repository."""

    @property
    def model_class(self):
        return Homework

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return Homework.homework_id


class QuestionRepository(BaseRepository[Question]):
    """题目Repository."""

    @property
    def model_class(self):
        return Question

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return Question.question_id


class HomeworkAnalysisRepository(BaseRepository[HomeworkAnalysis]):
    """作业分析Repository."""

    @property
    def model_class(self):
        return HomeworkAnalysis

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return HomeworkAnalysis.analysis_id


class StudentAnswerRepository(BaseRepository[StudentAnswer]):
    """学生答案Repository."""

    @property
    def model_class(self):
        return StudentAnswer

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return StudentAnswer.answer_id


class AnswerTraceRepository(BaseRepository[AnswerTrace]):
    """答题路径Repository."""

    @property
    def model_class(self):
        return AnswerTrace

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return AnswerTrace.trace_id


class ErrorDiagnosisRepository(BaseRepository[ErrorDiagnosis]):
    """错题诊断Repository."""

    @property
    def model_class(self):
        return ErrorDiagnosis

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return ErrorDiagnosis.diagnosis_id


class DiagnosisPathRepository(BaseRepository[DiagnosisPath]):
    """诊断路径Repository."""

    @property
    def model_class(self):
        return DiagnosisPath

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return DiagnosisPath.path_id


class VariantQuestionRepository(BaseRepository[VariantQuestion]):
    """变形题Repository."""

    @property
    def model_class(self):
        return VariantQuestion

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return VariantQuestion.variant_id


class VariantAnswerRepository(BaseRepository[VariantAnswer]):
    """变形题答案Repository."""

    @property
    def model_class(self):
        return VariantAnswer

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return VariantAnswer.variant_answer_id


class KnowledgePointRepository(BaseRepository[KnowledgePoint]):
    """知识点Repository."""

    @property
    def model_class(self):
        return KnowledgePoint

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return KnowledgePoint.knowledge_id


class KnowledgeDependencyRepository(BaseRepository[KnowledgeDependency]):
    """知识依赖Repository."""

    @property
    def model_class(self):
        return KnowledgeDependency

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return KnowledgeDependency.dependency_id


class StudentKnowledgeMasteryRepository(BaseRepository[StudentKnowledgeMastery]):
    """学生知识掌握度Repository."""

    @property
    def model_class(self):
        return StudentKnowledgeMastery

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return StudentKnowledgeMastery.mastery_id


class QuestionKnowledgeTagRepository(BaseRepository[QuestionKnowledgeTag]):
    """题目知识点标签Repository."""

    @property
    def model_class(self):
        return QuestionKnowledgeTag

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return QuestionKnowledgeTag.tag_id


class MisconceptionRepository(BaseRepository[Misconception]):
    """概念误解Repository."""

    @property
    def model_class(self):
        return Misconception

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return Misconception.misconception_id


class CognitiveGapRepository(BaseRepository[CognitiveGap]):
    """认知缺口Repository."""

    @property
    def model_class(self):
        return CognitiveGap

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return CognitiveGap.gap_id


class GapEvidenceRepository(BaseRepository[GapEvidence]):
    """缺口证据Repository."""

    @property
    def model_class(self):
        return GapEvidence

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return GapEvidence.evidence_id


class ParentDescriptionRepository(BaseRepository[ParentDescription]):
    """家长描述Repository."""

    @property
    def model_class(self):
        return ParentDescription

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return ParentDescription.description_id


class DescriptionParseRepository(BaseRepository[DescriptionParse]):
    """描述解析Repository."""

    @property
    def model_class(self):
        return DescriptionParse

    @property
    def primary_key(self) -> InstrumentedAttribute:
        return DescriptionParse.parse_id
