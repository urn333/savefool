"""变形题生成引擎.

即时变形题生成主控制器，5秒内生成变形题并返回可信度评分。
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type

from src.domain.engines.variant_credibility import (
    CredibilityEvaluator,
    CredibilityHistory,
    CredibilityRating,
)
from src.domain.engines.variant_strategies import (
    ContextTransferStrategy,
    InverseOperationStrategy,
    NumericVariationStrategy,
    StrategyContext,
    StrategyResult,
    VariantStrategy,
)
from src.domain.engines.variant_validator import VariantValidator, ValidationResult
from src.domain.models.diagnosis import ErrorType, Problem
from src.domain.models.variant import (
    GenerationStrategy,
    VariantGenerationResult,
    VariantProblem,
)
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass
class GenerationConfig:
    """生成配置.
    
    Attributes:
        timeout_seconds: 生成超时时间(秒)
        max_retries: 最大重试次数
        fallback_to_preset: 失败时是否使用预生成题库
        preset_count: 预生成题库数量
        enable_credibility_rating: 是否启用可信度评分
        enable_validation: 是否启用验证
    """
    
    timeout_seconds: float = 5.0
    max_retries: int = 2
    fallback_to_preset: bool = True
    preset_count: int = 10
    enable_credibility_rating: bool = True
    enable_validation: bool = True


@dataclass
class VariantGenerationOutput:
    """变形题生成输出.
    
    包含生成的变形题及完整评估信息。
    
    Attributes:
        variant: 变形题
        credibility: 可信度评分
        validation: 验证结果
        generation_time: 生成耗时(秒)
        strategy_used: 使用的策略
        is_fallback: 是否为预生成题库
    """
    
    variant: Optional[VariantProblem]
    credibility: Optional[CredibilityRating]
    validation: Optional[ValidationResult]
    generation_time: float
    strategy_used: str
    is_fallback: bool
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "variant": self.variant.to_dict() if self.variant else None,
            "credibility": self.credibility.to_dict() if self.credibility else None,
            "validation": self.validation.to_dict() if self.validation else None,
            "generation_time": self.generation_time,
            "strategy_used": self.strategy_used,
            "is_fallback": self.is_fallback,
            "metadata": self.metadata,
        }


class VariantGenerator:
    """变形题生成引擎.
    
    主控制器，负责：
    - 根据错误类型选择策略
    - 5秒内生成变形题
    - 可信度评分(AI自动)
    - 验证和筛选
    - 失败时fallback到预生成题库
    
    时序要求：
    原题识别完成
      ↓ [0s]
    选择变形策略(基于错误类型)
      ↓ [2s]
    生成变形题
      ↓ [4s]
    可信度评分(AI自动)
      ↓ [5s]
    推送给学生(限时30秒作答)
    """
    
    # 错误类型到策略的优先级映射
    STRATEGY_PRIORITY: Dict[ErrorType, List[Type[VariantStrategy]]] = {
        ErrorType.CALCULATION_ERROR: [
            NumericVariationStrategy,
            InverseOperationStrategy,
            ContextTransferStrategy,
        ],
        ErrorType.CARELESS_MISTAKE: [
            ContextTransferStrategy,
            NumericVariationStrategy,
            InverseOperationStrategy,
        ],
        ErrorType.LOGICAL_FLAW: [
            InverseOperationStrategy,
            NumericVariationStrategy,
            ContextTransferStrategy,
        ],
        ErrorType.CONCEPT_MISUNDERSTANDING: [
            ContextTransferStrategy,
            InverseOperationStrategy,
            NumericVariationStrategy,
        ],
        ErrorType.KNOWLEDGE_GAP: [
            NumericVariationStrategy,
            ContextTransferStrategy,
            InverseOperationStrategy,
        ],
    }
    
    def __init__(
        self,
        model_client: Optional[Any] = None,
        config: Optional[GenerationConfig] = None,
    ):
        """初始化生成引擎.
        
        Args:
            model_client: 可选的模型客户端
            config: 生成配置
        """
        self.model_client = model_client
        self.config = config or GenerationConfig()
        
        # 初始化策略
        self._strategies: Dict[Type[VariantStrategy], VariantStrategy] = {
            NumericVariationStrategy: NumericVariationStrategy(model_client),
            InverseOperationStrategy: InverseOperationStrategy(model_client),
            ContextTransferStrategy: ContextTransferStrategy(model_client),
        }
        
        # 初始化验证器
        self._validator = VariantValidator()
        
        # 初始化可信度评估器
        self._credibility_evaluator = CredibilityEvaluator(model_client)
        
        # 初始化历史记录
        self._credibility_history = CredibilityHistory()
        
        # 预生成题库(简单示例)
        self._preset_variants: Dict[str, List[Dict[str, Any]]] = {}
    
    async def generate(
        self,
        original_problem: Problem,
        error_type: ErrorType,
        student_level: float,
    ) -> VariantGenerationOutput:
        """生成变形题.
        
        主入口方法，5秒内完成生成和评分。
        
        Args:
            original_problem: 原题
            error_type: 错误类型
            student_level: 学生水平(0-1)
            
        Returns:
            生成输出
        """
        start_time = time.time()
        
        logger.info(
            "variant_generation_start",
            problem_id=original_problem.id,
            error_type=error_type.value,
            student_level=student_level,
        )
        
        try:
            # 使用超时控制
            output = await asyncio.wait_for(
                self._generate_with_timeout(
                    original_problem, error_type, student_level
                ),
                timeout=self.config.timeout_seconds,
            )
            
            elapsed = time.time() - start_time
            logger.info(
                "variant_generation_success",
                problem_id=original_problem.id,
                elapsed=elapsed,
                strategy=output.strategy_used,
                credibility_stars=output.credibility.stars if output.credibility else None,
            )
            
            return output
            
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            logger.warning(
                "variant_generation_timeout",
                problem_id=original_problem.id,
                elapsed=elapsed,
                timeout=self.config.timeout_seconds,
            )
            
            # 超时处理：使用预生成题库
            if self.config.fallback_to_preset:
                return await self._fallback_to_preset(
                    original_problem, error_type, student_level, elapsed
                )
            else:
                return VariantGenerationOutput(
                    variant=None,
                    credibility=None,
                    validation=None,
                    generation_time=elapsed,
                    strategy_used="timeout",
                    is_fallback=False,
                    metadata={"error": "Generation timeout"},
                )
        
        except Exception as e:
            elapsed = time.time() - start_time
            logger.exception(
                "variant_generation_error",
                problem_id=original_problem.id,
                elapsed=elapsed,
                error=str(e),
            )
            
            # 错误处理：使用预生成题库
            if self.config.fallback_to_preset:
                return await self._fallback_to_preset(
                    original_problem, error_type, student_level, elapsed
                )
            else:
                return VariantGenerationOutput(
                    variant=None,
                    credibility=None,
                    validation=None,
                    generation_time=elapsed,
                    strategy_used="error",
                    is_fallback=False,
                    metadata={"error": str(e)},
                )
    
    async def _generate_with_timeout(
        self,
        original_problem: Problem,
        error_type: ErrorType,
        student_level: float,
    ) -> VariantGenerationOutput:
        """带超时的生成逻辑.
        
        Args:
            original_problem: 原题
            error_type: 错误类型
            student_level: 学生水平
            
        Returns:
            生成输出
        """
        start_time = time.time()
        
        # 1. 选择策略
        strategies = self._select_strategies(error_type, original_problem)
        
        # 2. 准备上下文
        target_difficulty = self._calculate_target_difficulty(
            original_problem.difficulty,
            student_level,
            error_type,
        )
        
        context = StrategyContext(
            original_problem=original_problem,
            error_type=error_type,
            student_level=student_level,
            target_difficulty=target_difficulty,
        )
        
        # 3. 尝试各策略生成
        best_result: Optional[StrategyResult] = None
        best_strategy: Optional[str] = None
        
        for strategy_class in strategies:
            strategy = self._strategies[strategy_class]
            
            # 检查策略适用性
            if not strategy.can_apply(original_problem, error_type):
                continue
            
            # 尝试生成
            for attempt in range(self.config.max_retries + 1):
                result = await strategy.generate(context)
                
                if result.success and result.variant:
                    # 快速验证
                    if self._validator.quick_validate(result.variant):
                        if (best_result is None or 
                            strategy.get_confidence_score(context) > 
                            self._strategies[best_strategy].get_confidence_score(context) if best_strategy else 0):
                            best_result = result
                            best_strategy = strategy_class.__name__
                        break
                
                if attempt < self.config.max_retries:
                    await asyncio.sleep(0.1)  # 短暂延迟后重试
        
        # 4. 处理生成结果
        if not best_result or not best_result.variant:
            # 所有策略都失败，使用预生成题库
            elapsed = time.time() - start_time
            return await self._fallback_to_preset(
                original_problem, error_type, student_level, elapsed
            )
        
        variant = best_result.variant
        
        # 5. 完整验证
        validation = None
        if self.config.enable_validation:
            validation = await self._validator.validate(
                variant, original_problem, student_level
            )
            
            # 如果验证不通过，尝试使用预生成题库
            if not validation.is_valid and self.config.fallback_to_preset:
                elapsed = time.time() - start_time
                return await self._fallback_to_preset(
                    original_problem, error_type, student_level, elapsed
                )
        
        # 6. 可信度评分
        credibility = None
        if self.config.enable_credibility_rating:
            credibility = await self._credibility_evaluator.evaluate(
                variant, original_problem, student_level, target_difficulty
            )
            
            # 记录到历史
            self._credibility_history.add_record(
                variant_id=variant.id,
                ai_rating=credibility,
            )
        
        elapsed = time.time() - start_time
        
        return VariantGenerationOutput(
            variant=variant,
            credibility=credibility,
            validation=validation,
            generation_time=elapsed,
            strategy_used=best_strategy or "unknown",
            is_fallback=False,
            metadata={
                "strategy_result": best_result.metadata if best_result else None,
                "target_difficulty": target_difficulty,
            },
        )
    
    def _select_strategies(
        self,
        error_type: ErrorType,
        problem: Problem,
    ) -> List[Type[VariantStrategy]]:
        """选择适用的策略.
        
        Args:
            error_type: 错误类型
            problem: 原题
            
        Returns:
            策略类列表
        """
        # 获取该错误类型的策略优先级
        strategies = self.STRATEGY_PRIORITY.get(
            error_type,
            [NumericVariationStrategy, ContextTransferStrategy, InverseOperationStrategy]
        )
        
        # 过滤不适用的策略
        applicable = [
            s for s in strategies
            if self._strategies[s].can_apply(problem, error_type)
        ]
        
        # 如果没有适用的，返回所有策略
        if not applicable:
            return list(self._strategies.keys())
        
        return applicable
    
    def _calculate_target_difficulty(
        self,
        original_difficulty: int,
        student_level: float,
        error_type: ErrorType,
    ) -> int:
        """计算目标难度.
        
        Args:
            original_difficulty: 原题难度
            student_level: 学生水平
            error_type: 错误类型
            
        Returns:
            目标难度
        """
        # 基础调整
        level_adjustment = (0.5 - student_level) * 2  # -1 到 +1
        
        # 错误类型调整
        error_adjustments = {
            ErrorType.CALCULATION_ERROR: 0,
            ErrorType.CARELESS_MISTAKE: 0,
            ErrorType.LOGICAL_FLAW: 1,
            ErrorType.CONCEPT_MISUNDERSTANDING: -1,
            ErrorType.KNOWLEDGE_GAP: -2,
        }
        error_adjustment = error_adjustments.get(error_type, 0)
        
        target = original_difficulty + level_adjustment + error_adjustment
        
        return max(1, min(10, int(round(target))))
    
    async def _fallback_to_preset(
        self,
        original_problem: Problem,
        error_type: ErrorType,
        student_level: float,
        elapsed_time: float,
    ) -> VariantGenerationOutput:
        """使用预生成题库.
        
        Args:
            original_problem: 原题
            error_type: 错误类型
            student_level: 学生水平
            elapsed_time: 已耗时间
            
        Returns:
            生成输出
        """
        logger.info(
            "using_preset_variants",
            problem_id=original_problem.id,
            error_type=error_type.value,
        )
        
        # 从预生成题库中选择最合适的
        preset_key = f"{error_type.value}_{original_problem.subject}"
        presets = self._preset_variants.get(preset_key, [])
        
        if not presets:
            # 如果没有特定预设，使用通用预设
            preset_key = f"general_{original_problem.subject}"
            presets = self._preset_variants.get(preset_key, [])
        
        if presets:
            # 选择难度最接近的
            target_difficulty = self._calculate_target_difficulty(
                original_problem.difficulty, student_level, error_type
            )
            
            best_preset = min(
                presets,
                key=lambda p: abs(p.get("difficulty", 5) - target_difficulty)
            )
            
            # 创建变形题对象
            variant = VariantProblem(
                original_problem_id=original_problem.id,
                content=best_preset.get("content", "变形题"),
                difficulty=best_preset.get("difficulty", original_problem.difficulty),
                target_concept=original_problem.knowledge_points[0] if original_problem.knowledge_points else "general",
                error_type=error_type,
                strategy=GenerationStrategy.VALUE_SUBSTITUTION,
                answer=best_preset.get("answer"),
                solution=best_preset.get("solution"),
                metadata={
                    "source": "preset_bank",
                    "preset_key": preset_key,
                },
            )
            
            # 可信度评分
            credibility = None
            if self.config.enable_credibility_rating:
                credibility = await self._credibility_evaluator.evaluate(
                    variant, original_problem, student_level, target_difficulty
                )
            
            return VariantGenerationOutput(
                variant=variant,
                credibility=credibility,
                validation=None,
                generation_time=elapsed_time,
                strategy_used="preset_bank",
                is_fallback=True,
                metadata={"preset_key": preset_key},
            )
        
        # 连预设都没有，返回失败
        return VariantGenerationOutput(
            variant=None,
            credibility=None,
            validation=None,
            generation_time=elapsed_time,
            strategy_used="fallback_failed",
            is_fallback=True,
            metadata={"error": "No preset variants available"},
        )
    
    async def generate_batch(
        self,
        original_problem: Problem,
        error_type: ErrorType,
        student_level: float,
        count: int = 3,
    ) -> VariantGenerationResult:
        """批量生成变形题.
        
        Args:
            original_problem: 原题
            error_type: 错误类型
            student_level: 学生水平
            count: 生成数量
            
        Returns:
            批量生成结果
        """
        variants = []
        metadata = {
            "requested_count": count,
            "successful_count": 0,
            "fallback_count": 0,
        }
        
        for i in range(count):
            output = await self.generate(
                original_problem, error_type, student_level
            )
            
            if output.variant:
                variants.append(output.variant)
                metadata["successful_count"] += 1
                if output.is_fallback:
                    metadata["fallback_count"] += 1
        
        return VariantGenerationResult(
            variants=variants,
            metadata=metadata,
        )
    
    def add_preset_variants(
        self,
        error_type: ErrorType,
        subject: str,
        variants: List[Dict[str, Any]],
    ) -> None:
        """添加预生成变形题.
        
        Args:
            error_type: 错误类型
            subject: 学科
            variants: 变形题列表
        """
        key = f"{error_type.value}_{subject}"
        self._preset_variants[key] = variants
    
    def get_credibility_history(self) -> CredibilityHistory:
        """获取可信度历史记录.
        
        Returns:
            历史记录对象
        """
        return self._credibility_history
    
    def get_calibration_report(self) -> Dict[str, Any]:
        """获取校准报告.
        
        Returns:
            校准报告
        """
        return self._credibility_history.get_calibration_data()
