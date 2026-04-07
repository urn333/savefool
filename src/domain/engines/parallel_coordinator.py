"""并行任务协调器.

负责并行调度多个模型，管理超时和错误处理。
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

from src.infrastructure.logging import get_logger
from src.domain.engines.model_schedulers import (
    BaseModelScheduler,
    ModelAScheduler,
    ModelBScheduler,
    ModelCScheduler,
    ParsedProblem,
)
from src.domain.models.arbitration import ModelResult

logger = get_logger(__name__)


@dataclass
class CoordinatorConfig:
    """协调器配置.
    
    Attributes:
        timeout: 单个模型超时时间(秒)
        max_concurrent: 最大并发数
        continue_on_error: 是否在一个失败时继续其他
    """
    timeout: float = 10.0
    max_concurrent: int = 3
    continue_on_error: bool = True


@dataclass
class ModelTaskResult:
    """模型任务结果.
    
    Attributes:
        model_id: 模型标识
        success: 是否成功
        result: 成功时的结果
        error: 失败时的错误信息
        latency_ms: 延迟(毫秒)
    """
    model_id: str
    success: bool
    result: Optional[ModelResult] = None
    error: Optional[str] = None
    latency_ms: float = 0.0


class ParallelCoordinator:
    """并行任务协调器.
    
    并行调用多个模型调度器，管理超时和错误处理。
    
    Example:
        >>> coordinator = ParallelCoordinator(config)
        >>> results = await coordinator.execute_parallel(
        ...     schedulers=[scheduler_a, scheduler_b, scheduler_c],
        ...     problem=parsed_problem,
        ...     images=[image_base64],
        ... )
    """
    
    def __init__(self, config: Optional[CoordinatorConfig] = None):
        """初始化协调器.
        
        Args:
            config: 协调器配置
        """
        self.config = config or CoordinatorConfig()
        self.logger = get_logger(__name__)
    
    async def execute_parallel(
        self,
        schedulers: List[BaseModelScheduler],
        problem: ParsedProblem,
        images: Optional[List[str]] = None,
    ) -> Dict[str, ModelTaskResult]:
        """并行执行多个模型调度器.
        
        Args:
            schedulers: 模型调度器列表
            problem: 解析后的题目
            images: 图片列表(base64)
            
        Returns:
            模型ID到任务结果的映射
        """
        self.logger.info(
            "parallel_execution_start",
            scheduler_count=len(schedulers),
            timeout=self.config.timeout,
        )
        
        # 创建任务
        tasks = []
        for scheduler in schedulers:
            task = self._execute_with_timeout(scheduler, problem, images)
            tasks.append(task)
        
        # 并行执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        task_results: Dict[str, ModelTaskResult] = {}
        for scheduler, result in zip(schedulers, results):
            model_id = scheduler.config.model_id
            
            if isinstance(result, Exception):
                task_results[model_id] = ModelTaskResult(
                    model_id=model_id,
                    success=False,
                    error=str(result),
                )
                self.logger.warning(
                    "model_execution_failed",
                    model_id=model_id,
                    error=str(result),
                )
            else:
                task_results[model_id] = result
                status = "success" if result.success else "failed"
                self.logger.info(
                    f"model_execution_{status}",
                    model_id=model_id,
                    latency_ms=result.latency_ms,
                )
        
        # 统计
        success_count = sum(1 for r in task_results.values() if r.success)
        self.logger.info(
            "parallel_execution_complete",
            total=len(schedulers),
            success=success_count,
            failed=len(schedulers) - success_count,
        )
        
        return task_results
    
    async def _execute_with_timeout(
        self,
        scheduler: BaseModelScheduler,
        problem: ParsedProblem,
        images: Optional[List[str]],
    ) -> ModelTaskResult:
        """带超时的执行单个调度器.
        
        Args:
            scheduler: 模型调度器
            problem: 解析后的题目
            images: 图片列表
            
        Returns:
            任务结果
        """
        model_id = scheduler.config.model_id
        
        try:
            # 使用asyncio.wait_for实现超时
            result = await asyncio.wait_for(
                scheduler.schedule(problem, images),
                timeout=self.config.timeout,
            )
            
            return ModelTaskResult(
                model_id=model_id,
                success=True,
                result=result,
                latency_ms=result.latency_ms,
            )
            
        except asyncio.TimeoutError:
            error_msg = f"Model {model_id} execution timeout after {self.config.timeout}s"
            self.logger.warning("model_timeout", model_id=model_id, timeout=self.config.timeout)
            return ModelTaskResult(
                model_id=model_id,
                success=False,
                error=error_msg,
                latency_ms=self.config.timeout * 1000,
            )
            
        except Exception as e:
            error_msg = f"Model {model_id} execution failed: {str(e)}"
            self.logger.error("model_error", model_id=model_id, error=str(e))
            return ModelTaskResult(
                model_id=model_id,
                success=False,
                error=error_msg,
            )
    
    async def execute_with_fallback(
        self,
        schedulers: List[BaseModelScheduler],
        problem: ParsedProblem,
        images: Optional[List[str]] = None,
        min_success: int = 2,
    ) -> Dict[str, ModelTaskResult]:
        """执行并确保最少成功数.
        
        如果成功数不足，会尝试使用备用策略。
        
        Args:
            schedulers: 模型调度器列表
            problem: 解析后的题目
            images: 图片列表
            min_success: 最少需要成功的模型数
            
        Returns:
            模型ID到任务结果的映射
        """
        results = await self.execute_parallel(schedulers, problem, images)
        
        success_count = sum(1 for r in results.values() if r.success)
        
        if success_count < min_success:
            self.logger.warning(
                "insufficient_successful_models",
                success_count=success_count,
                min_required=min_success,
            )
            # 这里可以实现更复杂的备用策略
            # 比如增加超时重试、使用缓存结果等
        
        return results
    
    def get_successful_results(
        self,
        task_results: Dict[str, ModelTaskResult],
    ) -> List[ModelResult]:
        """获取成功的模型结果.
        
        Args:
            task_results: 任务结果映射
            
        Returns:
            成功的模型结果列表
        """
        return [
            r.result for r in task_results.values()
            if r.success and r.result is not None
        ]
    
    def get_failed_models(
        self,
        task_results: Dict[str, ModelTaskResult],
    ) -> List[str]:
        """获取失败的模型ID列表.
        
        Args:
            task_results: 任务结果映射
            
        Returns:
            失败的模型ID列表
        """
        return [
            r.model_id for r in task_results.values()
            if not r.success
        ]
