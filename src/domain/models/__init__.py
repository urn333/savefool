"""领域模型模块.

定义AI助教系统的核心业务模型，包括诊断、仲裁、变形题和记忆数据。
"""

from src.domain.models.diagnosis import (
    DiagnosisResult,
    DiagnosisStatus,
    ErrorType,
    Problem,
    ProblemDiagnosis,
    RootCause,
    WrongProblem,
)
from src.domain.models.arbitration import (
    ArbitrationResult,
    ModelResult,
    ModelVote,
)
from src.domain.models.variant import (
    GenerationStrategy,
    VariantProblem,
)
from src.domain.models.memory import (
    CognitiveLevel,
    CompetencyMatrix,
    ConceptMastery,
    ConceptStrength,
    LearningEpisode,
    LearningEventType,
    LearningStyle,
    SemanticKnowledge,
    StudentProfile,
    WeakPoint,
)

__all__ = [
    # 诊断相关
    "DiagnosisResult",
    "DiagnosisStatus",
    "ErrorType",
    "Problem",
    "ProblemDiagnosis",
    "RootCause",
    "WrongProblem",
    # 仲裁相关
    "ArbitrationResult",
    "ModelResult",
    "ModelVote",
    # 变形题相关
    "GenerationStrategy",
    "VariantProblem",
    # 记忆系统相关
    "CognitiveLevel",
    "CompetencyMatrix",
    "ConceptMastery",
    "ConceptStrength",
    "LearningEpisode",
    "LearningEventType",
    "LearningStyle",
    "SemanticKnowledge",
    "StudentProfile",
    "WeakPoint",
]
