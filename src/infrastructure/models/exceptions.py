"""模型客户端异常.

定义模型调用过程中可能抛出的各种异常。
"""

from typing import Any, Dict, Optional

from src.domain.exceptions import InfrastructureError


class ModelClientError(InfrastructureError):
    """模型客户端基础异常.

    Attributes:
        provider: 模型提供商名称
        model: 使用的模型名称
        status_code: HTTP状态码（如果有）
    """

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.provider = provider
        self.model = model
        self.status_code = status_code

    def __str__(self) -> str:
        parts = [self.message]
        if self.provider:
            parts.append(f"provider={self.provider}")
        if self.model:
            parts.append(f"model={self.model}")
        if self.status_code:
            parts.append(f"status_code={self.status_code}")
        return " | ".join(parts)


class ModelAuthenticationError(ModelClientError):
    """模型认证错误.

    通常由API密钥无效或过期引起。
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        provider: Optional[str] = None,
        **kwargs: Any,
    ):
        super().__init__(message, provider=provider, status_code=401, **kwargs)


class ModelRateLimitError(ModelClientError):
    """模型速率限制错误.

    请求频率超过限制时抛出。

    Attributes:
        retry_after: 建议的等待时间（秒）
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        provider: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs: Any,
    ):
        super().__init__(message, provider=provider, status_code=429, **kwargs)
        self.retry_after = retry_after


class ModelTimeoutError(ModelClientError):
    """模型调用超时错误."""

    def __init__(
        self,
        message: str = "Request timeout",
        provider: Optional[str] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ):
        super().__init__(message, provider=provider, **kwargs)
        self.timeout = timeout


class ModelValidationError(ModelClientError):
    """模型请求验证错误.

    请求参数无效时抛出。
    """

    def __init__(
        self,
        message: str = "Invalid request",
        provider: Optional[str] = None,
        **kwargs: Any,
    ):
        super().__init__(message, provider=provider, status_code=400, **kwargs)


class ModelContentFilterError(ModelClientError):
    """模型内容过滤错误.

    输入或输出被内容过滤器拦截时抛出。
    """

    def __init__(
        self,
        message: str = "Content filtered",
        provider: Optional[str] = None,
        filter_type: Optional[str] = None,
        **kwargs: Any,
    ):
        super().__init__(message, provider=provider, **kwargs)
        self.filter_type = filter_type


class ModelServerError(ModelClientError):
    """模型服务端错误.

    模型服务内部错误时抛出。
    """

    def __init__(
        self,
        message: str = "Server error",
        provider: Optional[str] = None,
        status_code: int = 500,
        **kwargs: Any,
    ):
        super().__init__(message, provider=provider, status_code=status_code, **kwargs)
