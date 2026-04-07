"""变形题相关领域模型.

定义变形题生成策略和变形题核心业务模型。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from src.domain.models.base import DomainModel, generate_id, now_timestamp
from src.domain.models.diagnosis import ErrorType


class GenerationStrategy(str, Enum):
    """变形题生成策略枚举.

    根据错误类型选择不同的生成策略。
    """

    VALUE_SUBSTITUTION = "value_substitution"
    CONTEXT_CHANGE = "context_change"
    CONDITION_MODIFY = "condition_modify"
    REVERSE_CONSTRUCT = "reverse_construct"
    COMPREHENSIVE = "comprehensive"


# 错误类型到生成策略的映射
STRATEGY_MAPPING: Dict[ErrorType, List[GenerationStrategy]] = {
    ErrorType.CONCEPT_MISUNDERSTANDING: [
        GenerationStrategy.CONTEXT_CHANGE,
        GenerationStrategy.CONDITION_MODIFY,
    ],
    ErrorType.CALCULATION_ERROR: [
        GenerationStrategy.VALUE_SUBSTITUTION,
        GenerationStrategy.REVERSE_CONSTRUCT,
    ],
    ErrorType.LOGICAL_FLAW: [
        GenerationStrategy.REVERSE_CONSTRUCT,
        GenerationStrategy.COMPREHENSIVE,
    ],
    ErrorType.CARELESS_MISTAKE: [
        GenerationStrategy.VALUE_SUBSTITUTION,
        GenerationStrategy.CONTEXT_CHANGE,
    ],
    ErrorType.KNOWLEDGE_GAP: [
        GenerationStrategy.CONDITION_MODIFY,
        GenerationStrategy.COMPREHENSIVE,
    ],
}

# 难度调节映射
DIFFICULTY_ADJUSTMENT: Dict[ErrorType, int] = {
    ErrorType.CONCEPT_MISUNDERSTANDING: -1,
    ErrorType.CALCULATION_ERROR: 0,
    ErrorType.LOGICAL_FLAW: 1,
    ErrorType.CARELESS_MISTAKE: 0,
    ErrorType.KNOWLEDGE_GAP: -2,
}


class VariantProblem(DomainModel):
    """变形题.

    表示基于原题生成的变形练习题。

    Attributes:
        id: 变形题唯一ID
        original_problem_id: 原题ID
        content: 题目内容
        difficulty: 难度等级（1-10）
        target_concept: 针对的概念
        error_type: 针对的错误类型
        strategy: 生成策略
        hint: 提示信息
        expected_steps: 预期解题步骤数
        answer: 答案
        solution: 解题过程
        is_validated: 是否通过验证
        validation_errors: 验证错误信息
        created_at: 创建时间
    """

    id: str = Field(default_factory=lambda: generate_id("variant"))
    original_problem_id: str = Field(..., description="原题ID")
    content: str = Field(..., description="题目内容")
    difficulty: int = Field(
        ...,
        ge=1,
        le=10,
        description="难度等级",
    )
    target_concept: str = Field(..., description="针对的概念")
    error_type: ErrorType = Field(..., description="针对的错误类型")
    strategy: GenerationStrategy = Field(..., description="生成策略")
    hint: Optional[str] = Field(None, description="提示信息")
    expected_steps: int = Field(
        default=3,
        ge=1,
        description="预期解题步骤数",
    )
    answer: Optional[str] = Field(None, description="答案")
    solution: Optional[str] = Field(None, description="解题过程")
    is_validated: bool = Field(
        default=False,
        description="是否通过验证",
    )
    validation_errors: List[str] = Field(
        default_factory=list,
        description="验证错误信息",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="额外元数据",
    )
    created_at: datetime = Field(
        default_factory=now_timestamp,
        description="创建时间",
    )

    @classmethod
    def get_strategies_for_error(
        cls,
        error_type: ErrorType,
    ) -> List[GenerationStrategy]:
        """获取适用于错误类型的生成策略.

        Args:
            error_type: 错误类型

        Returns:
            生成策略列表
        """
        return STRATEGY_MAPPING.get(error_type, [GenerationStrategy.VALUE_SUBSTITUTION])

    @classmethod
    def get_difficulty_adjustment(
        cls,
        error_type: ErrorType,
    ) -> int:
        """获取难度调节值.

        Args:
            error_type: 错误类型

        Returns:
            难度调节值（可为负数）
        """
        return DIFFICULTY_ADJUSTMENT.get(error_type, 0)

    @property
    def is_solvable(self) -> bool:
        """题目是否有解（有答案）."""
        return self.answer is not None and len(self.answer) > 0

    def mark_validated(self, errors: Optional[List[str]] = None) -> None:
        """标记验证状态.

        Args:
            errors: 验证错误信息，为空表示验证通过
        """
        if errors:
            self.is_validated = False
            self.validation_errors = errors
        else:
            self.is_validated = True
            self.validation_errors = []


class VariantGenerationRequest(DomainModel):
    """变形题生成请求.

    Attributes:
        student_id: 学生ID
        original_problem_id: 原题ID
        error_type: 错误类型
        difficulty: 目标难度
        count: 生成数量
        strategies: 指定策略（可选）
    """

    student_id: str = Field(..., description="学生ID")
    original_problem_id: str = Field(..., description="原题ID")
    error_type: ErrorType = Field(..., description="错误类型")
    difficulty: str = Field(
        default="same",
        description="目标难度 (same/easier/harder)",
    )
    count: int = Field(
        default=3,
        ge=1,
        le=5,
        description="生成数量",
    )
    strategies: Optional[List[GenerationStrategy]] = Field(
        None,
        description="指定策略",
    )


class VariantGenerationResult(DomainModel):
    """变形题生成结果.

    Attributes:
        request_id: 请求ID
        variants: 生成的变形题列表
        metadata: 生成元数据
        generated_at: 生成时间
    """

    request_id: str = Field(default_factory=lambda: generate_id("gen"))
    variants: List[VariantProblem] = Field(
        default_factory=list,
        description="生成的变形题列表",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="生成元数据",
    )
    generated_at: datetime = Field(
        default_factory=now_timestamp,
        description="生成时间",
    )

    @property
    def valid_count(self) -> int:
        """通过验证的变形题数量."""
        return sum(1 for v in self.variants if v.is_validated)

    @property
    def success_rate(self) -> float:
        """生成成功率."""
        if not self.variants:
            return 0.0
        return self.valid_count / len(self.variants)
