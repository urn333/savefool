"""仲裁相关领域模型.

定义多模型仲裁结果、模型投票等核心业务模型。
"""

from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator

from src.domain.models.base import DomainModel, generate_id
from src.domain.models.diagnosis import ErrorType


class ModelVote(DomainModel):
    """模型投票.

    表示单个模型的诊断投票。

    Attributes:
        model_id: 模型标识
        is_correct: 是否正确
        error_type: 错误类型（如果错误）
        confidence: 置信度
        reason: 推理说明
    """

    model_id: str = Field(..., description="模型标识")
    is_correct: bool = Field(..., description="是否正确")
    error_type: Optional[ErrorType] = Field(
        None,
        description="错误类型",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="置信度",
    )
    reason: str = Field(
        default="",
        description="推理说明",
    )


class ModelResult(DomainModel):
    """模型结果.

    表示单个模型的完整诊断结果。

    Attributes:
        model_id: 模型标识
        is_correct: 是否正确
        error_type: 错误类型
        concept_scores: 概念评分
        confidence: 置信度
        diagnosis: 详细诊断
        latency_ms: 响应延迟（毫秒）
    """

    model_id: str = Field(..., description="模型标识")
    is_correct: bool = Field(..., description="是否正确")
    error_type: Optional[ErrorType] = Field(
        None,
        description="错误类型",
    )
    concept_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="概念评分",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="置信度",
    )
    diagnosis: Dict[str, Any] = Field(
        default_factory=dict,
        description="详细诊断",
    )
    latency_ms: float = Field(
        default=0.0,
        description="响应延迟（毫秒）",
    )


class ArbitrationResult(DomainModel):
    """仲裁结果.

    表示多模型仲裁的最终结果。

    Attributes:
        id: 结果ID
        problem_id: 题目ID
        is_correct: 最终判断是否正确
        error_type: 错误类型（如果错误）
        confidence: 最终置信度
        model_votes: 各模型投票
        is_consensus: 是否达成共识
        consensus_ratio: 共识比例
        conflict_info: 冲突信息（如果有）
        used_models: 使用的模型列表
    """

    id: str = Field(default_factory=lambda: generate_id("arbit"))
    problem_id: str = Field(..., description="题目ID")
    is_correct: bool = Field(..., description="最终判断是否正确")
    error_type: Optional[ErrorType] = Field(
        None,
        description="错误类型",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="最终置信度",
    )
    model_votes: Dict[str, ModelVote] = Field(
        default_factory=dict,
        description="各模型投票",
    )
    is_consensus: bool = Field(
        default=True,
        description="是否达成共识",
    )
    consensus_ratio: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="共识比例",
    )
    conflict_info: Optional[Dict[str, Any]] = Field(
        None,
        description="冲突信息（如果有）",
    )
    used_models: List[str] = Field(
        default_factory=list,
        description="使用的模型列表",
    )

    @field_validator("consensus_ratio")
    @classmethod
    def validate_consensus_ratio(cls, v: float) -> float:
        """验证共识比例."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("consensus_ratio must be between 0.0 and 1.0")
        return v

    @property
    def primary_model(self) -> Optional[str]:
        """获取主要模型（置信度最高）."""
        if not self.model_votes:
            return None
        return max(
            self.model_votes.items(),
            key=lambda x: x[1].confidence,
        )[0]

    @property
    def agreement_count(self) -> int:
        """获取同意最终结果的模型数量."""
        count = 0
        for vote in self.model_votes.values():
            if vote.is_correct == self.is_correct:
                count += 1
        return count

    @property
    def disagreement_count(self) -> int:
        """获取反对最终结果的模型数量."""
        return len(self.model_votes) - self.agreement_count

    def get_vote_by_model(self, model_id: str) -> Optional[ModelVote]:
        """获取指定模型的投票.

        Args:
            model_id: 模型标识

        Returns:
            模型投票，不存在则返回None
        """
        return self.model_votes.get(model_id)
