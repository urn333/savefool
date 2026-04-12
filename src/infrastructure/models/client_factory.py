"""模型客户端工厂.

根据配置自动创建对应的模型客户端(OpenAI或Kimi)。
"""

from typing import Optional

from src.infrastructure.config import get_settings, OpenAIConfig, KimiConfig, OllamaConfig, GeminiConfig
from src.infrastructure.models.base import ModelClient
from src.infrastructure.models.openai_client import OpenAIClient
from src.infrastructure.models.ollama_client import OllamaClient
from src.infrastructure.models.gemini_client import GeminiClient
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


def create_model_client(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    timeout: float = 60.0,
    max_retries: int = 3,
) -> ModelClient:
    """创建模型客户端.
    
    根据配置自动选择使用 OpenAI 还是 Kimi。
    
    Args:
        provider: 模型提供商 (openai|kimi)，默认从配置读取
        model: 模型名称，默认使用配置的模型
        temperature: 生成温度
        max_tokens: 最大token数
        timeout: 请求超时时间
        max_retries: 最大重试次数
        
    Returns:
        模型客户端实例
        
    Example:
        >>> # 使用默认配置创建客户端
        >>> client = create_model_client()
        >>> 
        >>> # 显式指定提供商和模型
        >>> client = create_model_client(provider="kimi", model="kimi-k2.5")
    """
    settings = get_settings()
    
    # 确定使用哪个提供商
    if provider is None:
        provider = getattr(settings, 'active_model_provider', 'openai')
    
    provider = provider.lower()
    
    if provider == 'kimi':
        # 使用 Kimi
        kimi_config: KimiConfig = settings.kimi
        api_key = kimi_config.api_key
        api_base = kimi_config.api_base
        
        # 判断是否启用 Thinking 模式
        if kimi_config.enable_thinking and model is None:
            model_name = kimi_config.thinking_model
            logger.info("kimi_thinking_mode_enabled", model=model_name)
        else:
            model_name = model or kimi_config.model
            
        vision_model = kimi_config.vision_model
        
        if not api_key:
            raise ValueError(
                "Kimi API Key 未配置。请在 .env 文件中设置 kimi_api_key，"
                "或从 https://www.kimi.com/code 控制台获取。"
            )
        
        logger.info(
            "creating_kimi_client",
            model=model_name,
            api_base=api_base,
            thinking_mode=kimi_config.enable_thinking,
        )
        
        return OpenAIClient(
            api_key=api_key,
            model=model_name,
            api_base=api_base,
            temperature=temperature,
            max_tokens=max_tokens or kimi_config.max_tokens,
            timeout=timeout,
            max_retries=max_retries,
        )
        
    elif provider == 'ollama':
        # 使用 Ollama 本地/局域网服务
        ollama_config: OllamaConfig = settings.ollama
        api_base = ollama_config.api_base
        model_name = model or ollama_config.model
        
        logger.info(
            "creating_ollama_client",
            model=model_name,
            api_base=api_base,
        )
        
        return OllamaClient(
            api_base=api_base,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens or ollama_config.max_tokens,
            timeout=timeout,
            max_retries=max_retries,
        )
        
    elif provider == 'openai':
        # 使用 OpenAI
        openai_config: OpenAIConfig = settings.openai
        api_key = openai_config.api_key
        api_base = openai_config.api_base
        model_name = model or openai_config.model
        
        if not api_key:
            raise ValueError(
                "OpenAI API Key 未配置。请在 .env 文件中设置 openai_api_key。"
            )
        
        logger.info(
            "creating_openai_client",
            model=model_name,
        )
        
        return OpenAIClient(
            api_key=api_key,
            model=model_name,
            api_base=api_base,
            temperature=temperature,
            max_tokens=max_tokens or openai_config.max_tokens,
            timeout=timeout,
            max_retries=max_retries,
        )
        
    elif provider == 'gemini':
        # 使用 Google Gemini（推荐，免费额度 generous）
        gemini_config: GeminiConfig = settings.gemini
        api_key = gemini_config.api_key
        model_name = model or gemini_config.model
        
        if not api_key:
            raise ValueError(
                "Gemini API Key 未配置。请在 .env 文件中设置 gemini_api_key，"
                "或从 https://ai.google.dev/ 获取。"
            )
        
        logger.info(
            "creating_gemini_client",
            model=model_name,
        )
        
        return GeminiClient(
            api_key=api_key,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens or gemini_config.max_tokens,
            timeout=timeout,
            max_retries=max_retries,
        )
    else:
        raise ValueError(f"不支持的模型提供商: {provider}，请使用 'openai'、'kimi'、'ollama' 或 'gemini'")


def get_active_provider() -> str:
    """获取当前激活的模型提供商.
    
    Returns:
        提供商名称 (openai|kimi)
    """
    settings = get_settings()
    return getattr(settings, 'active_model_provider', 'openai')


def get_active_model() -> str:
    """获取当前激活的模型名称.
    
    Returns:
        模型名称
    """
    settings = get_settings()
    provider = get_active_provider()
    
    if provider == 'kimi':
        return settings.kimi.model
    else:
        return settings.openai.model


def create_ocr_client(provider: Optional[str] = None):
    """创建OCR客户端.
    
    用于图片文字识别，支持百度OCR等免费服务。
    
    Args:
        provider: OCR提供商 (baidu_ocr|ollama)，默认从配置读取
        
    Returns:
        OCR客户端实例
        
    Example:
        >>> # 使用百度OCR（推荐，中文识别效果好）
        >>> client = create_ocr_client("baidu_ocr")
        >>> 
        >>> # 使用Ollama本地模型
        >>> client = create_ocr_client("ollama")
    """
    from src.infrastructure.config import BaiduOCRConfig
    from src.infrastructure.models.baidu_ocr_client import BaiduOCRClient
    
    settings = get_settings()
    
    # 确定使用哪个提供商
    if provider is None:
        # 优先使用百度OCR（如果配置）
        baidu_config: BaiduOCRConfig = settings.baidu_ocr
        if baidu_config.enabled and baidu_config.api_key and baidu_config.secret_key:
            provider = "baidu_ocr"
        else:
            provider = "ollama"
    
    provider = provider.lower()
    
    if provider == 'baidu_ocr':
        # 使用百度OCR
        baidu_config: BaiduOCRConfig = settings.baidu_ocr
        api_key = baidu_config.api_key
        secret_key = baidu_config.secret_key
        
        if not api_key or not secret_key:
            raise ValueError(
                "百度OCR API Key 或 Secret Key 未配置。"
                "请在 .env 文件中设置 baidu_ocr_api_key 和 baidu_ocr_secret_key，"
                "或从 https://cloud.baidu.com/product/ocr 申请。"
            )
        
        logger.info("creating_baidu_ocr_client")
        
        return BaiduOCRClient(
            api_key=api_key,
            secret_key=secret_key,
            timeout=baidu_config.timeout,
        )
    
    elif provider == 'ollama':
        # 使用Ollama本地模型
        ollama_config = settings.ollama
        
        logger.info(
            "creating_ollama_ocr_client",
            model=ollama_config.model,
            api_base=ollama_config.api_base,
        )
        
        return OllamaClient(
            api_base=ollama_config.api_base,
            model=ollama_config.model,
            timeout=ollama_config.timeout,
        )
    
    else:
        raise ValueError(f"不支持的OCR提供商: {provider}，请使用 'baidu_ocr' 或 'ollama'")
