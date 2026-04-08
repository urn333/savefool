"""Ollama客户端实现.

支持本地或局域网Ollama服务，兼容OpenAI API格式。
"""

import json
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import httpx
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


class OllamaClient(ModelClient):
    """Ollama API客户端.

    支持本地或局域网Ollama服务，兼容OpenAI API格式。

    Example:
        >>> client = OllamaClient(
        ...     api_base="http://192.168.1.100:11434",
        ...     model="gemma4"
        ... )
        >>> response = await client.complete([
        ...     Message.system("你是一个数学助教"),
        ...     Message.user("请解释勾股定理"),
        ... ])
    """

    def __init__(
        self,
        api_base: str = "http://localhost:11434",
        model: str = "gemma4",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        """初始化Ollama客户端.

        Args:
            api_base: Ollama服务地址 (如 http://localhost:11434)
            model: 模型名称
            temperature: 生成温度
            max_tokens: 最大token数
            timeout: 请求超时时间
            max_retries: 最大重试次数
        """
        super().__init__(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
        )
        self.api_base = api_base.rstrip("/")
        self.api_key = "ollama"  # Ollama通常不需要API Key

        # 初始化HTTP客户端
        self._client = httpx.AsyncClient(
            base_url=self.api_base,
            timeout=timeout,
        )

    @property
    def provider(self) -> str:
        """模型提供商名称."""
        return "ollama"

    def _map_exception(self, exc: Exception, attempt: int) -> ModelClientError:
        """将异常映射为内部异常."""
        if isinstance(exc, httpx.TimeoutException):
            return ModelTimeoutError(
                message=f"请求超时 (attempt {attempt})",
                provider=self.provider,
            )
        elif isinstance(exc, httpx.ConnectError):
            return ModelServerError(
                message=f"无法连接到Ollama服务: {self.api_base}",
                provider=self.provider,
            )
        elif isinstance(exc, httpx.HTTPStatusError):
            status_code = exc.response.status_code
            if status_code == 401:
                return ModelAuthenticationError(
                    message="认证失败",
                    provider=self.provider,
                )
            elif status_code == 429:
                return ModelRateLimitError(
                    message="请求过于频繁",
                    provider=self.provider,
                )
            elif status_code >= 500:
                return ModelServerError(
                    message=f"服务器错误: {status_code}",
                    provider=self.provider,
                )
            else:
                return ModelValidationError(
                    message=f"请求错误: {status_code}",
                    provider=self.provider,
                )
        else:
            return ModelClientError(
                message=str(exc),
                provider=self.provider,
            )

    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, str]]:
        """转换消息格式为Ollama格式."""
        return [
            {
                "role": msg.role.value,
                "content": msg.content,
            }
            for msg in messages
        ]
    
    def _format_messages_for_generate(self, messages: List[Message]) -> str:
        """将消息列表格式化为单个prompt字符串 (用于 /api/generate).
        
        Args:
            messages: 消息列表
            
        Returns:
            格式化后的prompt字符串
        """
        parts = []
        for msg in messages:
            role = msg.role.value
            content = msg.content
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
        return "\n\n".join(parts) + "\n\nAssistant:"

    async def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """完成对话.

        Args:
            messages: 消息列表
            model: 模型名称(可选)
            temperature: 温度(可选)
            max_tokens: 最大token数(可选)
            **kwargs: 其他参数

        Returns:
            模型响应
        """
        model_name = model or self.model
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens

        request_data = {
            "model": model_name,
            "messages": self._convert_messages(messages),
            "stream": False,
            "options": {
                "temperature": temp,
                "num_predict": max_tok,
            },
        }

        logger.info(
            "ollama_request",
            model=model_name,
            message_count=len(messages),
        )

        for attempt in range(1, self.max_retries + 1):
            try:
                # Ollama /api/generate 格式
                prompt = self._format_messages_for_generate(messages)
                generate_request = {
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temp,
                        "num_predict": max_tok,
                    },
                }
                
                response = await self._client.post(
                    "/api/generate",
                    json=generate_request,
                )
                response.raise_for_status()
                data = response.json()

                content = data.get("response", "")

                logger.info(
                    "ollama_response",
                    model=model_name,
                    content_length=len(content),
                )

                return ModelResponse(
                    content=content,
                    usage=Usage(
                        prompt_tokens=data.get("prompt_eval_count", 0),
                        completion_tokens=data.get("eval_count", 0),
                        total_tokens=data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                    ),
                    model=model_name,
                    finish_reason="stop",
                )

            except Exception as e:
                mapped_exc = self._map_exception(e, attempt)
                if attempt < self.max_retries:
                    logger.warning(
                        "ollama_retry",
                        attempt=attempt,
                        max_retries=self.max_retries,
                        error=str(e),
                    )
                    await self._sleep_with_backoff(attempt)
                else:
                    raise mapped_exc

        raise ModelClientError("Max retries exceeded", provider=self.provider)

    async def stream_complete(
        self,
        messages: List[Message],
        callback: Optional[Any] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> ModelResponse:
        """流式完成对话.

        Args:
            messages: 消息列表
            callback: 流式回调函数
            model: 模型名称(可选)
            **kwargs: 其他参数

        Returns:
            完整的模型响应
        """
        model_name = model or self.model
        temp = kwargs.get("temperature", self.temperature)
        max_tok = kwargs.get("max_tokens", self.max_tokens)

        # Ollama /api/generate 格式
        prompt = self._format_messages_for_generate(messages)
        request_data = {
            "model": model_name,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temp,
                "num_predict": max_tok,
            },
        }

        full_content = ""

        try:
            async with self._client.stream(
                "POST",
                "/api/generate",
                json=request_data,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        # /api/generate 返回的是 "response" 字段
                        chunk = data.get("response", "")
                        full_content += chunk

                        if callback:
                            await callback(chunk)

                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue

            return ModelResponse(
                content=full_content,
                usage=Usage(
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                ),
                model=model_name,
                finish_reason="stop",
            )

        except Exception as e:
            raise self._map_exception(e, 1)

    async def complete_with_vision(
        self,
        messages: List[Message],
        images: List[str],
        model: Optional[str] = None,
        **kwargs,
    ) -> ModelResponse:
        """多模态完成对话 (图片理解).

        Ollama /api/generate 支持 images 参数传递图片 base64。
        适用于 llava、gemma4 等多模态模型。

        Args:
            messages: 消息列表
            images: 图片列表 (base64编码字符串，不含data:image前缀)
            model: 模型名称(可选)
            **kwargs: 其他参数

        Returns:
            模型响应
        """
        model_name = model or self.model
        temp = kwargs.get("temperature", self.temperature)
        max_tok = kwargs.get("max_tokens", self.max_tokens)

        # 提取用户提示词 (最后一条用户消息)
        prompt = ""
        for msg in reversed(messages):
            if msg.role.value == "user":
                prompt = msg.content
                break
        
        if not prompt:
            prompt = "请描述这张图片"

        # 清理图片数据 (去掉可能的 data:image 前缀)
        clean_images = []
        for img in images:
            if "," in img:
                # 有 data:image/jpeg;base64, 前缀
                clean_images.append(img.split(",", 1)[1])
            else:
                clean_images.append(img)

        request_data = {
            "model": model_name,
            "prompt": prompt,
            "images": clean_images,
            "stream": False,
            "options": {
                "temperature": temp,
                "num_predict": max_tok,
            },
        }

        logger.info(
            "ollama_vision_request",
            model=model_name,
            image_count=len(clean_images),
            prompt_length=len(prompt),
        )

        try:
            response = await self._client.post(
                "/api/generate",
                json=request_data,
            )
            response.raise_for_status()
            data = response.json()

            content = data.get("response", "")

            logger.info(
                "ollama_vision_response",
                model=model_name,
                content_length=len(content),
                prompt_eval=data.get("prompt_eval_count", 0),
                eval_count=data.get("eval_count", 0),
            )

            return ModelResponse(
                content=content,
                usage=Usage(
                    prompt_tokens=data.get("prompt_eval_count", 0),
                    completion_tokens=data.get("eval_count", 0),
                    total_tokens=data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                ),
                model=model_name,
                finish_reason="stop",
            )

        except Exception as e:
            raise self._map_exception(e, 1)

    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """估算token数量.

        Ollama没有内置的token计数API，使用简单估算。

        Args:
            text: 文本内容
            model: 模型名称(可选)

        Returns:
            估算的token数量
        """
        # 简单估算: 中文约1.5字符/token，英文约4字符/token
        # 这里使用保守估计
        return int(len(text) / 3)

    async def _sleep_with_backoff(self, attempt: int):
        """指数退避等待."""
        import asyncio
        wait_time = min(2 ** attempt, 60)
        await asyncio.sleep(wait_time)

    async def health_check(self) -> bool:
        """检查Ollama服务健康状态.

        Returns:
            是否健康
        """
        try:
            response = await self._client.get("/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        """列出可用的模型.

        Returns:
            模型名称列表
        """
        try:
            response = await self._client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
        except Exception as e:
            logger.error("list_models_failed", error=str(e))
            return []
