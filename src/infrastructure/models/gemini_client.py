"""Google Gemini客户端.

Google Gemini多模态API，支持图片理解、题目分析。
免费额度：
- Gemini 2.0 Flash: 1500次/分钟，免费额度非常慷慨
- Gemini Pro: 有限免费额度

功能：
- 图片理解：识别图片中的数学/物理题目
- 题目分析：理解题意、分析解题步骤
- 答案批改：判断对错、指出错误

文档：https://ai.google.dev/docs
"""

import base64
import json
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import httpx

from src.infrastructure.logging import get_logger
from src.infrastructure.models.base import Message, ModelClient, ModelResponse, Usage
from src.infrastructure.models.exceptions import (
    ModelAuthenticationError,
    ModelClientError,
    ModelRateLimitError,
    ModelServerError,
    ModelTimeoutError,
)

logger = get_logger(__name__)


class GeminiClient(ModelClient):
    """Google Gemini API客户端.
    
    支持多模态理解，可以分析图片中的题目并给出详细解答。
    
    Example:
        >>> client = GeminiClient(api_key="your_api_key")
        >>> response = await client.complete_with_vision(
        ...     messages=[Message.user("分析这道数学题")],
        ...     images=[base64_image]
        ... )
        >>> print(response.content)  # 题目分析和解答
    """
    
    # API配置
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash-exp",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        """初始化Gemini客户端.
        
        Args:
            api_key: Google AI API Key
            model: 模型名称 (gemini-2.0-flash-exp / gemini-1.5-flash / gemini-1.5-pro)
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
        self.api_key = api_key
        
        # 初始化HTTP客户端
        self._client = httpx.AsyncClient(
            timeout=timeout,
        )
    
    @property
    def provider(self) -> str:
        """模型提供商名称."""
        return "google_gemini"
    
    def _build_request_body(
        self,
        messages: List[Message],
        images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """构建Gemini API请求体.
        
        Args:
            messages: 消息列表
            images: 图片列表（base64编码）
            
        Returns:
            API请求体
        """
        # Gemini使用不同的消息格式
        contents = []
        
        # 处理消息和图片
        for msg in messages:
            role = "user" if msg.role.value == "user" else "model"
            
            parts = [{"text": msg.content}]
            
            # 如果是用户消息且有图片，添加图片
            if role == "user" and images:
                for img_base64 in images:
                    # 清理base64数据
                    if "," in img_base64:
                        img_base64 = img_base64.split(",", 1)[1]
                    
                    parts.append({
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": img_base64,
                        }
                    })
                images = []  # 只添加一次
            
            contents.append({
                "role": role,
                "parts": parts,
            })
        
        return {
            "contents": contents,
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
                "topP": 0.95,
                "topK": 40,
            },
        }
    
    async def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """纯文本对话.
        
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
        
        request_body = self._build_request_body(messages)
        request_body["generationConfig"]["temperature"] = temp
        request_body["generationConfig"]["maxOutputTokens"] = max_tok
        
        url = f"{self.BASE_URL}/models/{model_name}:generateContent?key={self.api_key}"
        
        logger.info(
            "gemini_request",
            model=model_name,
            message_count=len(messages),
        )
        
        try:
            response = await self._client.post(
                url,
                json=request_body,
            )
            response.raise_for_status()
            
            data = response.json()
            
            # 解析响应
            if "candidates" not in data or not data["candidates"]:
                error_msg = "No response generated"
                if "promptFeedback" in data:
                    error_msg = data["promptFeedback"].get("blockReason", error_msg)
                raise ModelServerError(
                    message=f"Gemini生成失败: {error_msg}",
                    provider=self.provider,
                )
            
            candidate = data["candidates"][0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            
            text_parts = [p["text"] for p in parts if "text" in p]
            full_text = "".join(text_parts)
            
            # 获取token使用情况
            usage_metadata = data.get("usageMetadata", {})
            prompt_tokens = usage_metadata.get("promptTokenCount", 0)
            completion_tokens = usage_metadata.get("candidatesTokenCount", 0)
            
            logger.info(
                "gemini_response",
                model=model_name,
                content_length=len(full_text),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            
            return ModelResponse(
                content=full_text,
                usage=Usage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                ),
                model=model_name,
                finish_reason=candidate.get("finishReason", "stop").lower(),
            )
            
        except httpx.TimeoutException:
            raise ModelTimeoutError(
                message="请求超时",
                provider=self.provider,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise ModelRateLimitError(
                    message="请求过于频繁，请稍后再试",
                    provider=self.provider,
                )
            elif e.response.status_code in [401, 403]:
                raise ModelAuthenticationError(
                    message="API Key无效或已过期",
                    provider=self.provider,
                )
            else:
                raise ModelServerError(
                    message=f"服务器错误: {e.response.status_code}",
                    provider=self.provider,
                )
    
    async def complete_with_vision(
        self,
        messages: List[Message],
        images: List[str],
        model: Optional[str] = None,
        **kwargs,
    ) -> ModelResponse:
        """多模态完成对话（图片理解）.
        
        Args:
            messages: 消息列表
            images: 图片列表（base64编码）
            model: 模型名称(可选)
            **kwargs: 其他参数
            
        Returns:
            模型响应
        """
        # Gemini原生支持多模态，直接调用complete即可
        return await self.complete(
            messages=messages,
            model=model,
            **kwargs,
        )
    
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
        
        request_body = self._build_request_body(messages)
        url = f"{self.BASE_URL}/models/{model_name}:streamGenerateContent?alt=sse&key={self.api_key}"
        
        full_content = ""
        
        try:
            async with self._client.stream("POST", url, json=request_body) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    
                    try:
                        data = json.loads(line[6:])  # 去掉 "data: " 前缀
                        
                        if "candidates" in data and data["candidates"]:
                            candidate = data["candidates"][0]
                            content = candidate.get("content", {})
                            parts = content.get("parts", [])
                            
                            for part in parts:
                                if "text" in part:
                                    chunk = part["text"]
                                    full_content += chunk
                                    
                                    if callback:
                                        await callback(chunk)
                        
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
            raise ModelServerError(
                message=f"流式请求失败: {e}",
                provider=self.provider,
            )
    
    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """估算token数量.
        
        Gemini使用大致估算：
        - 中文约1.5字符/token
        - 英文约4字符/token
        
        Args:
            text: 文本内容
            model: 模型名称（忽略）
            
        Returns:
            估算的token数量
        """
        return int(len(text) / 2.5)
    
    async def health_check(self) -> bool:
        """检查服务健康状态.
        
        Returns:
            是否健康
        """
        try:
            # 简单请求检查
            url = f"{self.BASE_URL}/models?key={self.api_key}"
            response = await self._client.get(url)
            return response.status_code == 200
        except Exception:
            return False
    
    async def list_models(self) -> List[str]:
        """列出可用的模型.
        
        Returns:
            模型名称列表
        """
        try:
            url = f"{self.BASE_URL}/models?key={self.api_key}"
            response = await self._client.get(url)
            response.raise_for_status()
            
            data = response.json()
            models = data.get("models", [])
            
            # 过滤出支持的生成模型
            gemini_models = [
                m["name"].replace("models/", "")
                for m in models
                if "gemini" in m["name"] and "generateContent" in m.get("supportedGenerationMethods", [])
            ]
            
            return gemini_models
            
        except Exception as e:
            logger.error("list_models_failed", error=str(e))
            return []
    
    async def close(self):
        """关闭客户端."""
        await self._client.aclose()
