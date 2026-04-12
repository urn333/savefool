"""百度OCR客户端.

百度智能云OCR服务，提供免费的文字识别API。
免费额度：
- 个人用户：每月几万次调用
- 企业用户：每月更高额度

支持的识别类型：
- 通用文字识别（高精度版）
- 手写文字识别
- 公式识别
- 表格识别

文档：https://cloud.baidu.com/doc/OCR/index.html
"""

import base64
import json
import time
from typing import Any, Dict, List, Optional

import httpx

from src.infrastructure.logging import get_logger
from src.infrastructure.models.base import Message, ModelClient, ModelResponse, Usage
from src.infrastructure.models.exceptions import (
    ModelAuthenticationError,
    ModelClientError,
    ModelRateLimitError,
    ModelServerError,
)

logger = get_logger(__name__)


class BaiduOCRClient(ModelClient):
    """百度OCR API客户端.
    
    使用百度智能云OCR服务进行文字识别。
    需要先申请API Key和Secret Key。
    
    Example:
        >>> client = BaiduOCRClient(
        ...     api_key="your_api_key",
        ...     secret_key="your_secret_key"
        ... )
        >>> response = await client.complete_with_vision(
        ...     messages=[Message.user("识别图片中的文字")],
        ...     images=[base64_image]
        ... )
    """
    
    # API地址
    TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
    OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"
    HANDWRITING_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/handwriting"
    FORMULA_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/formula"
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        timeout: float = 30.0,
    ):
        """初始化百度OCR客户端.
        
        Args:
            api_key: API Key（从百度智能云控制台获取）
            secret_key: Secret Key（从百度智能云控制台获取）
            timeout: 请求超时时间
        """
        super().__init__(
            model="baidu_ocr",
            temperature=0.0,  # OCR不需要温度参数
            max_tokens=4096,
            timeout=timeout,
        )
        self.api_key = api_key
        self.secret_key = secret_key
        self.access_token: Optional[str] = None
        self.token_expire_time: float = 0
        
        # 初始化HTTP客户端
        self._client = httpx.AsyncClient(timeout=timeout)
    
    @property
    def provider(self) -> str:
        """模型提供商名称."""
        return "baidu_ocr"
    
    async def _get_access_token(self) -> str:
        """获取百度API访问令牌.
        
        令牌有效期为30天，需要缓存避免频繁获取。
        
        Returns:
            访问令牌
        """
        # 检查令牌是否有效
        if self.access_token and time.time() < self.token_expire_time:
            return self.access_token
        
        # 获取新令牌
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key,
        }
        
        try:
            response = await self._client.post(self.TOKEN_URL, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if "access_token" not in data:
                error_msg = data.get("error_description", "Unknown error")
                raise ModelAuthenticationError(
                    message=f"获取访问令牌失败: {error_msg}",
                    provider=self.provider,
                )
            
            self.access_token = data["access_token"]
            # 提前5分钟过期
            expires_in = data.get("expires_in", 2592000)  # 默认30天
            self.token_expire_time = time.time() + expires_in - 300
            
            logger.info("baidu_token_refreshed")
            return self.access_token
            
        except httpx.HTTPError as e:
            raise ModelServerError(
                message=f"获取访问令牌请求失败: {e}",
                provider=self.provider,
            )
    
    async def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """纯文本对话（百度OCR不支持，抛出错误）.
        
        Args:
            messages: 消息列表
            model: 模型名称（忽略）
            temperature: 温度（忽略）
            max_tokens: 最大token数（忽略）
            **kwargs: 其他参数
            
        Raises:
            ModelClientError: 百度OCR不支持纯文本对话
        """
        raise ModelClientError(
            message="百度OCR不支持纯文本对话，请使用 complete_with_vision 方法",
            provider=self.provider,
        )
    
    async def complete_with_vision(
        self,
        messages: List[Message],
        images: List[str],
        model: Optional[str] = None,
        ocr_type: str = "general",  # general, handwriting, formula
        **kwargs,
    ) -> ModelResponse:
        """图片文字识别.
        
        Args:
            messages: 消息列表（用于构建提示，实际识别不依赖此参数）
            images: 图片列表（base64编码，不含data:image前缀）
            model: 模型名称（忽略）
            ocr_type: OCR类型 - general(通用)/handwriting(手写)/formula(公式)
            **kwargs: 其他参数
            
        Returns:
            识别结果
        """
        if not images:
            raise ModelClientError(
                message="需要提供至少一张图片",
                provider=self.provider,
            )
        
        # 获取访问令牌
        access_token = await self._get_access_token()
        
        # 选择API地址
        if ocr_type == "handwriting":
            api_url = self.HANDWRITING_URL
        elif ocr_type == "formula":
            api_url = self.FORMULA_URL
        else:
            api_url = self.OCR_URL
        
        # 处理第一张图片
        image_data = images[0]
        
        # 清理base64数据
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]
        
        logger.info(
            "baidu_ocr_request",
            ocr_type=ocr_type,
            image_size=len(image_data),
        )
        
        try:
            # 构建请求
            url = f"{api_url}?access_token={access_token}"
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            data = {"image": image_data}
            
            response = await self._client.post(url, headers=headers, data=data)
            response.raise_for_status()
            
            result = response.json()
            
            # 检查错误
            if "error_code" in result:
                error_code = result["error_code"]
                error_msg = result.get("error_msg", "Unknown error")
                
                if error_code == 18:  # QPS超限
                    raise ModelRateLimitError(
                        message=f"请求过于频繁: {error_msg}",
                        provider=self.provider,
                    )
                elif error_code in [110, 111, 100]:  # 认证错误
                    raise ModelAuthenticationError(
                        message=f"认证失败: {error_msg}",
                        provider=self.provider,
                    )
                else:
                    raise ModelServerError(
                        message=f"OCR识别失败: {error_msg}",
                        provider=self.provider,
                    )
            
            # 解析识别结果
            words_result = result.get("words_result", [])
            
            # 合并所有识别到的文字
            texts = []
            for item in words_result:
                text = item.get("words", "").strip()
                if text:
                    texts.append(text)
            
            content = "\n".join(texts)
            
            # 计算大致的token数（中文约1字/token，英文约4字符/token）
            total_chars = len(content)
            estimated_tokens = max(int(total_chars / 2), 1)
            
            logger.info(
                "baidu_ocr_response",
                text_lines=len(words_result),
                content_length=len(content),
            )
            
            return ModelResponse(
                content=content,
                usage=Usage(
                    prompt_tokens=estimated_tokens,
                    completion_tokens=0,
                    total_tokens=estimated_tokens,
                ),
                model="baidu_ocr",
                finish_reason="stop",
            )
            
        except httpx.TimeoutException:
            raise ModelServerError(
                message="请求超时",
                provider=self.provider,
            )
        except httpx.HTTPError as e:
            raise ModelServerError(
                message=f"HTTP错误: {e}",
                provider=self.provider,
            )
    
    async def stream_complete(self, *args, **kwargs) -> ModelResponse:
        """流式完成（百度OCR不支持）."""
        raise ModelClientError(
            message="百度OCR不支持流式输出",
            provider=self.provider,
        )
    
    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """估算token数量.
        
        对于中文，大致按字符数估算。
        
        Args:
            text: 文本内容
            model: 模型名称（忽略）
            
        Returns:
            估算的token数量
        """
        return max(len(text) // 2, 1)
    
    async def health_check(self) -> bool:
        """检查服务健康状态.
        
        Returns:
            是否健康
        """
        try:
            await self._get_access_token()
            return True
        except Exception:
            return False
    
    async def close(self):
        """关闭客户端."""
        await self._client.aclose()
