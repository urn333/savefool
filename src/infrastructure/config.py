"""配置管理模块.

使用pydantic-settings管理应用配置，支持.env文件加载。
"""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """运行环境枚举."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """日志级别枚举."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DatabaseConfig(BaseSettings):
    """数据库配置."""

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        extra="ignore",
    )

    url: str = Field(
        default="sqlite:///./data/app.db",
        description="数据库连接URL",
    )
    echo: bool = Field(
        default=False,
        description="是否输出SQL语句",
    )
    pool_size: int = Field(
        default=5,
        description="连接池大小",
    )
    max_overflow: int = Field(
        default=10,
        description="连接池最大溢出连接数",
    )
    pool_timeout: int = Field(
        default=30,
        description="连接池获取连接超时时间(秒)",
    )
    pool_recycle: int = Field(
        default=3600,
        description="连接回收时间(秒)",
    )


class OpenAIConfig(BaseSettings):
    """OpenAI API配置."""

    model_config = SettingsConfigDict(
        env_prefix="OPENAI_",
        extra="ignore",
    )

    api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API密钥",
    )
    api_base: Optional[str] = Field(
        default=None,
        description="OpenAI API基础URL",
    )
    model: str = Field(
        default="gpt-4",
        description="默认使用的模型",
    )
    vision_model: str = Field(
        default="gpt-4-vision-preview",
        description="视觉模型",
    )
    max_retries: int = Field(
        default=3,
        description="最大重试次数",
    )
    timeout: float = Field(
        default=60.0,
        description="请求超时时间(秒)",
    )
    temperature: float = Field(
        default=0.7,
        description="生成温度",
    )
    max_tokens: int = Field(
        default=2048,
        description="最大生成token数",
    )

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """验证温度参数范围."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")
        return v


class KimiConfig(BaseSettings):
    """Kimi Code API配置.
    
    官方文档: https://www.kimi.com/code/docs/more/third-party-agents.html
    """

    model_config = SettingsConfigDict(
        env_prefix="KIMI_",
        extra="ignore",
    )

    api_key: Optional[str] = Field(
        default=None,
        description="Kimi Code API密钥 (从 https://www.kimi.com/code 控制台获取)",
    )
    api_base: str = Field(
        default="https://api.kimi.com/coding/v1",
        description="Kimi Code API基础URL (OpenAI兼容模式)",
    )
    model: str = Field(
        default="kimi-for-coding",
        description="默认使用的模型 (kimi-for-coding 或 kimi-k2-thinking)",
    )
    vision_model: str = Field(
        default="kimi-k2.5",
        description="视觉模型",
    )
    max_retries: int = Field(
        default=3,
        description="最大重试次数",
    )
    timeout: float = Field(
        default=60.0,
        description="请求超时时间(秒)",
    )
    temperature: float = Field(
        default=0.7,
        description="生成温度",
    )
    max_tokens: int = Field(
        default=4096,
        description="最大生成token数",
    )

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """验证温度参数范围."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")
        return v


class AnthropicConfig(BaseSettings):
    """Anthropic API配置."""

    model_config = SettingsConfigDict(
        env_prefix="ANTHROPIC_",
        extra="ignore",
    )

    api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API密钥",
    )
    api_base: Optional[str] = Field(
        default=None,
        description="Anthropic API基础URL",
    )
    model: str = Field(
        default="claude-3-opus-20240229",
        description="默认使用的模型",
    )
    max_retries: int = Field(
        default=3,
        description="最大重试次数",
    )
    timeout: float = Field(
        default=60.0,
        description="请求超时时间(秒)",
    )
    temperature: float = Field(
        default=0.7,
        description="生成温度",
    )
    max_tokens: int = Field(
        default=2048,
        description="最大生成token数",
    )


class DeepSeekConfig(BaseSettings):
    """DeepSeek API配置."""

    model_config = SettingsConfigDict(
        env_prefix="DEEPSEEK_",
        extra="ignore",
    )

    api_key: Optional[str] = Field(
        default=None,
        description="DeepSeek API密钥",
    )
    api_base: str = Field(
        default="https://api.deepseek.com/v1",
        description="DeepSeek API基础URL",
    )
    model: str = Field(
        default="deepseek-chat",
        description="默认使用的模型",
    )
    math_model: str = Field(
        default="deepseek-reasoner",
        description="数学推理专用模型",
    )
    max_retries: int = Field(
        default=3,
        description="最大重试次数",
    )
    timeout: float = Field(
        default=60.0,
        description="请求超时时间(秒)",
    )
    temperature: float = Field(
        default=0.7,
        description="生成温度",
    )
    max_tokens: int = Field(
        default=2048,
        description="最大生成token数",
    )


class LlamaConfig(BaseSettings):
    """Llama本地模型配置."""

    model_config = SettingsConfigDict(
        env_prefix="LLAMA_",
        extra="ignore",
    )

    enabled: bool = Field(
        default=False,
        description="是否启用本地Llama模型",
    )
    model_path: Optional[str] = Field(
        default=None,
        description="模型文件路径",
    )
    host: str = Field(
        default="localhost",
        description="模型服务主机",
    )
    port: int = Field(
        default=8000,
        description="模型服务端口",
    )
    temperature: float = Field(
        default=0.7,
        description="生成温度",
    )
    max_tokens: int = Field(
        default=2048,
        description="最大生成token数",
    )


class LoggingConfig(BaseSettings):
    """日志配置."""

    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        extra="ignore",
    )

    level: LogLevel = Field(
        default=LogLevel.INFO,
        description="日志级别",
    )
    format: str = Field(
        default="json",
        description="日志格式 (json|console)",
    )
    dir: Path = Field(
        default=Path("./logs"),
        description="日志文件目录",
    )
    max_bytes: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        description="单个日志文件最大大小(字节)",
    )
    backup_count: int = Field(
        default=5,
        description="日志文件备份数量",
    )
    separate_files: bool = Field(
        default=True,
        description="是否按级别分离日志文件",
    )

    @field_validator("dir")
    @classmethod
    def validate_dir(cls, v: Path) -> Path:
        """验证并创建日志目录."""
        v.mkdir(parents=True, exist_ok=True)
        return v


class VectorDBConfig(BaseSettings):
    """向量数据库配置."""

    model_config = SettingsConfigDict(
        env_prefix="VECTOR_",
        extra="ignore",
    )

    provider: str = Field(
        default="chroma",
        description="向量数据库提供商 (chroma|pinecone|weaviate)",
    )
    host: str = Field(
        default="localhost",
        description="服务主机",
    )
    port: int = Field(
        default=8000,
        description="服务端口",
    )
    collection_name: str = Field(
        default="ai_tutor",
        description="集合/索引名称",
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="使用的嵌入模型",
    )
    dimension: int = Field(
        default=1536,
        description="向量维度",
    )


class DiagnosisConfig(BaseSettings):
    """诊断引擎配置."""

    model_config = SettingsConfigDict(
        env_prefix="DIAG_",
        extra="ignore",
    )

    timeout_seconds: int = Field(
        default=90,
        description="诊断超时时间(秒)",
    )
    enable_streaming: bool = Field(
        default=True,
        description="是否启用流式输出",
    )
    confidence_threshold: float = Field(
        default=0.8,
        description="诊断置信度阈值",
    )
    max_variants_per_problem: int = Field(
        default=3,
        description="每道错题生成变形题的最大数量",
    )


class MemoryConfig(BaseSettings):
    """记忆系统配置."""

    model_config = SettingsConfigDict(
        env_prefix="MEMORY_",
        extra="ignore",
    )

    crystallization_hour: int = Field(
        default=2,
        description="每日结晶时间(小时，0-23)",
    )
    retention_days: Dict[str, int] = Field(
        default={
            "episodic": 90,
            "semantic": 365,
            "meta": 180,
        },
        description="各类记忆保留天数",
    )
    auto_compact: bool = Field(
        default=True,
        description="是否启用自动压缩",
    )
    compact_threshold: int = Field(
        default=10000,
        description="触发压缩的记录数阈值",
    )


class Settings(BaseSettings):
    """应用主配置类.

    整合所有子配置，提供统一的配置访问接口。
    支持从.env文件加载配置。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 基础配置
    env: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="运行环境",
    )
    app_name: str = Field(
        default="AI助教系统",
        description="应用名称",
    )
    app_version: str = Field(
        default="1.0.0",
        description="应用版本",
    )
    debug: bool = Field(
        default=False,
        description="调试模式",
    )
    secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        description="应用密钥",
    )

    # 模型提供商选择
    active_model_provider: str = Field(
        default="openai",
        description="当前激活的模型提供商 (openai|kimi)",
    )
    
    # 子配置
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    kimi: KimiConfig = Field(default_factory=KimiConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    deepseek: DeepSeekConfig = Field(default_factory=DeepSeekConfig)
    llama: LlamaConfig = Field(default_factory=LlamaConfig)
    vector_db: VectorDBConfig = Field(default_factory=VectorDBConfig)
    diagnosis: DiagnosisConfig = Field(default_factory=DiagnosisConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)

    # API配置
    api_host: str = Field(
        default="0.0.0.0",
        description="API服务主机",
    )
    api_port: int = Field(
        default=8000,
        description="API服务端口",
    )
    api_workers: int = Field(
        default=1,
        description="API工作进程数",
    )
    api_prefix: str = Field(
        default="/api/v1",
        description="API路径前缀",
    )
    cors_origins: List[str] = Field(
        default=["*"],
        description="CORS允许的来源",
    )
    upload_dir: str = Field(
        default="./uploads",
        description="上传文件存储目录",
    )

    @property
    def is_development(self) -> bool:
        """是否为开发环境."""
        return self.env == Environment.DEVELOPMENT

    @property
    def is_testing(self) -> bool:
        """是否为测试环境."""
        return self.env == Environment.TESTING

    @property
    def is_production(self) -> bool:
        """是否为生产环境."""
        return self.env == Environment.PRODUCTION
    
    @property
    def VERSION(self) -> str:
        """应用版本（兼容属性）."""
        return self.app_version
    
    @property
    def API_PREFIX(self) -> str:
        """API前缀（兼容属性）."""
        return self.api_prefix
    
    @property
    def CORS_ORIGINS(self) -> List[str]:
        """CORS来源（兼容属性）."""
        return self.cors_origins
    
    @property
    def UPLOAD_DIR(self) -> str:
        """上传目录（兼容属性）."""
        return self.upload_dir

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典.

        Returns:
            配置字典，敏感信息会被脱敏。
        """
        return {
            "env": self.env.value,
            "app_name": self.app_name,
            "app_version": self.app_version,
            "debug": self.debug,
            "api_host": self.api_host,
            "api_port": self.api_port,
            "database": {
                "echo": self.database.echo,
                "pool_size": self.database.pool_size,
            },
            "logging": {
                "level": self.logging.level.value,
                "format": self.logging.format,
            },
            "diagnosis": {
                "timeout_seconds": self.diagnosis.timeout_seconds,
                "confidence_threshold": self.diagnosis.confidence_threshold,
            },
        }


# 全局配置实例
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取配置实例.

    使用单例模式，确保配置只被加载一次。

    Returns:
        Settings: 配置实例
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """重新加载配置.

    用于在运行时刷新配置（如配置文件变更后）。

    Returns:
        Settings: 新的配置实例
    """
    global _settings
    _settings = Settings()
    return _settings
