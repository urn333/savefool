"""API异常处理模块.

提供统一的异常响应格式和HTTP状态码映射.
"""

from typing import Any, Dict, Optional
from datetime import datetime

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


# ========== 错误码定义 ==========

class ErrorCode:
    """错误码枚举.
    
    采用6位数字格式：XXYYYY
    - XX：错误类别
    - YYYY：具体错误
    """
    
    # 系统级错误 (00)
    SYSTEM_ERROR = 100001
    SERVICE_UNAVAILABLE = 100002
    REQUEST_TIMEOUT = 100003
    
    # 认证授权错误 (01)
    TOKEN_INVALID = 110001
    TOKEN_FORMAT_ERROR = 110002
    PERMISSION_DENIED = 110003
    NOT_AUTHENTICATED = 110004
    
    # 请求参数错误 (02)
    PARAM_MISSING = 120001
    PARAM_FORMAT_ERROR = 120002
    PARAM_INVALID = 120003
    JSON_PARSE_ERROR = 120004
    
    # 资源错误 (03)
    RESOURCE_NOT_FOUND = 130001
    RESOURCE_EXISTS = 130002
    RESOURCE_LOCKED = 130003
    
    # 业务逻辑错误 (04)
    IMAGE_FORMAT_UNSUPPORTED = 140001
    IMAGE_SIZE_EXCEEDED = 140002
    RECOGNITION_FAILED = 140003
    DIAGNOSIS_INCOMPLETE = 140004
    VARIANT_GENERATION_FAILED = 140005
    DESCRIPTION_TOO_LONG = 140006
    
    # 限流错误 (05)
    RATE_LIMIT_EXCEEDED = 150001
    QUOTA_EXHAUSTED = 150002


# 错误码到HTTP状态码的映射
ERROR_CODE_HTTP_MAP: Dict[int, int] = {
    # 系统级错误
    ErrorCode.SYSTEM_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.SERVICE_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.REQUEST_TIMEOUT: status.HTTP_504_GATEWAY_TIMEOUT,
    
    # 认证授权错误
    ErrorCode.TOKEN_INVALID: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.TOKEN_FORMAT_ERROR: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.PERMISSION_DENIED: status.HTTP_403_FORBIDDEN,
    ErrorCode.NOT_AUTHENTICATED: status.HTTP_401_UNAUTHORIZED,
    
    # 请求参数错误
    ErrorCode.PARAM_MISSING: status.HTTP_400_BAD_REQUEST,
    ErrorCode.PARAM_FORMAT_ERROR: status.HTTP_400_BAD_REQUEST,
    ErrorCode.PARAM_INVALID: status.HTTP_400_BAD_REQUEST,
    ErrorCode.JSON_PARSE_ERROR: status.HTTP_400_BAD_REQUEST,
    
    # 资源错误
    ErrorCode.RESOURCE_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.RESOURCE_EXISTS: status.HTTP_409_CONFLICT,
    ErrorCode.RESOURCE_LOCKED: status.HTTP_423_LOCKED,
    
    # 业务逻辑错误
    ErrorCode.IMAGE_FORMAT_UNSUPPORTED: status.HTTP_400_BAD_REQUEST,
    ErrorCode.IMAGE_SIZE_EXCEEDED: status.HTTP_400_BAD_REQUEST,
    ErrorCode.RECOGNITION_FAILED: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ErrorCode.DIAGNOSIS_INCOMPLETE: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ErrorCode.VARIANT_GENERATION_FAILED: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ErrorCode.DESCRIPTION_TOO_LONG: status.HTTP_400_BAD_REQUEST,
    
    # 限流错误
    ErrorCode.RATE_LIMIT_EXCEEDED: status.HTTP_429_TOO_MANY_REQUESTS,
    ErrorCode.QUOTA_EXHAUSTED: status.HTTP_429_TOO_MANY_REQUESTS,
}


# 错误码到默认消息的映射
ERROR_CODE_MESSAGE_MAP: Dict[int, str] = {
    ErrorCode.SYSTEM_ERROR: "系统内部错误",
    ErrorCode.SERVICE_UNAVAILABLE: "服务暂时不可用",
    ErrorCode.REQUEST_TIMEOUT: "请求超时",
    ErrorCode.TOKEN_INVALID: "Token无效或过期",
    ErrorCode.TOKEN_FORMAT_ERROR: "Token格式错误",
    ErrorCode.PERMISSION_DENIED: "权限不足",
    ErrorCode.NOT_AUTHENTICATED: "未登录",
    ErrorCode.PARAM_MISSING: "参数缺失",
    ErrorCode.PARAM_FORMAT_ERROR: "参数格式错误",
    ErrorCode.PARAM_INVALID: "参数值非法",
    ErrorCode.JSON_PARSE_ERROR: "JSON解析失败",
    ErrorCode.RESOURCE_NOT_FOUND: "资源不存在",
    ErrorCode.RESOURCE_EXISTS: "资源已存在",
    ErrorCode.RESOURCE_LOCKED: "资源被占用",
    ErrorCode.IMAGE_FORMAT_UNSUPPORTED: "图片格式不支持",
    ErrorCode.IMAGE_SIZE_EXCEEDED: "图片大小超限",
    ErrorCode.RECOGNITION_FAILED: "识别失败",
    ErrorCode.DIAGNOSIS_INCOMPLETE: "诊断未完成",
    ErrorCode.VARIANT_GENERATION_FAILED: "变形题生成失败",
    ErrorCode.DESCRIPTION_TOO_LONG: "描述长度超限",
    ErrorCode.RATE_LIMIT_EXCEEDED: "请求过于频繁",
    ErrorCode.QUOTA_EXHAUSTED: "配额已用完",
}


# ========== 自定义异常类 ==========

class APIException(Exception):
    """API基础异常类.
    
    Attributes:
        code: 错误码
        message: 错误消息
        data: 附加数据
        request_id: 请求追踪ID
    """
    
    def __init__(
        self,
        code: int,
        message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        self.code = code
        self.message = message or ERROR_CODE_MESSAGE_MAP.get(code, "未知错误")
        self.data = data or {}
        self.request_id = request_id
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式."""
        return {
            "code": self.code,
            "message": self.message,
            "data": self.data,
            "request_id": self.request_id,
            "timestamp": int(datetime.utcnow().timestamp()),
        }
    
    def get_http_status(self) -> int:
        """获取对应的HTTP状态码."""
        return ERROR_CODE_HTTP_MAP.get(self.code, status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotFoundException(APIException):
    """资源不存在异常."""
    
    def __init__(
        self,
        resource_type: str = "资源",
        resource_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        message = f"{resource_type}不存在"
        if resource_id:
            message = f"{resource_type}不存在: {resource_id}"
        super().__init__(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message=message,
            request_id=request_id,
        )


class ValidationException(APIException):
    """参数验证异常."""
    
    def __init__(
        self,
        message: str = "参数验证失败",
        errors: Optional[list] = None,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            code=ErrorCode.PARAM_INVALID,
            message=message,
            data={"errors": errors or []},
            request_id=request_id,
        )


class AuthenticationException(APIException):
    """认证异常."""
    
    def __init__(
        self,
        message: str = "认证失败",
        request_id: Optional[str] = None,
    ):
        super().__init__(
            code=ErrorCode.TOKEN_INVALID,
            message=message,
            request_id=request_id,
        )


class BusinessException(APIException):
    """业务逻辑异常."""
    
    def __init__(
        self,
        code: int = ErrorCode.SYSTEM_ERROR,
        message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        super().__init__(code, message, data, request_id)


# ========== 异常处理器 ==========

async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """处理API自定义异常."""
    logger.warning(
        "api_exception",
        code=exc.code,
        message=exc.message,
        path=request.url.path,
        request_id=exc.request_id,
    )
    return JSONResponse(
        status_code=exc.get_http_status(),
        content=exc.to_dict(),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """处理请求参数验证异常."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })
    
    api_exc = ValidationException(
        message="请求参数验证失败",
        errors=errors,
    )
    
    logger.warning(
        "validation_exception",
        path=request.url.path,
        errors=errors,
    )
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=api_exc.to_dict(),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理通用异常."""
    logger.exception(
        "unhandled_exception",
        path=request.url.path,
        error=str(exc),
    )
    
    api_exc = APIException(
        code=ErrorCode.SYSTEM_ERROR,
        message="系统内部错误，请稍后重试",
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=api_exc.to_dict(),
    )


# ========== 注册异常处理器 ==========

def register_exception_handlers(app):
    """注册所有异常处理器.
    
    Args:
        app: FastAPI应用实例
    """
    app.add_exception_handler(APIException, api_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
