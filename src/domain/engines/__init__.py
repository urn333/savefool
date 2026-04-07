"""仲裁引擎模块.

提供三模型仲裁的核心功能，包括模型调度、并行协调、决策仲裁和结果融合。
"""

from src.domain.engines.model_schedulers import (
    ModelAScheduler,
    ModelBScheduler,
    ModelCScheduler,
    SchedulerConfig,
    ParsedProblem,
)
from src.domain.engines.parallel_coordinator import (
    ParallelCoordinator,
    CoordinatorConfig,
    ModelTaskResult,
)
from src.domain.engines.arbitration_engine import (
    ArbitrationEngine,
    ArbitrationConfig,
    ArbitrationStatus,
)
from src.domain.engines.result_fusion import (
    ResultFusion,
    FusionConfig,
    FusionResult,
    FieldSource,
)

__all__ = [
    # 模型调度器
    "ModelAScheduler",
    "ModelBScheduler",
    "ModelCScheduler",
    "SchedulerConfig",
    "ParsedProblem",
    # 并行协调器
    "ParallelCoordinator",
    "CoordinatorConfig",
    "ModelTaskResult",
    # 仲裁引擎
    "ArbitrationEngine",
    "ArbitrationConfig",
    "ArbitrationStatus",
    # 结果融合
    "ResultFusion",
    "FusionConfig",
    "FusionResult",
    "FieldSource",
]
