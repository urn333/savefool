"""变形题生成策略模块.

提供不同维度的变形题生成策略，支持数值、逆运算、情境等多种变形方式。
"""

from src.domain.engines.variant_strategies.base import (
    StrategyContext,
    StrategyResult,
    VariantStrategy,
)
from src.domain.engines.variant_strategies.context_strategy import (
    ContextTransferStrategy,
)
from src.domain.engines.variant_strategies.inverse_strategy import (
    InverseOperationStrategy,
)
from src.domain.engines.variant_strategies.numeric_strategy import (
    NumericVariationStrategy,
)

__all__ = [
    "VariantStrategy",
    "StrategyContext",
    "StrategyResult",
    "NumericVariationStrategy",
    "InverseOperationStrategy",
    "ContextTransferStrategy",
]
