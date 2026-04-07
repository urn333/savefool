"""领域模型测试."""

import pytest
from datetime import datetime

from src.domain.models import (
    ArbitrationResult,
    ConceptStrength,
    DiagnosisResult,
    DiagnosisStatus,
    ErrorType,
    GenerationStrategy,
    LearningEpisode,
    LearningEventType,
    LearningStyle,
    ModelVote,
    Problem,
    ProblemDiagnosis,
    StudentProfile,
    VariantProblem,
    WrongProblem,
)


class TestErrorType:
    """错误类型测试."""

    def test_error_type_values(self):
        """测试错误类型值."""
        assert ErrorType.CONCEPT_MISUNDERSTANDING.value == "concept"
        assert ErrorType.CALCULATION_ERROR.value == "calculation"
        assert ErrorType.LOGICAL_FLAW.value == "logic"
        assert ErrorType.CARELESS_MISTAKE.value == "careless"
        assert ErrorType.KNOWLEDGE_GAP.value == "knowledge"


class TestProblem:
    """题目模型测试."""

    def test_create_problem(self):
        """测试创建题目."""
        problem = Problem(
            content="What is 2+2?",
            subject="math",
            difficulty=3,
            answer="4",
            knowledge_points=["addition"],
        )
        assert problem.content == "What is 2+2?"
        assert problem.subject == "math"
        assert problem.difficulty == 3
        assert problem.answer == "4"
        assert problem.id.startswith("prob_")

    def test_subject_validation(self):
        """测试学科验证."""
        with pytest.raises(ValueError):
            Problem(content="Test", subject="invalid", difficulty=5)

    def test_subject_lowercase(self):
        """测试学科转小写."""
        problem = Problem(content="Test", subject="MATH", difficulty=5)
        assert problem.subject == "math"


class TestWrongProblem:
    """错题模型测试."""

    def test_create_wrong_problem(self):
        """测试创建错题."""
        wrong = WrongProblem(
            problem_id="prob_123",
            error_type=ErrorType.CALCULATION_ERROR,
            root_cause="Careless mistake",
            confidence=0.85,
        )
        assert wrong.problem_id == "prob_123"
        assert wrong.error_type == ErrorType.CALCULATION_ERROR
        assert wrong.confidence == 0.85


class TestDiagnosisResult:
    """诊断结果测试."""

    def test_create_diagnosis_result(self):
        """测试创建诊断结果."""
        result = DiagnosisResult(
            task_id="task_123",
            status=DiagnosisStatus.COMPLETED,
            processing_time=5.5,
        )
        assert result.task_id == "task_123"
        assert result.processing_time == 5.5

    def test_accuracy_rate(self):
        """测试正确率计算."""
        result = DiagnosisResult(
            task_id="task_123",
            original_problems=[
                Problem(content="Q1", subject="math", difficulty=5),
                Problem(content="Q2", subject="math", difficulty=5),
                Problem(content="Q3", subject="math", difficulty=5),
                Problem(content="Q4", subject="math", difficulty=5),
            ],
            wrong_problems=[
                WrongProblem(
                    problem_id="prob_1",
                    error_type=ErrorType.CALCULATION_ERROR,
                    root_cause="Test",
                    confidence=0.8,
                ),
            ],
        )
        assert result.total_count == 4
        assert result.wrong_count == 1
        assert result.accuracy_rate == 0.75
        assert result.has_wrong_problems is True


class TestArbitrationResult:
    """仲裁结果测试."""

    def test_create_arbitration_result(self):
        """测试创建仲裁结果."""
        result = ArbitrationResult(
            problem_id="prob_123",
            is_correct=False,
            error_type=ErrorType.CALCULATION_ERROR,
            confidence=0.9,
        )
        assert result.problem_id == "prob_123"
        assert result.is_correct is False
        assert result.confidence == 0.9

    def test_model_votes(self):
        """测试模型投票."""
        result = ArbitrationResult(
            problem_id="prob_123",
            is_correct=False,
            confidence=0.85,
            model_votes={
                "model_a": ModelVote(
                    model_id="model_a",
                    is_correct=False,
                    confidence=0.9,
                ),
                "model_b": ModelVote(
                    model_id="model_b",
                    is_correct=False,
                    confidence=0.8,
                ),
            },
        )
        assert len(result.model_votes) == 2
        assert result.agreement_count == 2
        assert result.disagreement_count == 0

    def test_primary_model(self):
        """测试主要模型."""
        result = ArbitrationResult(
            problem_id="prob_123",
            is_correct=True,
            confidence=0.85,
            model_votes={
                "model_a": ModelVote(
                    model_id="model_a",
                    is_correct=True,
                    confidence=0.9,
                ),
                "model_b": ModelVote(
                    model_id="model_b",
                    is_correct=True,
                    confidence=0.7,
                ),
            },
        )
        assert result.primary_model == "model_a"


class TestVariantProblem:
    """变形题测试."""

    def test_create_variant(self):
        """测试创建变形题."""
        variant = VariantProblem(
            original_problem_id="prob_123",
            content="What is 3+3?",
            difficulty=4,
            target_concept="addition",
            error_type=ErrorType.CALCULATION_ERROR,
            strategy=GenerationStrategy.VALUE_SUBSTITUTION,
            answer="6",
        )
        assert variant.original_problem_id == "prob_123"
        assert variant.difficulty == 4
        assert variant.is_solvable is True

    def test_get_strategies(self):
        """测试获取策略."""
        strategies = VariantProblem.get_strategies_for_error(
            ErrorType.CONCEPT_MISUNDERSTANDING
        )
        assert GenerationStrategy.CONTEXT_CHANGE in strategies
        assert GenerationStrategy.CONDITION_MODIFY in strategies

    def test_difficulty_adjustment(self):
        """测试难度调节."""
        adjustment = VariantProblem.get_difficulty_adjustment(
            ErrorType.KNOWLEDGE_GAP
        )
        assert adjustment == -2


class TestStudentProfile:
    """学生画像测试."""

    def test_create_profile(self):
        """测试创建学生画像."""
        profile = StudentProfile(student_id="student_123")
        assert profile.student_id == "student_123"
        assert profile.version == 1
        assert profile.learning_style is not None

    def test_get_concept_mastery(self):
        """测试获取概念掌握."""
        concept = ConceptStrength(
            concept_id="math_addition",
            concept_name="Addition",
            mastery_level=0.8,
        )
        profile = StudentProfile(
            student_id="student_123",
            strong_concepts=[concept],
        )
        found = profile.get_concept_mastery("math_addition")
        assert found is not None
        assert found.mastery_level == 0.8


class TestLearningEpisode:
    """学习事件测试."""

    def test_create_episode(self):
        """测试创建学习事件."""
        episode = LearningEpisode(
            student_id="student_123",
            event_type=LearningEventType.PROBLEM_ATTEMPT,
            problem_id="prob_456",
            final_result="correct",
        )
        assert episode.student_id == "student_123"
        assert episode.event_type == LearningEventType.PROBLEM_ATTEMPT
        assert episode.final_result == "correct"
