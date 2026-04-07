"""诊断流程引擎 - 90秒闭环诊断.

功能追溯ID: F-DIAG系列
主流程控制器，实现90秒闭环诊断流程：
[0s]  upload
[5s]  ocr_extract
[10s] problem_understand
[20s] model_arbitration (parallel)
[30s] error_detect + attribution
[35s] variant_generate (if needed)
[65s] variant_answer (30s timeout)
[80s] layered_diagnosis (2-3 steps)
[90s] result_assemble + memory_update
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from src.infrastructure.logging import get_logger
from src.infrastructure.models.base import ModelClient
from src.domain.models.diagnosis import DiagnosisResult, DiagnosisStatus, Problem
from src.domain.models.arbitration import ArbitrationResult, ModelResult
from src.domain.engines.ocr_engine import OCREngine, OCRResult
from src.domain.engines.arbitration_engine import ArbitrationEngine, ArbitrationConfig
from src.domain.engines.parallel_coordinator import ParallelCoordinator, CoordinatorConfig
from src.domain.engines.model_schedulers import (
    ModelAScheduler,
    ModelBScheduler,
    ModelCScheduler,
    ParsedProblem,
    SchedulerConfig,
)
from src.domain.engines.error_detection import ErrorDetectionEngine, ErrorDetectionResult
from src.domain.engines.error_attribution import ErrorAttributionEngine, ErrorAttributionResult
from src.domain.engines.explanation_generator import ExplanationGenerator, ExplanationResult
from src.domain.engines.layered_diagnosis import LayeredDiagnosisEngine, DiagnosisPath
from src.domain.engines.diagnosis_assembler import DiagnosisAssembler, DiagnosisReport
from src.domain.memory.memory_manager import MemoryManager
from src.domain.models.base import generate_id

logger = get_logger(__name__)


@dataclass
class DiagnosisConfig:
    """诊断配置.
    
    Attributes:
        total_timeout: 总超时时间(秒)
        ocr_timeout: OCR超时(秒)
        arbitration_timeout: 仲裁超时(秒)
        variant_timeout: 变形题等待超时(秒)
        enable_variant: 是否启用变形题
        enable_layered_diagnosis: 是否启用分层诊断
    """
    total_timeout: float = 90.0
    ocr_timeout: float = 8.0
    arbitration_timeout: float = 15.0
    variant_timeout: float = 30.0
    enable_variant: bool = True
    enable_layered_diagnosis: bool = True


@dataclass
class DiagnosisProgress:
    """诊断进度.
    
    Attributes:
        stage: 当前阶段
        progress_percent: 进度百分比
        elapsed_time: 已用时间
        status: 状态
        details: 详细信息
    """
    stage: str
    progress_percent: int
    elapsed_time: float
    status: str = "running"
    details: Dict[str, Any] = field(default_factory=dict)


class DiagnosisEngine:
    """诊断流程引擎.
    
    实现90秒闭环诊断流程：
    1. 作业照片上传 → OCR识别
    2. 题目理解 + 答案提取
    3. 3模型并行仲裁
    4. 错题识别 + 错误归因
    5. 变形题生成（如果需要）
    6. 分层选择诊断
    7. 诊断结果组装
    
    Example:
        >>> engine = DiagnosisEngine(
        ...     ocr_engine=ocr_engine,
        ...     arbitration_engine=arbitration_engine,
        ...     memory_manager=memory_manager,
        ... )
        >>> result = await engine.diagnose(
        ...     homework_image="/path/to/image.jpg",
        ...     student_id="stu_123",
        ... )
    """
    
    def __init__(
        self,
        ocr_engine: OCREngine,
        arbitration_engine: ArbitrationEngine,
        memory_manager: MemoryManager,
        model_a_scheduler: ModelAScheduler,
        model_b_scheduler: ModelBScheduler,
        model_c_scheduler: ModelCScheduler,
        config: Optional[DiagnosisConfig] = None,
    ):
        """初始化诊断引擎.
        
        Args:
            ocr_engine: OCR引擎
            arbitration_engine: 仲裁引擎
            memory_manager: 记忆管理器
            model_a_scheduler: 模型A调度器
            model_b_scheduler: 模型B调度器
            model_c_scheduler: 模型C调度器
            config: 诊断配置
        """
        self.ocr_engine = ocr_engine
        self.arbitration_engine = arbitration_engine
        self.memory_manager = memory_manager
        self.model_a_scheduler = model_a_scheduler
        self.model_b_scheduler = model_b_scheduler
        self.model_c_scheduler = model_c_scheduler
        self.config = config or DiagnosisConfig()
        
        # 初始化各子引擎
        self.error_detection = ErrorDetectionEngine()
        self.error_attribution = ErrorAttributionEngine(memory_manager)
        self.explanation_generator = ExplanationGenerator()
        self.layered_diagnosis = LayeredDiagnosisEngine(memory_manager)
        self.diagnosis_assembler = DiagnosisAssembler(memory_manager)
        
        # 并行协调器
        self.coordinator = ParallelCoordinator(
            CoordinatorConfig(timeout=self.config.arbitration_timeout)
        )
        
        self.logger = get_logger(__name__)
    
    async def diagnose(
        self,
        homework_image: str,
        student_id: str,
        subject_hint: Optional[str] = None,
        parent_description: Optional[str] = None,
    ) -> Tuple[DiagnosisResult, DiagnosisReport]:
        """执行90秒闭环诊断.
        
        Args:
            homework_image: 作业图片路径或base64
            student_id: 学生ID
            subject_hint: 学科提示（可选）
            parent_description: 家长描述（可选）
            
        Returns:
            (诊断结果, 诊断报告)
        """
        start_time = time.time()
        task_id = generate_id("task")
        
        self.logger.info(
            "diagnosis_start",
            task_id=task_id,
            student_id=student_id,
            image=homework_image[:50] if len(homework_image) > 50 else homework_image,
        )
        
        try:
            # 使用总超时控制
            async with asyncio.timeout(self.config.total_timeout):
                result, report = await self._execute_diagnosis_flow(
                    task_id=task_id,
                    student_id=student_id,
                    homework_image=homework_image,
                    subject_hint=subject_hint,
                    parent_description=parent_description,
                    start_time=start_time,
                )
                
                elapsed = time.time() - start_time
                self.logger.info(
                    "diagnosis_complete",
                    task_id=task_id,
                    elapsed_time=elapsed,
                    wrong_count=result.wrong_count,
                )
                
                return result, report
                
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            self.logger.error(
                "diagnosis_timeout",
                task_id=task_id,
                elapsed_time=elapsed,
                timeout=self.config.total_timeout,
            )
            return self._create_timeout_result(task_id, elapsed)
            
        except Exception as e:
            elapsed = time.time() - start_time
            self.logger.error(
                "diagnosis_failed",
                task_id=task_id,
                elapsed_time=elapsed,
                error=str(e),
            )
            return self._create_error_result(task_id, elapsed, str(e))
    
    async def _execute_diagnosis_flow(
        self,
        task_id: str,
        student_id: str,
        homework_image: str,
        subject_hint: Optional[str],
        parent_description: Optional[str],
        start_time: float,
    ) -> Tuple[DiagnosisResult, DiagnosisReport]:
        """执行诊断流程.
        
        [0s-5s] OCR识别
        [5s-10s] 题目理解
        [10s-25s] 3模型并行仲裁
        [25s-35s] 错题识别 + 归因分析
        [35s-65s] 变形题生成与作答（可选）
        [65s-80s] 启发式讲解生成
        [80s-90s] 分层诊断 + 结果组装
        
        Args:
            task_id: 任务ID
            student_id: 学生ID
            homework_image: 作业图片
            subject_hint: 学科提示
            parent_description: 家长描述
            start_time: 开始时间
            
        Returns:
            (诊断结果, 诊断报告)
        """
        # ========== [0s-5s] OCR识别 ==========
        ocr_result = await self._step_ocr(
            homework_image, subject_hint, start_time
        )
        
        # 构建题目对象
        problem = self._create_problem_from_ocr(ocr_result, task_id)
        problems = [problem]
        
        # ========== [5s-10s] 题目理解（在OCR中已完成） ==========
        self._log_progress("problem_understanding", 15, start_time)
        
        # ========== [10s-25s] 3模型并行仲裁 ==========
        parsed_problem = ocr_result.to_parsed_problem()
        arbitration_result = await self._step_arbitration(
            parsed_problem, homework_image, start_time
        )
        
        # ========== [25s-35s] 错题识别 + 归因分析 ==========
        detection_result = await self._step_error_detection(
            problem, arbitration_result, ocr_result, start_time
        )
        
        attribution_result = None
        if detection_result.is_wrong:
            attribution_result = await self._step_error_attribution(
                student_id, problem, detection_result, start_time
            )
        
        # ========== [35s-65s] 变形题生成（如果需要且配置启用） ==========
        variant_result = None
        if (self.config.enable_variant and 
            not arbitration_result.is_correct and
            self.arbitration_engine.should_trigger_variant(arbitration_result)):
            variant_result = await self._step_variant_generation(
                problem, arbitration_result, start_time
            )
        
        # ========== [65s-80s] 启发式讲解生成 ==========
        explanation_result = None
        if attribution_result:
            explanation_result = await self._step_explanation_generation(
                attribution_result, problem.content, start_time
            )
        
        # ========== [80s-90s] 分层诊断 + 结果组装 ==========
        # 模拟分层诊断过程（实际应该与用户交互）
        diagnosis_path = None
        if self.config.enable_layered_diagnosis and attribution_result:
            diagnosis_path = await self._step_layered_diagnosis(
                student_id, problem, attribution_result, start_time
            )
        
        # 组装最终结果
        processing_time = time.time() - start_time
        
        detection_results = [detection_result]
        attribution_results = [attribution_result] if attribution_result else []
        explanation_results = [explanation_result] if explanation_result else []
        diagnosis_paths = [diagnosis_path]
        
        result, report = await self.diagnosis_assembler.assemble(
            task_id=task_id,
            student_id=student_id,
            problems=problems,
            detection_results=detection_results,
            attribution_results=attribution_results,
            explanation_results=explanation_results,
            diagnosis_paths=diagnosis_paths,
            processing_time=processing_time,
            variant_results=[variant_result] if variant_result else None,
        )
        
        return result, report
    
    async def _step_ocr(
        self,
        homework_image: str,
        subject_hint: Optional[str],
        start_time: float,
    ) -> OCRResult:
        """执行OCR识别步骤.
        
        Args:
            homework_image: 作业图片
            subject_hint: 学科提示
            start_time: 开始时间
            
        Returns:
            OCR结果
        """
        self._log_progress("ocr_extract", 5, start_time)
        
        try:
            async with asyncio.timeout(self.config.ocr_timeout):
                ocr_result = await self.ocr_engine.recognize(
                    homework_image,
                    subject_hint=subject_hint,
                )
                
                if not ocr_result.success:
                    self.logger.warning("ocr_failed", error=ocr_result.error)
                    # 创建默认结果
                    return OCRResult(
                        success=True,
                        content="[无法识别题目内容]",
                        student_answer=None,
                        confidence=0.3,
                    )
                
                return ocr_result
                
        except asyncio.TimeoutError:
            self.logger.warning("ocr_timeout")
            return OCRResult(
                success=True,
                content="[OCR超时，使用备用识别]",
                student_answer=None,
                confidence=0.3,
            )
    
    async def _step_arbitration(
        self,
        parsed_problem: ParsedProblem,
        homework_image: str,
        start_time: float,
    ) -> ArbitrationResult:
        """执行仲裁步骤.
        
        Args:
            parsed_problem: 解析后的题目
            homework_image: 作业图片
            start_time: 开始时间
            
        Returns:
            仲裁结果
        """
        self._log_progress("model_arbitration", 25, start_time)
        
        # 并行调度三个模型
        schedulers = [
            self.model_a_scheduler,
            self.model_b_scheduler,
            self.model_c_scheduler,
        ]
        
        # 读取图片
        try:
            import base64
            with open(homework_image, "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode("utf-8")
            images = [image_base64]
        except Exception:
            images = None
        
        task_results = await self.coordinator.execute_parallel(
            schedulers=schedulers,
            problem=parsed_problem,
            images=images,
        )
        
        # 获取成功的结果
        model_results = self.coordinator.get_successful_results(task_results)
        
        if not model_results:
            self.logger.error("all_models_failed")
            # 返回默认仲裁结果
            return ArbitrationResult(
                problem_id="unknown",
                is_correct=True,
                confidence=0.5,
                is_consensus=False,
                consensus_ratio=0.0,
                used_models=[],
            )
        
        # 执行仲裁
        arbitration_result = self.arbitration_engine.arbitrate(
            problem_id=parsed_problem.content[:50],  # 使用内容前50字符作为ID
            model_results=model_results,
        )
        
        return arbitration_result
    
    async def _step_error_detection(
        self,
        problem: Problem,
        arbitration_result: ArbitrationResult,
        ocr_result: OCRResult,
        start_time: float,
    ) -> ErrorDetectionResult:
        """执行错题识别步骤.
        
        Args:
            problem: 题目
            arbitration_result: 仲裁结果
            ocr_result: OCR结果
            start_time: 开始时间
            
        Returns:
            错题识别结果
        """
        self._log_progress("error_detection", 35, start_time)
        
        detection_result = await self.error_detection.detect(
            problem=problem,
            arbitration_result=arbitration_result,
            ocr_result=ocr_result.__dict__ if ocr_result else None,
        )
        
        return detection_result
    
    async def _step_error_attribution(
        self,
        student_id: str,
        problem: Problem,
        detection_result: ErrorDetectionResult,
        start_time: float,
    ) -> ErrorAttributionResult:
        """执行错误归因步骤.
        
        Args:
            student_id: 学生ID
            problem: 题目
            detection_result: 错题识别结果
            start_time: 开始时间
            
        Returns:
            归因结果
        """
        self._log_progress("error_attribution", 45, start_time)
        
        attribution_result = await self.error_attribution.analyze(
            student_id=student_id,
            problem_id=problem.id,
            error_type=detection_result.error_type or detection_result.error_type,
            concept_ids=problem.knowledge_points,
            student_answer=detection_result.student_answer,
            correct_answer=detection_result.correct_answer,
        )
        
        return attribution_result
    
    async def _step_variant_generation(
        self,
        problem: Problem,
        arbitration_result: ArbitrationResult,
        start_time: float,
    ) -> Optional[Dict[str, Any]]:
        """执行变形题生成步骤.
        
        Args:
            problem: 题目
            arbitration_result: 仲裁结果
            start_time: 开始时间
            
        Returns:
            变形题结果或None
        """
        self._log_progress("variant_generation", 50, start_time)
        
        # 这里简化实现，实际应该调用变形题生成模块
        # 模拟变形题生成和等待作答的过程
        
        variant = {
            "variant_id": generate_id("var"),
            "original_problem_id": problem.id,
            "variant_type": "numerical",
            "content": f"[变形题] {problem.content[:50]}...",
            "answer": "[变形题答案]",
            "status": "generated",
        }
        
        # 模拟变形题作答超时等待
        # 实际应该推送给学生作答
        self.logger.info("variant_generated", variant_id=variant["variant_id"])
        
        return variant
    
    async def _step_explanation_generation(
        self,
        attribution_result: ErrorAttributionResult,
        problem_content: str,
        start_time: float,
    ) -> ExplanationResult:
        """执行讲解生成步骤.
        
        Args:
            attribution_result: 归因结果
            problem_content: 题目内容
            start_time: 开始时间
            
        Returns:
            讲解结果
        """
        self._log_progress("explanation_generation", 75, start_time)
        
        explanation_result = await self.explanation_generator.generate(
            attribution_result=attribution_result,
            problem_content=problem_content,
        )
        
        return explanation_result
    
    async def _step_layered_diagnosis(
        self,
        student_id: str,
        problem: Problem,
        attribution_result: ErrorAttributionResult,
        start_time: float,
    ) -> DiagnosisPath:
        """执行分层诊断步骤.
        
        模拟分层诊断过程，实际应该与用户交互。
        
        Args:
            student_id: 学生ID
            problem: 题目
            attribution_result: 归因结果
            start_time: 开始时间
            
        Returns:
            诊断路径
        """
        self._log_progress("layered_diagnosis", 85, start_time)
        
        # 开始诊断路径
        path = self.layered_diagnosis.start_diagnosis_path(
            student_id=student_id,
            problem_id=problem.id,
        )
        
        # 生成第一层选项（模拟自动选择最可能的）
        first_options = await self.layered_diagnosis.generate_first_layer(
            attribution_result
        )
        
        if first_options:
            # 模拟选择置信度最高的
            selected = first_options[0]
            self.layered_diagnosis.record_first_selection(
                path_id=path.path_id,
                option_id=selected.option_id,
                option_type=selected.type.value,
            )
            
            # 生成第二层选项
            second_options = await self.layered_diagnosis.generate_second_layer(
                student_id=student_id,
                problem_id=problem.id,
                first_selection=selected.option_id,
                attribution_result=attribution_result,
                first_layer_options=first_options,
            )
            
            if second_options:
                # 模拟选择
                selected_second = second_options[0]
                final_diagnosis = f"{selected.title} - {selected_second.title}"
                self.layered_diagnosis.record_second_selection(
                    path_id=path.path_id,
                    option_id=selected_second.option_id,
                    option_type=selected_second.type.value,
                    final_diagnosis=final_diagnosis,
                )
        
        return path
    
    def _create_problem_from_ocr(
        self,
        ocr_result: OCRResult,
        task_id: str,
    ) -> Problem:
        """从OCR结果创建题目对象.
        
        Args:
            ocr_result: OCR结果
            task_id: 任务ID
            
        Returns:
            题目对象
        """
        return Problem(
            id=generate_id("prob"),
            content=ocr_result.content or "[未识别内容]",
            subject=ocr_result.subject or "math",
            difficulty=5,  # 默认中等难度
            answer=None,  # 需要从外部获取
            solution_steps=[],
            knowledge_points=ocr_result.knowledge_points[:3],
        )
    
    def _log_progress(
        self,
        stage: str,
        progress_percent: int,
        start_time: float,
    ) -> None:
        """记录进度.
        
        Args:
            stage: 当前阶段
            progress_percent: 进度百分比
            start_time: 开始时间
        """
        elapsed = time.time() - start_time
        self.logger.info(
            "diagnosis_progress",
            stage=stage,
            progress=progress_percent,
            elapsed_time=round(elapsed, 2),
        )
    
    def _create_timeout_result(
        self,
        task_id: str,
        elapsed: float,
    ) -> Tuple[DiagnosisResult, DiagnosisReport]:
        """创建超时结果.
        
        Args:
            task_id: 任务ID
            elapsed: 已用时间
            
        Returns:
            超时结果
        """
        from datetime import datetime
        
        result = DiagnosisResult(
            task_id=task_id,
            status=DiagnosisStatus.TIMEOUT,
            original_problems=[],
            wrong_problems=[],
            processing_time=elapsed,
            error={"type": "timeout", "message": f"诊断超时（>{self.config.total_timeout}s）"},
            created_at=datetime.utcnow(),
        )
        
        report = DiagnosisReport(
            report_id=generate_id("report"),
            task_id=task_id,
            student_id="unknown",
            created_at=result.created_at,
            diagnosis_summary={"status": "timeout", "elapsed_time": elapsed},
        )
        
        return result, report
    
    def _create_error_result(
        self,
        task_id: str,
        elapsed: float,
        error_message: str,
    ) -> Tuple[DiagnosisResult, DiagnosisReport]:
        """创建错误结果.
        
        Args:
            task_id: 任务ID
            elapsed: 已用时间
            error_message: 错误信息
            
        Returns:
            错误结果
        """
        from datetime import datetime
        
        result = DiagnosisResult(
            task_id=task_id,
            status=DiagnosisStatus.FAILED,
            original_problems=[],
            wrong_problems=[],
            processing_time=elapsed,
            error={"type": "exception", "message": error_message},
            created_at=datetime.utcnow(),
        )
        
        report = DiagnosisReport(
            report_id=generate_id("report"),
            task_id=task_id,
            student_id="unknown",
            created_at=result.created_at,
            diagnosis_summary={
                "status": "failed",
                "elapsed_time": elapsed,
                "error": error_message,
            },
        )
        
        return result, report
    
    async def diagnose_with_progress(
        self,
        homework_image: str,
        student_id: str,
        subject_hint: Optional[str] = None,
        progress_callback: Optional[Any] = None,
    ) -> Tuple[DiagnosisResult, DiagnosisReport]:
        """执行诊断并报告进度.
        
        Args:
            homework_image: 作业图片
            student_id: 学生ID
            subject_hint: 学科提示
            progress_callback: 进度回调函数
            
        Returns:
            (诊断结果, 诊断报告)
        """
        # 这里可以实现更细粒度的进度报告
        # 通过回调函数或生成器模式
        return await self.diagnose(homework_image, student_id, subject_hint)
