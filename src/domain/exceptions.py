"""领域异常体系.

定义AI助教系统的所有领域异常，包括诊断、模型调用、存储等。

异常层次结构:
    DomainError (基础领域异常)
    ├── DiagnosisError (诊断相关异常)
    │   ├── DiagnosisTimeoutError
    │   ├── DiagnosisConflictError
    │   └── InvalidProblemError
    ├── ArbitrationError (仲裁相关异常)
    │   ├── ArbitrationConflictError
    │   └── ModelUnavailableError
    ├── VariantGenerationError (变形题生成异常)
    │   └── InvalidVariantError
    ├── MemoryError (记忆系统异常)
    │   └── ProfileNotFoundError
    └── ValidationError (验证异常)

    InfrastructureError (基础设施异常)
    ├── StorageError (存储异常)
    │   ├── DatabaseConnectionError
    │   └── VectorDBError
    └── ExternalServiceError (外部服务异常)
"""

from typing import Any, Dict, List, Optional


class DomainError(Exception):
    """领域异常基类.

    所有领域异常都继承此类，提供统一的错误处理接口。

    Attributes:
        message: 错误信息
        error_code: 错误代码
        details: 详细错误信息
    """

    # 错误代码前缀
    ERROR_CODE_PREFIX = "DOMAIN"

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or f"{self.ERROR_CODE_PREFIX}_001"
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"[{self.error_code}] {self.message} | details={self.details}"
        return f"[{self.error_code}] {self.message}"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式.

        Returns:
            包含错误信息的字典
        """
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


# =============================================================================
# 诊断相关异常
# =============================================================================


class DiagnosisError(DomainError):
    """诊断异常基类.

    诊断流程中发生的所有异常都继承此类。
    """

    ERROR_CODE_PREFIX = "DIAG"

    def __init__(
        self,
        message: str,
        task_id: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, error_code, details)
        self.task_id = task_id


class DiagnosisTimeoutError(DiagnosisError):
    """诊断超时异常.

    诊断流程超过最大允许时间时抛出。
    """

    def __init__(
        self,
        message: str = "Diagnosis timeout",
        task_id: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message,
            task_id=task_id,
            error_code="DIAG_TIMEOUT",
            details={**(details or {}), "timeout_seconds": timeout_seconds},
        )
        self.timeout_seconds = timeout_seconds


class DiagnosisConflictError(DiagnosisError):
    """诊断冲突异常.

    多模型诊断结果存在严重冲突时抛出。
    """

    def __init__(
        self,
        message: str = "Diagnosis conflict detected",
        task_id: Optional[str] = None,
        conflicts: Optional[List[Dict[str, Any]]] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message,
            task_id=task_id,
            error_code="DIAG_CONFLICT",
            details={**(details or {}), "conflicts": conflicts or []},
        )
        self.conflicts = conflicts or []


class InvalidProblemError(DiagnosisError):
    """无效题目异常.

    题目格式无效或无法识别时抛出。
    """

    def __init__(
        self,
        message: str = "Invalid problem format",
        task_id: Optional[str] = None,
        problem_id: Optional[str] = None,
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message,
            task_id=task_id,
            error_code="DIAG_INVALID_PROBLEM",
            details={
                **(details or {}),
                "problem_id": problem_id,
                "reason": reason,
            },
        )
        self.problem_id = problem_id
        self.reason = reason


# =============================================================================
# 仲裁相关异常
# =============================================================================


class ArbitrationError(DomainError):
    """仲裁异常基类.

    多模型仲裁过程中发生的异常。
    """

    ERROR_CODE_PREFIX = "ARBIT"

    def __init__(
        self,
        message: str,
        problem_id: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, error_code, details)
        self.problem_id = problem_id


class ArbitrationConflictError(ArbitrationError):
    """仲裁冲突异常.

    多模型结果无法通过仲裁达成共识时抛出。
    """

    def __init__(
        self,
        message: str = "Arbitration cannot reach consensus",
        problem_id: Optional[str] = None,
        model_results: Optional[List[Dict[str, Any]]] = None,
        confidence_scores: Optional[Dict[str, float]] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message,
            problem_id=problem_id,
            error_code="ARBIT_CONFLICT",
            details={
                **(details or {}),
                "model_results": model_results or [],
                "confidence_scores": confidence_scores or {},
            },
        )
        self.model_results = model_results or []
        self.confidence_scores = confidence_scores or {}


class ModelUnavailableError(ArbitrationError):
    """模型不可用异常.

    某个模型服务无法访问时抛出。
    """

    def __init__(
        self,
        message: str = "Model service unavailable",
        problem_id: Optional[str] = None,
        model_id: Optional[str] = None,
        retryable: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message,
            problem_id=problem_id,
            error_code="ARBIT_MODEL_UNAVAILABLE",
            details={
                **(details or {}),
                "model_id": model_id,
                "retryable": retryable,
            },
        )
        self.model_id = model_id
        self.retryable = retryable


# =============================================================================
# 变形题生成异常
# =============================================================================


class VariantGenerationError(DomainError):
    """变形题生成异常基类."""

    ERROR_CODE_PREFIX = "VARIANT"

    def __init__(
        self,
        message: str,
        original_problem_id: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, error_code, details)
        self.original_problem_id = original_problem_id


class InvalidVariantError(VariantGenerationError):
    """无效变形题异常.

    生成的变形题未通过验证时抛出。
    """

    def __init__(
        self,
        message: str = "Generated variant is invalid",
        original_problem_id: Optional[str] = None,
        variant_id: Optional[str] = None,
        validation_errors: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message,
            original_problem_id=original_problem_id,
            error_code="VARIANT_INVALID",
            details={
                **(details or {}),
                "variant_id": variant_id,
                "validation_errors": validation_errors or [],
            },
        )
        self.variant_id = variant_id
        self.validation_errors = validation_errors or []


class VariantGenerationTimeoutError(VariantGenerationError):
    """变形题生成超时异常."""

    def __init__(
        self,
        message: str = "Variant generation timeout",
        original_problem_id: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message,
            original_problem_id=original_problem_id,
            error_code="VARIANT_TIMEOUT",
            details={**(details or {}), "timeout_seconds": timeout_seconds},
        )
        self.timeout_seconds = timeout_seconds


# =============================================================================
# 记忆系统异常
# =============================================================================


class MemoryError(DomainError):
    """记忆系统异常基类."""

    ERROR_CODE_PREFIX = "MEMORY"

    def __init__(
        self,
        message: str,
        student_id: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, error_code, details)
        self.student_id = student_id


class ProfileNotFoundError(MemoryError):
    """学生画像不存在异常.

    查询不存在的学生画像时抛出。
    """

    def __init__(
        self,
        message: str = "Student profile not found",
        student_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message,
            student_id=student_id,
            error_code="MEMORY_PROFILE_NOT_FOUND",
            details=details,
        )


class EpisodeNotFoundError(MemoryError):
    """学习事件不存在异常."""

    def __init__(
        self,
        message: str = "Learning episode not found",
        student_id: Optional[str] = None,
        episode_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message,
            student_id=student_id,
            error_code="MEMORY_EPISODE_NOT_FOUND",
            details={**(details or {}), "episode_id": episode_id},
        )
        self.episode_id = episode_id


class MemoryUpdateError(MemoryError):
    """记忆更新异常."""

    def __init__(
        self,
        message: str = "Failed to update memory",
        student_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message,
            student_id=student_id,
            error_code="MEMORY_UPDATE_FAILED",
            details={**(details or {}), "memory_type": memory_type},
        )
        self.memory_type = memory_type


# =============================================================================
# 验证异常
# =============================================================================


class ValidationError(DomainError):
    """验证异常基类."""

    ERROR_CODE_PREFIX = "VALIDATION"

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, error_code, details)
        self.field = field


# =============================================================================
# 基础设施异常
# =============================================================================


class InfrastructureError(Exception):
    """基础设施异常基类.

    存储、外部服务等基础设施相关的异常。
    """

    ERROR_CODE_PREFIX = "INFRA"

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | details={self.details}"
        return self.message

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class StorageError(InfrastructureError):
    """存储异常基类."""

    ERROR_CODE_PREFIX = "STORAGE"

    def __init__(
        self,
        message: str,
        storage_type: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.storage_type = storage_type
        self.operation = operation


class DatabaseConnectionError(StorageError):
    """数据库连接异常."""

    def __init__(
        self,
        message: str = "Database connection failed",
        connection_string: Optional[str] = None,
        retryable: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message,
            storage_type="database",
            operation="connect",
            details={
                **(details or {}),
                "connection_string": connection_string,
                "retryable": retryable,
            },
        )
        self.retryable = retryable


class VectorDBError(StorageError):
    """向量数据库异常."""

    def __init__(
        self,
        message: str,
        collection: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message,
            storage_type="vector_db",
            operation=operation,
            details={**(details or {}), "collection": collection},
        )
        self.collection = collection


class ExternalServiceError(InfrastructureError):
    """外部服务异常基类."""

    ERROR_CODE_PREFIX = "EXTERNAL"

    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.service_name = service_name
        self.status_code = status_code


# =============================================================================
# 应用层异常
# =============================================================================


class ApplicationError(Exception):
    """应用层异常基类.

    业务逻辑相关的异常。
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "APP_ERROR"
        self.details = details or {}

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"


class AuthenticationError(ApplicationError):
    """认证异常."""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, "AUTH_ERROR", details)


class AuthorizationError(ApplicationError):
    """授权异常."""

    def __init__(
        self,
        message: str = "Permission denied",
        resource: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message,
            "FORBIDDEN",
            {**(details or {}), "resource": resource, "action": action},
        )
