"""变形策略模块.

提供多种变形题生成策略：
- 数值变形: 整数/分数/小数转换
- 逆运算变形: 等价性验证
- 情境迁移: 结构保持验证
"""

from .base import StrategyContext, StrategyResult, VariantStrategy
from .numeric_strategy import NumericVariationStrategy
from .inverse_strategy import InverseOperationStrategy
from .context_strategy import ContextTransferStrategy

__all__ = [
    "VariantStrategy",
    "StrategyContext",
    "StrategyResult",
    "NumericVariationStrategy",
    "InverseOperationStrategy",
    "ContextTransferStrategy",
]
