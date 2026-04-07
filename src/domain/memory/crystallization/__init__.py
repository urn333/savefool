"""24小时结晶机制实现.

本模块实现AI助教系统的24小时记忆结晶机制，包括:
- 结晶调度器: 定时执行结晶任务
- 条件判定: 检查结晶条件
- 执行器: 执行结晶过程
- 数据压缩: 记忆数据自动压缩
- 监控: 结晶过程监控与告警

功能追溯ID: F-MEM-004, F-MEM-005, F-MEM-006
"""

from src.domain.memory.crystallization.conditions import (
    CrystallizationConditions,
    CrystallizationTrigger,
)
from src.domain.memory.crystallization.executor import (
    CrystallizationExecutor,
    CrystallizationRecord,
)
from src.domain.memory.crystallization.scheduler import CrystallizationScheduler
from src.domain.memory.crystallization.monitor import (
    CrystallizationMonitor,
    CrystallizationAlert,
    AlertLevel,
)
from src.domain.memory.crystallization.compaction import (
    MemoryCompaction,
    EpisodicCompression,
    ImageArchiveRecord,
)

__all__ = [
    "CrystallizationScheduler",
    "CrystallizationConditions",
    "CrystallizationTrigger",
    "CrystallizationExecutor",
    "CrystallizationRecord",
    "CrystallizationMonitor",
    "CrystallizationAlert",
    "AlertLevel",
    "MemoryCompaction",
    "EpisodicCompression",
    "ImageArchiveRecord",
]
