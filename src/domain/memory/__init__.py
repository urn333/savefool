"""记忆系统模块.

OpenHarness风格的四层记忆系统实现：
- Profile记忆层: 长期认知画像
- Episodic记忆层: 作业事件流
- Semantic记忆层: 结构化知识
- Meta记忆层: 元认知层(24小时结晶)
- MemoryManager: 统一接口

功能追溯ID: F-MEM-001 ~ F-MEM-008
"""

from src.domain.memory.episodic_memory import (
    DecisionTrace,
    EpisodeQuery,
    EpisodicMemory,
    ProblemAttempt,
    VariantLineage,
)
from src.domain.memory.meta_memory import (
    CRYSTALLIZATION_PERIOD_HOURS,
    CrystallizationResult,
    CrystallizedFeature,
    MetaMemory,
    PendingGap,
)
from src.domain.memory.memory_manager import (
    CompressionResult,
    MemoryManager,
    MemoryQuery,
    MemorySnapshot,
)
from src.domain.memory.profile_memory import (
    CognitiveFeatureVector,
    ErrorDNA,
    ProfileMemory,
    StudentCognitiveProfile,
    ThinkingStyle,
    ZPDBoundary,
)
from src.domain.memory.semantic_memory import (
    KnowledgeConcept,
    KnowledgeGraph,
    MasteryUpdate,
    MisconceptionRecord,
    PrerequisiteChain,
    SemanticMemory,
)

__all__ = [
    # Profile层
    "StudentCognitiveProfile",
    "ThinkingStyle",
    "ErrorDNA",
    "ZPDBoundary",
    "CognitiveFeatureVector",
    "ProfileMemory",
    
    # Episodic层
    "ProblemAttempt",
    "VariantLineage",
    "DecisionTrace",
    "EpisodeQuery",
    "EpisodicMemory",
    
    # Semantic层
    "KnowledgeConcept",
    "KnowledgeGraph",
    "MasteryUpdate",
    "MisconceptionRecord",
    "PrerequisiteChain",
    "SemanticMemory",
    
    # Meta层
    "PendingGap",
    "CrystallizedFeature",
    "CrystallizationResult",
    "MetaMemory",
    "CRYSTALLIZATION_PERIOD_HOURS",
    
    # 管理器
    "MemoryManager",
    "MemoryQuery",
    "MemorySnapshot",
    "CompressionResult",
]
