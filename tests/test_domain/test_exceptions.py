"""异常体系测试."""

import pytest

from src.domain.exceptions import (
    ArbitrationConflictError,
    AuthenticationError,
    DatabaseConnectionError,
    DiagnosisConflictError,
    DiagnosisError,
    DiagnosisTimeoutError,
    DomainError,
    InvalidProblemError,
    InvalidVariantError,
    MemoryError,
    ModelUnavailableError,
    ProfileNotFoundError,
    VariantGenerationError,
)


class TestDomainError:
    """领域异常基础测试."""

    def test_basic_error(self):
        """测试基础错误."""
        error = DomainError("Test error")
        assert str(error) == "[DOMAIN_001] Test error"
        assert error.message == "Test error"
        assert error.error_code == "DOMAIN_001"

    def test_error_with_details(self):
        """测试带详情的错误."""
        error = DomainError(
            "Test error",
            error_code="CUSTOM_001",
            details={"key": "value"},
        )
        assert error.error_code == "CUSTOM_001"
        assert error.details == {"key": "value"}
        assert "details=" in str(error)

    def test_to_dict(self):
        """测试转字典."""
        error = DomainError(
            "Test error",
            error_code="TEST_001",
            details={"count": 5},
        )
        error_dict = error.to_dict()
        assert error_dict["error_type"] == "DomainError"
        assert error_dict["error_code"] == "TEST_001"
        assert error_dict["message"] == "Test error"
        assert error_dict["details"]["count"] == 5


class TestDiagnosisErrors:
    """诊断异常测试."""

    def test_diagnosis_error(self):
        """测试诊断异常."""
        error = DiagnosisError(
            "Diagnosis failed",
            task_id="task_123",
            error_code="DIAG_FAIL",
        )
        assert error.task_id == "task_123"
        assert error.error_code == "DIAG_FAIL"

    def test_diagnosis_timeout_error(self):
        """测试诊断超时异常."""
        error = DiagnosisTimeoutError(
            task_id="task_123",
            timeout_seconds=90.0,
        )
        assert error.error_code == "DIAG_TIMEOUT"
        assert error.timeout_seconds == 90.0
        assert error.details["timeout_seconds"] == 90.0

    def test_diagnosis_conflict_error(self):
        """测试诊断冲突异常."""
        conflicts = [{"model": "A", "result": True}]
        error = DiagnosisConflictError(
            task_id="task_123",
            conflicts=conflicts,
        )
        assert error.error_code == "DIAG_CONFLICT"
        assert error.conflicts == conflicts

    def test_invalid_problem_error(self):
        """测试无效题目异常."""
        error = InvalidProblemError(
            task_id="task_123",
            problem_id="prob_456",
            reason="Image unclear",
        )
        assert error.problem_id == "prob_456"
        assert error.reason == "Image unclear"


class TestArbitrationErrors:
    """仲裁异常测试."""

    def test_arbitration_conflict_error(self):
        """测试仲裁冲突异常."""
        model_results = [
            {"model_id": "A", "result": True},
            {"model_id": "B", "result": False},
        ]
        error = ArbitrationConflictError(
            problem_id="prob_123",
            model_results=model_results,
        )
        assert error.error_code == "ARBIT_CONFLICT"
        assert error.model_results == model_results

    def test_model_unavailable_error(self):
        """测试模型不可用异常."""
        error = ModelUnavailableError(
            problem_id="prob_123",
            model_id="model_A",
            retryable=True,
        )
        assert error.model_id == "model_A"
        assert error.retryable is True


class TestVariantErrors:
    """变形题异常测试."""

    def test_invalid_variant_error(self):
        """测试无效变形题异常."""
        validation_errors = ["Invalid formula"]
        error = InvalidVariantError(
            original_problem_id="prob_123",
            variant_id="var_456",
            validation_errors=validation_errors,
        )
        assert error.variant_id == "var_456"
        assert error.validation_errors == validation_errors


class TestMemoryErrors:
    """记忆系统异常测试."""

    def test_profile_not_found_error(self):
        """测试画像不存在异常."""
        error = ProfileNotFoundError(student_id="student_123")
        assert error.student_id == "student_123"
        assert error.error_code == "MEMORY_PROFILE_NOT_FOUND"


class TestInfrastructureErrors:
    """基础设施异常测试."""

    def test_database_connection_error(self):
        """测试数据库连接异常."""
        error = DatabaseConnectionError(
            connection_string="sqlite:///test.db",
            retryable=True,
        )
        assert error.storage_type == "database"
        assert error.operation == "connect"
        assert error.retryable is True
