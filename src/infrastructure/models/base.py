"""模型客户端抽象基类.

定义AI模型调用的标准接口和数据结构。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    Optional,
    Union,
)


class Role(str, Enum):
    """消息角色枚举."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """对话消息.

    Attributes:
        role: 消息角色
        content: 消息内容
        name: 发送者名称（可选，用于function calling）
        tool_calls: 工具调用信息（可选）
        tool_call_id: 工具调用ID（可选）
    """

    role: Role
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为API格式字典."""
        result: Dict[str, Any] = {
            "role": self.role.value,
            "content": self.content,
        }
        if self.name:
            result["name"] = self.name
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        return result

    @classmethod
    def system(cls, content: str) -> "Message":
        """创建系统消息."""
        return cls(role=Role.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> "Message":
        """创建用户消息."""
        return cls(role=Role.USER, content=content)

    @classmethod
    def assistant(cls, content: str) -> "Message":
        """创建助手消息."""
        return cls(role=Role.ASSISTANT, content=content)


@dataclass
class Usage:
    """Token使用情况."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ModelResponse:
    """模型响应.

    Attributes:
        content: 响应内容
        model: 使用的模型名称
        usage: Token使用情况
        finish_reason: 完成原因
        metadata: 额外元数据
    """

    content: str
    model: str
    usage: Usage = field(default_factory=Usage)
    finish_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# 流式回调类型
StreamingCallback = Callable[[str], None]


class ModelClient(ABC):
    """模型客户端抽象基类.

    所有AI模型客户端必须实现此接口，以提供统一的调用方式。

    Example:
        >>> client = OpenAIClient(config)
        >>> response = await client.complete([
        ...     Message.system("You are a helpful assistant"),
        ...     Message.user("Hello!"),
        ... ])
        >>> print(response.content)
    """

    def __init__(
        self,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        """初始化模型客户端.

        Args:
            model: 模型名称
            temperature: 生成温度 (0.0-2.0)
            max_tokens: 最大生成token数
            timeout: 请求超时时间(秒)
            max_retries: 最大重试次数
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    @abstractmethod
    def provider(self) -> str:
        """模型提供商名称."""
        pass

    @abstractmethod
    async def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """完成对话.

        Args:
            messages: 消息列表
            model: 覆盖默认模型
            temperature: 覆盖默认温度
            max_tokens: 覆盖默认最大token数
            **kwargs: 额外参数

        Returns:
            模型响应

        Raises:
            ModelClientError: 调用失败时抛出
        """
        pass

    @abstractmethod
    async def stream_complete(
        self,
        messages: List[Message],
        callback: Optional[StreamingCallback] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """流式完成对话.

        Args:
            messages: 消息列表
            callback: 流式回调函数
            model: 覆盖默认模型
            temperature: 覆盖默认温度
            max_tokens: 覆盖默认最大token数
            **kwargs: 额外参数

        Yields:
            流式响应文本片段

        Raises:
            ModelClientError: 调用失败时抛出
        """
        pass

    async def complete_with_vision(
        self,
        messages: List[Message],
        images: List[Union[str, bytes]],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """完成多模态对话（包含图片）.

        Args:
            messages: 消息列表
            images: 图片列表（base64字符串或字节）
            model: 覆盖默认模型
            **kwargs: 额外参数

        Returns:
            模型响应

        Raises:
            ModelClientError: 调用失败时抛出
            NotImplementedError: 如果模型不支持视觉
        """
        raise NotImplementedError("Vision not supported by this client")

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """计算文本的token数量.

        Args:
            text: 输入文本

        Returns:
            Token数量
        """
        pass

    def _get_effective_params(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """获取有效的参数值.

        Args:
            model: 可选的模型覆盖
            temperature: 可选的温度覆盖
            max_tokens: 可选的最大token覆盖

        Returns:
            参数字典
        """
        return {
            "model": model or self.model,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
        }

    def _prepare_messages(
        self,
        messages: List[Message],
    ) -> List[Dict[str, Any]]:
        """准备消息列表用于API调用.

        Args:
            messages: 消息对象列表

        Returns:
            API格式的消息字典列表
        """
        return [msg.to_dict() for msg in messages]
