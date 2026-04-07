"""领域模型基类.

提供所有领域模型共享的基础功能。
"""

from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def generate_id(prefix: str = "") -> str:
    """生成带前缀的唯一ID.

    Args:
        prefix: ID前缀

    Returns:
        唯一ID字符串
    """
    uid = str(uuid4()).replace("-", "")[:16]
    if prefix:
        return f"{prefix}_{uid}"
    return uid


def now_timestamp() -> datetime:
    """获取当前UTC时间.

    Returns:
        当前UTC时间
    """
    return datetime.utcnow()


class DomainModel(BaseModel):
    """领域模型基类.

    所有领域模型都继承此类，提供统一的序列化和验证。
    """

    model_config = ConfigDict(
        # 允许从ORM对象创建
        from_attributes=True,
        # 允许字段名作为别名
        populate_by_name=True,
        # 忽略未声明的字段
        extra="ignore",
        # 支持JSON序列化
        json_encoders={
            datetime: lambda v: v.isoformat(),
        },
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典.

        Returns:
            模型字典表示
        """
        return self.model_dump(mode="json")

    def to_json(self) -> str:
        """转换为JSON字符串.

        Returns:
            JSON字符串
        """
        return self.model_dump_json()


class TimestampMixin(BaseModel):
    """时间戳混入类.

    为模型添加创建和更新时间戳。
    """

    created_at: datetime = Field(
        default_factory=now_timestamp,
        description="创建时间",
    )
    updated_at: datetime = Field(
        default_factory=now_timestamp,
        description="更新时间",
    )


class VersionMixin(BaseModel):
    """版本混入类.

    为模型添加版本控制支持。
    """

    version: int = Field(
        default=1,
        description="版本号",
        ge=1,
    )

    def increment_version(self) -> None:
        """递增版本号."""
        self.version += 1
