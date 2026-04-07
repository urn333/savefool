"""数据库连接管理.

本模块提供数据库引擎和会话管理功能，支持异步操作.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.orm import sessionmaker

from src.infrastructure.db import Base

# 默认数据库URL，使用SQLite
DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./data/ai_tutor.db"

# 从环境变量获取数据库URL
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


class DatabaseManager:
    """数据库管理器.

    管理数据库引擎和会话的创建与生命周期.
    """

    def __init__(self, database_url: Optional[str] = None):
        """初始化数据库管理器.

        Args:
            database_url: 数据库连接URL，默认从环境变量获取.
        """
        self.database_url = database_url or DATABASE_URL
        self._async_engine: Optional[object] = None
        self._async_session_maker: Optional[async_sessionmaker] = None
        self._sync_engine: Optional[object] = None
        self._sync_session_maker: Optional[sessionmaker] = None

    def _get_async_url(self) -> str:
        """获取异步数据库URL.

        Returns:
            适配异步驱动器的URL.
        """
        url = self.database_url
        # 如果是SQLite且不是异步驱动，转换为aiosqlite
        if url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
            url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        return url

    def _get_sync_url(self) -> str:
        """获取同步数据库URL.

        Returns:
            适配同步驱动器的URL.
        """
        url = self.database_url
        # 确保使用同步驱动
        if url.startswith("sqlite+aiosqlite://"):
            url = url.replace("sqlite+aiosqlite://", "sqlite://", 1)
        elif url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return url

    @property
    def async_engine(self):
        """获取异步引擎（延迟初始化）."""
        if self._async_engine is None:
            self._async_engine = create_async_engine(
                self._get_async_url(),
                echo=os.getenv("SQL_ECHO", "false").lower() == "true",
                future=True,
            )
        return self._async_engine

    @property
    def async_session_maker(self):
        """获取异步会话工厂（延迟初始化）."""
        if self._async_session_maker is None:
            self._async_session_maker = async_sessionmaker(
                self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
        return self._async_session_maker

    @property
    def sync_engine(self):
        """获取同步引擎（延迟初始化）."""
        if self._sync_engine is None:
            self._sync_engine = create_engine(
                self._get_sync_url(),
                echo=os.getenv("SQL_ECHO", "false").lower() == "true",
                future=True,
            )
        return self._sync_engine

    @property
    def sync_session_maker(self):
        """获取同步会话工厂（延迟初始化）."""
        if self._sync_session_maker is None:
            self._sync_session_maker = sessionmaker(
                self.sync_engine,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
        return self._sync_session_maker

    async def create_tables(self) -> None:
        """创建所有表结构."""
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self) -> None:
        """删除所有表结构."""
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    def create_tables_sync(self) -> None:
        """同步方式创建所有表结构."""
        Base.metadata.create_all(bind=self.sync_engine)

    def drop_tables_sync(self) -> None:
        """同步方式删除所有表结构."""
        Base.metadata.drop_all(bind=self.sync_engine)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """异步上下文管理器，提供数据库会话.

        Yields:
            异步数据库会话.

        Example:
            >>> async with db_manager.session() as session:
            ...     result = await session.execute(query)
        """
        async_session = self.async_session_maker()
        try:
            yield async_session
            await async_session.commit()
        except Exception:
            await async_session.rollback()
            raise
        finally:
            await async_session.close()

    async def close(self) -> None:
        """关闭数据库连接."""
        if self._async_engine:
            await self._async_engine.dispose()
            self._async_engine = None
        if self._sync_engine:
            self._sync_engine.dispose()
            self._sync_engine = None


# 全局数据库管理器实例
db_manager = DatabaseManager()


# 依赖注入使用的异步会话生成器
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI依赖注入使用的异步会话生成器.

    Yields:
        异步数据库会话.
    """
    async with db_manager.session() as session:
        yield session
