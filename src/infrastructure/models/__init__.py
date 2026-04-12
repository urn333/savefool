"""模型客户端模块.

提供统一的AI模型调用接口，支持多模型切换和流式输出。
"""

from src.infrastructure.models.base import (
    Message,
    ModelClient,
    ModelResponse,
    Role,
    StreamingCallback,
    Usage,
)
from src.infrastructure.models.openai_client import OpenAIClient
from src.infrastructure.models.baidu_ocr_client import BaiduOCRClient
from src.infrastructure.models.gemini_client import GeminiClient
from src.infrastructure.models.client_factory import (
    create_model_client,
    create_ocr_client,
    get_active_provider,
    get_active_model,
)
from src.infrastructure.models.exceptions import (
    ModelAuthenticationError,
    ModelClientError,
    ModelContentFilterError,
    ModelRateLimitError,
    ModelServerError,
    ModelTimeoutError,
    ModelValidationError,
)

__all__ = [
    # 基础类型
    "Message",
    "Role",
    "ModelResponse",
    "Usage",
    "StreamingCallback",
    # 抽象基类
    "ModelClient",
    # 具体实现
    "OpenAIClient",
    "BaiduOCRClient",
    "GeminiClient",
    # 工厂函数
    "create_model_client",
    "create_ocr_client",
    "get_active_provider",
    "get_active_model",
    # 异常
    "ModelClientError",
    "ModelAuthenticationError",
    "ModelRateLimitError",
    "ModelTimeoutError",
    "ModelValidationError",
    "ModelContentFilterError",
    "ModelServerError",
]
