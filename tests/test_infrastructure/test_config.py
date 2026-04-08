"""配置管理测试."""

import os
import tempfile
from pathlib import Path

import pytest

from src.infrastructure.config import (
    DatabaseConfig,
    Environment,
    LogLevel,
    OpenAIConfig,
    Settings,
    get_settings,
    reload_settings,
)


class TestEnvironment:
    """环境枚举测试."""

    def test_environment_values(self):
        """测试环境枚举值."""
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.TESTING.value == "testing"
        assert Environment.PRODUCTION.value == "production"


class TestLogLevel:
    """日志级别枚举测试."""

    def test_log_level_values(self):
        """测试日志级别枚举值."""
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.ERROR.value == "ERROR"


class TestDatabaseConfig:
    """数据库配置测试."""

    def test_default_values(self):
        """测试默认值."""
        config = DatabaseConfig()
        assert config.url == "sqlite:///./data/app.db"
        assert config.echo is False
        assert config.pool_size == 5

    def test_custom_values(self):
        """测试自定义值."""
        config = DatabaseConfig(
            url="postgresql://user:pass@localhost/db",
            echo=True,
            pool_size=10,
        )
        assert config.url == "postgresql://user:pass@localhost/db"
        assert config.echo is True
        assert config.pool_size == 10


class TestOpenAIConfig:
    """OpenAI配置测试."""

    def test_default_values(self):
        """测试默认值."""
        config = OpenAIConfig()
        assert config.model == "gpt-4"
        assert config.temperature == 0.7
        assert config.max_retries == 3

    def test_temperature_validation(self):
        """测试温度参数验证."""
        with pytest.raises(ValueError):
            OpenAIConfig(temperature=3.0)

        with pytest.raises(ValueError):
            OpenAIConfig(temperature=-0.1)

        config = OpenAIConfig(temperature=1.5)
        assert config.temperature == 1.5


class TestSettings:
    """主配置测试."""

    def test_default_settings(self):
        """测试默认配置."""
        # 使用 _env_file=None 避免加载项目 .env 文件
        settings = Settings(_env_file=None)
        assert settings.app_name == "AI助教系统"
        assert settings.app_version == "1.0.0"
        assert settings.debug is False

    def test_environment_detection(self):
        """测试环境检测."""
        settings = Settings(env=Environment.DEVELOPMENT)
        assert settings.is_development is True
        assert settings.is_testing is False
        assert settings.is_production is False

        settings = Settings(env=Environment.PRODUCTION)
        assert settings.is_development is False
        assert settings.is_production is True

    def test_to_dict(self):
        """测试配置转字典."""
        settings = Settings()
        config_dict = settings.to_dict()

        assert "env" in config_dict
        assert "app_name" in config_dict
        assert "database" in config_dict
        assert "logging" in config_dict


class TestGetSettings:
    """获取配置测试."""

    def test_singleton(self):
        """测试单例模式."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_reload(self):
        """测试重新加载."""
        settings1 = get_settings()
        settings2 = reload_settings()
        assert settings1 is not settings2
