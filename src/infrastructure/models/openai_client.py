"""OpenAI客户端实现.

支持GPT-4、GPT-4o等OpenAI模型，包含重试机制和流式输出。
"""

import base64
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import httpx
from openai import AsyncOpenAI, APIError, AuthenticationError, RateLimitError
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from src.infrastructure.logging import get_logger
from src.infrastructure.models.base import Message, ModelClient, ModelResponse, Usage
from src.infrastructure.models.exceptions import (
    ModelAuthenticationError,
    ModelClientError,
    ModelContentFilterError,
    ModelRateLimitError,
    ModelServerError,
    ModelTimeoutError,
    ModelValidationError,
)

logger = get_logger(__name__)


class OpenAIClient(ModelClient):
    """OpenAI API客户端.

    支持GPT-4、GPT-4o等模型的异步调用，包含自动重试和错误处理。

    Example:
        >>> config = OpenAIConfig(api_key="sk-...", model="gpt-4")
        >>> client = OpenAIClient(config)
        >>> response = await client.complete([
        ...     Message.system("你是一个数学助教"),
        ...     Message.user("请解释勾股定理"),
        ... ])
    """

    VISION_MODELS = {"gpt-4-vision-preview", "gpt-4o", "gpt-4o-mini"}

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        api_base: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: float = 60.0,
        max_retries: int = 3,
        organization: Optional[str] = None,
    ):
        """初始化OpenAI客户端.

        Args:
            api_key: OpenAI API密钥
            model: 默认模型名称
            api_base: 自定义API基础URL
            temperature: 生成温度
            max_tokens: 最大token数
            timeout: 请求超时时间
            max_retries: 最大重试次数
            organization: OpenAI组织ID
        """
        super().__init__(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
        )
        self.api_key = api_key
        self.api_base = api_base
        self.organization = organization

        # 初始化底层客户端
        client_kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "timeout": timeout,
            "max_retries": 0,  # 我们自己处理重试
        }
        if api_base:
            client_kwargs["base_url"] = api_base
        if organization:
            client_kwargs["organization"] = organization

        self._client = AsyncOpenAI(**client_kwargs)

    @property
    def provider(self) -> str:
        """模型提供商名称."""
        return "openai"

    def _map_exception(self, exc: Exception, attempt: int) -> ModelClientError:
        """将OpenAI异常映射为内部异常.

        Args:
            exc: 原始异常
            attempt: 当前尝试次数

        Returns:
            映射后的异常
        """
        if isinstance(exc, AuthenticationError):
            return ModelAuthenticationError(
                message="Invalid API key",
                provider=self.provider,
            )
        elif isinstance(exc, RateLimitError):
            retry_after = None
            if hasattr(exc, "headers") and exc.headers:
                retry_after_str = exc.headers.get("retry-after")
                if retry_after_str:
                    try:
                        retry_after = int(retry_after_str)
                    except ValueError:
                        pass
            return ModelRateLimitError(
                message="Rate limit exceeded",
                provider=self.provider,
                retry_after=retry_after,
            )
        elif isinstance(exc, APIError):
            status_code = getattr(exc, "status_code", None)
            if status_code == 400:
                return ModelValidationError(
                    message=str(exc),
                    provider=self.provider,
                )
            elif status_code == 500 or status_code == 503:
                return ModelServerError(
                    message="OpenAI server error",
                    provider=self.provider,
                    status_code=status_code or 500,
                )
            elif status_code == 504:
                return ModelTimeoutError(
                    message="OpenAI request timeout",
                    provider=self.provider,
                    timeout=self.timeout,
                )

        # 内容过滤错误通常包装在APIError中
        error_message = str(exc).lower()
        if "content_filter" in error_message or "content filter" in error_message:
            return ModelContentFilterError(
                message="Content filtered by safety system",
                provider=self.provider,
            )

        return ModelClientError(
            message=str(exc),
            provider=self.provider,
            model=self.model,
        )

    async def _call_with_retry(
        self,
        call_fn,
        *args,
        **kwargs,
    ) -> Any:
        """带重试机制的API调用.

        Args:
            call_fn: 要调用的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            API调用结果

        Raises:
            ModelClientError: 重试耗尽后抛出
        """
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                return await call_fn(*args, **kwargs)
            except (APIError, httpx.TimeoutException) as e:
                last_error = e
                mapped_error = self._map_exception(e, attempt)

                # 不重试认证错误
                if isinstance(mapped_error, ModelAuthenticationError):
                    raise mapped_error

                # 记录重试
                if attempt < self.max_retries:
                    wait_time = min(2 ** attempt, 30)  # 指数退避，最大30秒
                    logger.warning(
                        "openai_retry",
                        attempt=attempt,
                        max_retries=self.max_retries,
                        wait_time=wait_time,
                        error=str(e),
                    )
                    await self._sleep(wait_time)

        # 重试耗尽
        if last_error:
            raise self._map_exception(last_error, self.max_retries)

        raise ModelClientError("Max retries exceeded", provider=self.provider)

    async def _sleep(self, seconds: float) -> None:
        """异步休眠（可被测试覆盖）."""
        await __import__("asyncio").sleep(seconds)

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
        """
        params = self._get_effective_params(model, temperature, max_tokens)
        api_messages = self._prepare_messages(messages)

        logger.debug(
            "openai_complete_request",
            model=params["model"],
            message_count=len(api_messages),
        )

        start_time = time.time()

        try:
            completion: ChatCompletion = await self._call_with_retry(
                self._client.chat.completions.create,
                model=params["model"],
                messages=api_messages,
                temperature=params["temperature"],
                max_tokens=params["max_tokens"],
                **kwargs,
            )

            elapsed = time.time() - start_time

            # 解析响应
            choice = completion.choices[0]
            usage = completion.usage

            logger.debug(
                "openai_complete_success",
                model=params["model"],
                elapsed=elapsed,
                tokens_used=usage.total_tokens if usage else 0,
            )

            return ModelResponse(
                content=choice.message.content or "",
                model=completion.model,
                usage=Usage(
                    prompt_tokens=usage.prompt_tokens if usage else 0,
                    completion_tokens=usage.completion_tokens if usage else 0,
                    total_tokens=usage.total_tokens if usage else 0,
                ),
                finish_reason=choice.finish_reason,
                metadata={
                    "elapsed_time": elapsed,
                    "created": completion.created,
                    "system_fingerprint": completion.system_fingerprint,
                },
            )

        except ModelClientError:
            raise
        except Exception as e:
            logger.exception("openai_complete_error")
            raise ModelClientError(
                message=f"Unexpected error: {str(e)}",
                provider=self.provider,
                model=params["model"],
            )

    async def stream_complete(
        self,
        messages: List[Message],
        callback: Optional[callable] = None,
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
        """
        params = self._get_effective_params(model, temperature, max_tokens)
        api_messages = self._prepare_messages(messages)

        logger.debug(
            "openai_stream_request",
            model=params["model"],
            message_count=len(api_messages),
        )

        try:
            stream = await self._call_with_retry(
                self._client.chat.completions.create,
                model=params["model"],
                messages=api_messages,
                temperature=params["temperature"],
                max_tokens=params["max_tokens"],
                stream=True,
                **kwargs,
            )

            async for chunk in stream:
                chunk: ChatCompletionChunk
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        text = delta.content
                        if callback:
                            callback(text)
                        yield text

        except ModelClientError:
            raise
        except Exception as e:
            logger.exception("openai_stream_error")
            raise ModelClientError(
                message=f"Stream error: {str(e)}",
                provider=self.provider,
                model=params["model"],
            )

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
            model: 覆盖默认模型，需为视觉模型
            **kwargs: 额外参数

        Returns:
            模型响应
        """
        # 使用视觉模型
        effective_model = model or self.model
        if effective_model not in self.VISION_MODELS:
            effective_model = "gpt-4o"

        # 准备图片内容
        image_contents = []
        for img in images:
            if isinstance(img, bytes):
                base64_image = base64.b64encode(img).decode("utf-8")
            else:
                # 假设已经是base64字符串，去除可能的data URL前缀
                base64_image = img.split(",")[-1] if "," in img else img

            image_contents.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}",
                },
            })

        # 构建多模态消息
        # 最后一条用户消息加入图片
        api_messages = []
        for i, msg in enumerate(messages):
            msg_dict = msg.to_dict()

            # 如果是最后一条用户消息，添加图片
            if msg.role.value == "user" and i == len(messages) - 1:
                # 将纯文本消息转换为多模态
                text_content = msg_dict.get("content", "")
                msg_dict["content"] = [
                    {"type": "text", "text": text_content},
                    *image_contents,
                ]

            api_messages.append(msg_dict)

        logger.debug(
            "openai_vision_request",
            model=effective_model,
            image_count=len(images),
        )

        # 调用API
        completion: ChatCompletion = await self._call_with_retry(
            self._client.chat.completions.create,
            model=effective_model,
            messages=api_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **kwargs,
        )

        choice = completion.choices[0]
        usage = completion.usage

        return ModelResponse(
            content=choice.message.content or "",
            model=completion.model,
            usage=Usage(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            ),
            finish_reason=choice.finish_reason,
        )

    def count_tokens(self, text: str) -> int:
        """计算文本的token数量.

        使用简单的估算方法（每4个字符约1个token）。
        生产环境建议使用tiktoken。

        Args:
            text: 输入文本

        Returns:
            估算的token数量
        """
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model(self.model)
            return len(encoding.encode(text))
        except Exception:
            # 简单的字符数估算（每4个字符约1个token）
            return len(text) // 4 + 1
