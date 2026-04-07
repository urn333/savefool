"""结构化日志系统.

使用structlog实现结构化日志，支持JSON格式输出和级别分离。
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import structlog
from structlog.processors import (
    JSONRenderer,
    TimeStamper,
    add_log_level,
    dict_tracebacks,
)
from structlog.stdlib import (
    ExtraAdder,
    LoggerFactory,
    add_logger_name,
    filter_by_level,
)

from src.infrastructure.config import LogLevel, get_settings


def _get_log_level(level: Union[str, LogLevel]) -> int:
    """转换日志级别.

    Args:
        level: 日志级别字符串或枚举

    Returns:
        标准日志级别数值
    """
    if isinstance(level, LogLevel):
        level = level.value
    return getattr(logging, level.upper(), logging.INFO)


def _create_file_handler(
    log_dir: Path,
    filename: str,
    level: int,
    max_bytes: int,
    backup_count: int,
) -> RotatingFileHandler:
    """创建文件日志处理器.

    Args:
        log_dir: 日志目录
        filename: 日志文件名
        level: 日志级别
        max_bytes: 单个文件最大字节数
        backup_count: 备份文件数量

    Returns:
        RotatingFileHandler实例
    """
    log_path = log_dir / filename
    handler = RotatingFileHandler(
        filename=log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    return handler


def _configure_stdlib_logging(
    log_dir: Path,
    level: Union[str, LogLevel],
    max_bytes: int,
    backup_count: int,
    separate_files: bool,
    format_type: str,
) -> None:
    """配置标准库日志.

    Args:
        log_dir: 日志目录
        level: 日志级别
        max_bytes: 单个文件最大字节数
        backup_count: 备份文件数量
        separate_files: 是否按级别分离日志文件
        format_type: 日志格式类型 (json|console)
    """
    log_level = _get_log_level(level)

    # 基础配置
    handlers: List[logging.Handler] = []

    if separate_files:
        # 分离不同级别的日志到不同文件
        handlers.extend([
            _create_file_handler(log_dir, "debug.log", logging.DEBUG, max_bytes, backup_count),
            _create_file_handler(log_dir, "info.log", logging.INFO, max_bytes, backup_count),
            _create_file_handler(log_dir, "warning.log", logging.WARNING, max_bytes, backup_count),
            _create_file_handler(log_dir, "error.log", logging.ERROR, max_bytes, backup_count),
        ])
    else:
        # 所有级别写入同一个文件
        handlers.append(
            _create_file_handler(log_dir, "app.log", logging.DEBUG, max_bytes, backup_count)
        )

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    handlers.append(console_handler)

    # 格式化器
    if format_type == "json":
        formatter = logging.Formatter(
            "%(message)s"  # JSON格式通过structlog处理
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    for handler in handlers:
        handler.setFormatter(formatter)

    # 根日志器配置
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除现有处理器
    root_logger.handlers = []

    for handler in handlers:
        root_logger.addHandler(handler)

    # 设置第三方库的日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def _configure_structlog(format_type: str) -> None:
    """配置structlog.

    Args:
        format_type: 日志格式类型 (json|console)
    """
    processors: List[Any] = [
        filter_by_level,
        add_log_level,
        add_logger_name,
        TimeStamper(fmt="iso"),
        ExtraAdder(),
    ]

    if format_type == "json":
        processors.extend([
            structlog.processors.format_exc_info,
            dict_tracebacks,
            JSONRenderer(),
        ])
    else:
        processors.extend([
            structlog.dev.ConsoleRenderer(
                colors=True,
                pad_level=False,
            ),
        ])

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            _get_log_level(get_settings().logging.level)
        ),
        context_class=dict,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def configure_logging() -> None:
    """配置日志系统.

    根据配置初始化日志系统，包括标准库日志和structlog。
    """
    settings = get_settings()
    log_config = settings.logging

    # 确保日志目录存在
    log_config.dir.mkdir(parents=True, exist_ok=True)

    # 配置标准库日志
    _configure_stdlib_logging(
        log_dir=log_config.dir,
        level=log_config.level,
        max_bytes=log_config.max_bytes,
        backup_count=log_config.backup_count,
        separate_files=log_config.separate_files,
        format_type=log_config.format,
    )

    # 配置structlog
    _configure_structlog(format_type=log_config.format)


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """获取日志记录器.

    Args:
        name: 日志记录器名称，通常为模块名

    Returns:
        绑定的日志记录器

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("user_logged_in", user_id="123")
        {"event": "user_logged_in", "user_id": "123", ...}
    """
    return structlog.get_logger(name)


class LoggerMixin:
    """日志混入类.

    为类提供便捷的日志记录功能。

    Example:
        >>> class MyService(LoggerMixin):
        ...     def do_something(self):
        ...         self.logger.info("doing_something")
    """

    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """获取类日志记录器."""
        return get_logger(self.__class__.__module__)


# 便捷函数

def bind_context(**kwargs: Any) -> structlog.stdlib.BoundLogger:
    """绑定上下文到日志记录器.

    Args:
        **kwargs: 要绑定的键值对

    Returns:
        绑定后的日志记录器

    Example:
        >>> logger = bind_context(request_id="abc", user_id="123")
        >>> logger.info("request_started")
    """
    return get_logger().bind(**kwargs)


def clear_context() -> None:
    """清除日志上下文."""
    structlog.contextvars.clear_contextvars()


def log_exception(
    logger: structlog.stdlib.BoundLogger,
    exc: Exception,
    message: str = "exception_occurred",
    **kwargs: Any,
) -> None:
    """记录异常信息.

    Args:
        logger: 日志记录器
        exc: 异常对象
        message: 日志消息
        **kwargs: 额外的上下文信息
    """
    logger.error(
        message,
        exc_info=True,
        error_type=exc.__class__.__name__,
        error_message=str(exc),
        **kwargs,
    )
