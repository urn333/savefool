"""枚举类型定义.

本模块包含所有数据模型使用的枚举类型定义.
"""

from enum import Enum as PyEnum


class ErrorType(str, PyEnum):
    """错因类型枚举."""

    CARELESS = "careless"  # 粗心错误
    METHOD_ERROR = "method_error"  # 方法错误
    CONCEPT_GAP = "concept_gap"  # 概念漏洞
    CALCULATION_ERROR = "calculation_error"  # 计算错误
    READING_ERROR = "reading_error"  # 审题错误
    UNKNOWN = "unknown"  # 未知类型


class VariantType(str, PyEnum):
    """变形类型枚举."""

    NUMERIC_CHANGE = "numeric_change"  # 数值变化
    INVERSE_OPERATION = "inverse_operation"  # 逆运算
    CONTEXT_TRANSFER = "context_transfer"  # 情境迁移
    DIFFICULTY_ADJUST = "difficulty_adjust"  # 难度调整
    FORMAT_CHANGE = "format_change"  # 形式变化


class GapStatus(str, PyEnum):
    """认知缺口状态枚举."""

    PENDING = "pending"  # 待验证
    CRYSTALLIZED = "crystallized"  # 已固化
    DISMISSED = "dismissed"  # 已排除


class ValidationStatus(str, PyEnum):
    """变形题验证状态枚举."""

    PENDING = "pending"  # 待验证
    VALIDATED = "validated"  # 验证通过
    FAILED = "failed"  # 验证失败
    EXPIRED = "expired"  # 已过期


class HomeworkStatus(str, PyEnum):
    """作业状态枚举."""

    ACTIVE = "active"  # 活跃
    ARCHIVED = "archived"  # 已归档
    DELETED = "deleted"  # 已删除


class EvidenceType(str, PyEnum):
    """证据类型枚举."""

    INITIAL_DIAGNOSIS = "initial_diagnosis"  # 初始诊断
    REPEAT_ERROR = "repeat_error"  # 重复错误
    VARIANT_FAILED = "variant_failed"  # 变形题失败
    CROSS_HOMEWORK = "cross_homework"  # 跨作业共现


class SourceType(str, PyEnum):
    """家长描述来源类型枚举."""

    TEXT = "text"  # 文本
    VOICE = "voice"  # 语音
    VIDEO = "video"  # 视频
