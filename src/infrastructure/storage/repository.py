"""Repository模式实现.

本模块提供通用的CRUD操作和分页查询功能.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql import Select

from src.infrastructure.db import Base

ModelType = TypeVar("ModelType", bound=Base)


class Pagination:
    """分页参数类."""

    def __init__(self, page: int = 1, page_size: int = 20):
        """初始化分页参数.

        Args:
            page: 页码，从1开始.
            page_size: 每页记录数.
        """
        self.page = max(1, page)
        self.page_size = max(1, min(page_size, 100))  # 最大100条

    @property
    def offset(self) -> int:
        """计算偏移量."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """获取限制数量."""
        return self.page_size


class PageResult(Generic[ModelType]):
    """分页结果类."""

    def __init__(
        self,
        items: List[ModelType],
        total: int,
        page: int,
        page_size: int,
    ):
        """初始化分页结果.

        Args:
            items: 当前页数据列表.
            total: 总记录数.
            page: 当前页码.
            page_size: 每页记录数.
        """
        self.items = items
        self.total = total
        self.page = page
        self.page_size = page_size
        self.total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        self.has_next = page < self.total_pages
        self.has_prev = page > 1

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式.

        Returns:
            分页结果字典.
        """
        return {
            "items": [
                item.to_dict() if hasattr(item, "to_dict") else item
                for item in self.items
            ],
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": self.total_pages,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
        }


class BaseRepository(Generic[ModelType], ABC):
    """基础Repository抽象类.

    提供通用的CRUD操作接口.
    """

    def __init__(self, session: AsyncSession):
        """初始化Repository.

        Args:
            session: 数据库会话.
        """
        self.session = session

    @property
    @abstractmethod
    def model_class(self) -> Type[ModelType]:
        """获取模型类."""
        pass

    @property
    @abstractmethod
    def primary_key(self) -> InstrumentedAttribute:
        """获取主键字段."""
        pass

    async def get_by_id(self, id: str) -> Optional[ModelType]:
        """根据ID获取实体.

        Args:
            id: 实体ID.

        Returns:
            实体对象，不存在时返回None.
        """
        stmt = select(self.model_class).where(self.primary_key == id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_ids(self, ids: List[str]) -> List[ModelType]:
        """根据ID列表批量获取实体.

        Args:
            ids: 实体ID列表.

        Returns:
            实体对象列表.
        """
        if not ids:
            return []
        stmt = select(self.model_class).where(self.primary_key.in_(ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all(
        self,
        pagination: Optional[Pagination] = None,
        order_by: Optional[InstrumentedAttribute] = None,
        desc_order: bool = False,
    ) -> Union[List[ModelType], PageResult[ModelType]]:
        """获取所有实体.

        Args:
            pagination: 分页参数，None时返回全部.
            order_by: 排序字段.
            desc_order: 是否降序.

        Returns:
            实体列表或分页结果.
        """
        stmt = select(self.model_class)

        # 添加排序
        if order_by is not None:
            stmt = stmt.order_by(desc(order_by) if desc_order else asc(order_by))

        # 添加分页
        if pagination:
            # 先查询总数
            count_stmt = select(func.count()).select_from(self.model_class)
            count_result = await self.session.execute(count_stmt)
            total = count_result.scalar()

            # 再查询分页数据
            stmt = stmt.offset(pagination.offset).limit(pagination.limit)
            result = await self.session.execute(stmt)
            items = list(result.scalars().all())

            return PageResult(
                items=items,
                total=total,
                page=pagination.page,
                page_size=pagination.page_size,
            )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, entity: ModelType) -> ModelType:
        """创建实体.

        Args:
            entity: 实体对象.

        Returns:
            创建的实体对象.
        """
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def create_many(self, entities: List[ModelType]) -> List[ModelType]:
        """批量创建实体.

        Args:
            entities: 实体对象列表.

        Returns:
            创建的实体对象列表.
        """
        self.session.add_all(entities)
        await self.session.flush()
        return entities

    async def update(self, entity: ModelType) -> ModelType:
        """更新实体.

        Args:
            entity: 实体对象.

        Returns:
            更新后的实体对象.
        """
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update_many(
        self,
        ids: List[str],
        update_data: Dict[str, Any],
    ) -> int:
        """批量更新实体.

        Args:
            ids: 要更新的实体ID列表.
            update_data: 更新的字段和值.

        Returns:
            更新的记录数.
        """
        if not ids or not update_data:
            return 0

        stmt = (
            self.model_class.__table__.update()
            .where(self.primary_key.in_(ids))
            .values(**update_data)
        )
        result = await self.session.execute(stmt)
        return result.rowcount

    async def delete(self, entity: ModelType) -> None:
        """删除实体.

        Args:
            entity: 实体对象.
        """
        await self.session.delete(entity)
        await self.session.flush()

    async def delete_by_id(self, id: str) -> bool:
        """根据ID删除实体.

        Args:
            id: 实体ID.

        Returns:
            是否删除成功.
        """
        entity = await self.get_by_id(id)
        if entity:
            await self.delete(entity)
            return True
        return False

    async def delete_many(self, ids: List[str]) -> int:
        """批量删除实体.

        Args:
            ids: 要删除的实体ID列表.

        Returns:
            删除的记录数.
        """
        if not ids:
            return 0

        stmt = self.model_class.__table__.delete().where(self.primary_key.in_(ids))
        result = await self.session.execute(stmt)
        return result.rowcount

    async def exists(self, id: str) -> bool:
        """检查实体是否存在.

        Args:
            id: 实体ID.

        Returns:
            是否存在.
        """
        stmt = select(func.count()).where(self.primary_key == id)
        result = await self.session.execute(stmt)
        return result.scalar() > 0

    async def count(self) -> int:
        """获取总记录数.

        Returns:
            记录总数.
        """
        stmt = select(func.count()).select_from(self.model_class)
        result = await self.session.execute(stmt)
        return result.scalar()

    async def find_one(self, **filters) -> Optional[ModelType]:
        """根据条件查询单个实体.

        Args:
            **filters: 过滤条件.

        Returns:
            实体对象，不存在时返回None.
        """
        stmt = select(self.model_class)
        for key, value in filters.items():
            if hasattr(self.model_class, key):
                stmt = stmt.where(getattr(self.model_class, key) == value)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_many(
        self,
        pagination: Optional[Pagination] = None,
        order_by: Optional[InstrumentedAttribute] = None,
        desc_order: bool = False,
        **filters,
    ) -> Union[List[ModelType], PageResult[ModelType]]:
        """根据条件查询多个实体.

        Args:
            pagination: 分页参数，None时返回全部.
            order_by: 排序字段.
            desc_order: 是否降序.
            **filters: 过滤条件.

        Returns:
            实体列表或分页结果.
        """
        stmt = select(self.model_class)

        # 添加过滤条件
        for key, value in filters.items():
            if hasattr(self.model_class, key):
                stmt = stmt.where(getattr(self.model_class, key) == value)

        # 添加排序
        if order_by is not None:
            stmt = stmt.order_by(desc(order_by) if desc_order else asc(order_by))

        # 添加分页
        if pagination:
            # 先查询总数
            count_stmt = stmt.with_only_columns(func.count())
            count_result = await self.session.execute(count_stmt)
            total = count_result.scalar()

            # 再查询分页数据
            stmt = stmt.offset(pagination.offset).limit(pagination.limit)
            result = await self.session.execute(stmt)
            items = list(result.scalars().all())

            return PageResult(
                items=items,
                total=total,
                page=pagination.page,
                page_size=pagination.page_size,
            )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())
