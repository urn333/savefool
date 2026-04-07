"""诊断引擎模块.

提供完整的诊断流程引擎，包括：
- 三模型仲裁核心功能
- 错题识别与归因
- 启发式讲解生成
- 分层诊断
- 90秒闭环诊断流程
"""

# OCR引擎
from src.domain.engines.ocr_engine import (
    OCREngine,
    OCRResult,
    OCROptions,
    SubjectType,
    ProblemType,
)

# 模型调度与仲裁
from src.domain.engines.model_schedulers import (
    ModelAScheduler,
    ModelBScheduler,
    ModelCScheduler,
    SchedulerConfig,
    ParsedProblem,
    BaseModelScheduler,
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

# 诊断流程组件
from src.domain.engines.error_detection import (
    ErrorDetectionEngine,
    ErrorDetectionResult,
    ErrorLocation,
)
from src.domain.engines.error_attribution import (
    ErrorAttributionEngine,
    ErrorAttributionResult,
    AttributionFactor,
)
from src.domain.engines.explanation_generator import (
    ExplanationGenerator,
    ExplanationResult,
    ExplanationContent,
)
from src.domain.engines.layered_diagnosis import (
    LayeredDiagnosisEngine,
    LayerOption,
    LayerOptionType,
    DiagnosisPath,
)
from src.domain.engines.diagnosis_assembler import (
    DiagnosisAssembler,
    DiagnosisReport,
)
from src.domain.engines.diagnosis_engine import (
    DiagnosisEngine,
    DiagnosisConfig,
    DiagnosisProgress,
)

__all__ = [
    # OCR引擎
    "OCREngine",
    "OCRResult",
    "OCROptions",
    "SubjectType",
    "ProblemType",
    # 模型调度器
    "ModelAScheduler",
    "ModelBScheduler",
    "ModelCScheduler",
    "BaseModelScheduler",
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
    # 错题识别
    "ErrorDetectionEngine",
    "ErrorDetectionResult",
    "ErrorLocation",
    # 错误归因
    "ErrorAttributionEngine",
    "ErrorAttributionResult",
    "AttributionFactor",
    # 讲解生成
    "ExplanationGenerator",
    "ExplanationResult",
    "ExplanationContent",
    # 分层诊断
    "LayeredDiagnosisEngine",
    "LayerOption",
    "LayerOptionType",
    "DiagnosisPath",
    # 诊断组装
    "DiagnosisAssembler",
    "DiagnosisReport",
    # 主诊断引擎
    "DiagnosisEngine",
    "DiagnosisConfig",
    "DiagnosisStage",
    "DiagnosisStageResult",
    "DetectedError",
    "ErrorLocation",
    "AttributionResult",
    "Explanation",
    "LayeredOption",
    "DiagnosisPath",
]
