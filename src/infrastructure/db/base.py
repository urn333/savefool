"""SQLAlchemy基类定义.

本模块包含所有ORM模型的基类.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有ORM模型的基类."""

    type_annotation_map = {
        datetime: DateTime,
    }

    def to_dict(self) -> dict[str, Any]:
        """将模型实例转换为字典.

        Returns:
            包含模型字段的字典.
        """
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
