"""Episodic记忆层实现.

作业事件流存储：
- 解题决策路径记录
- 原题与变形题lineage
- 时间序列查询

功能追溯ID: F-MEM-002
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from pydantic import Field

from src.domain.models.base import DomainModel, generate_id, now_timestamp
from src.domain.models.diagnosis import ErrorType
from src.domain.models.memory import LearningEpisode, LearningEventType
from src.infrastructure.db.answer import AnswerTrace, StudentAnswer
from src.infrastructure.db.variant import VariantAnswer, VariantQuestion
from src.infrastructure.storage.repositories import (
    AnswerTraceRepository,
    StudentAnswerRepository,
    VariantAnswerRepository,
    VariantQuestionRepository,
)


class ProblemAttempt(DomainModel):
    """题目尝试记录.
    
    单次解题尝试的完整记录。
    """
    
    attempt_id: str = Field(default_factory=lambda: generate_id("attempt"))
    question_id: str = Field(..., description="题目ID")
    answer_content: str = Field(..., description="答案内容")
    is_correct: Optional[bool] = Field(None, description="是否正确")
    time_spent: int = Field(default=0, ge=0, description="耗时(秒)")
    confidence_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="自信度",
    )
    decision_path: Dict[str, Any] = Field(
        default_factory=dict,
        description="决策路径",
    )
    created_at: datetime = Field(
        default_factory=now_timestamp,
        description="创建时间",
    )


class VariantLineage(DomainModel):
    """变形题血缘关系.
    
    记录原题与变形题的派生关系。
    """
    
    lineage_id: str = Field(default_factory=lambda: generate_id("lineage"))
    original_question_id: str = Field(..., description="原题ID")
    variant_id: str = Field(..., description="变形题ID")
    variant_type: str = Field(..., description="变形类型")
    student_id: str = Field(..., description="学生ID")
    
    # 练习记录
    original_result: Optional[bool] = Field(None, description="原题结果")
    variant_result: Optional[bool] = Field(None, description="变形题结果")
    
    # 时间线
    original_attempted_at: datetime = Field(..., description="原题尝试时间")
    variant_attempted_at: Optional[datetime] = Field(
        None,
        description="变形题尝试时间",
    )
    
    # 分析结果
    validation_outcome: Optional[str] = Field(
        None,
        description="验证结果: master/needs_work/misunderstanding",
    )
    
    def is_validated(self) -> bool:
        """检查是否已完成验证.
        
        Returns:
            是否已验证
        """
        return self.validation_outcome is not None
    
    def determine_validation(self) -> Optional[str]:
        """根据答题结果确定验证结果.
        
        Returns:
            验证结果
        """
        if self.original_result is None or self.variant_result is None:
            return None
        
        if self.original_result and self.variant_result:
            return "master"  # 完全掌握
        elif not self.original_result and self.variant_result:
            return "careless"  # 粗心错误
        elif self.original_result and not self.variant_result:
            return "misunderstanding"  # 深层误解
        else:
            return "needs_work"  # 需要继续练习


class DecisionTrace(DomainModel):
    """解题决策路径.
    
    记录学生解题时的思维过程。
    """
    
    trace_id: str = Field(default_factory=lambda: generate_id("trace"))
    answer_id: str = Field(..., description="答案ID")
    
    # 决策步骤
    steps: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="决策步骤",
    )
    
    # 关键节点
    key_decisions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="关键决策点",
    )
    
    # 使用的策略
    strategies_used: List[str] = Field(
        default_factory=list,
        description="使用的解题策略",
    )
    
    # 资源使用
    hints_used: int = Field(default=0, ge=0, description="使用提示次数")
    calculator_used: bool = Field(False, description="是否使用计算器")
    
    recorded_at: datetime = Field(
        default_factory=now_timestamp,
        description="记录时间",
    )
    
    def add_step(
        self,
        step_number: int,
        action: str,
        reasoning: Optional[str] = None,
    ) -> None:
        """添加决策步骤.
        
        Args:
            step_number: 步骤序号
            action: 执行的动作
            reasoning: 推理过程
        """
        self.steps.append({
            "step": step_number,
            "action": action,
            "reasoning": reasoning,
            "timestamp": now_timestamp().isoformat(),
        })
    
    def identify_key_decisions(self) -> List[Dict[str, Any]]:
        """识别关键决策点.
        
        Returns:
            关键决策点列表
        """
        # 简化实现：标记所有涉及策略选择的步骤
        key_decisions = []
        for step in self.steps:
            if "strategy" in step.get("action", "").lower():
                key_decisions.append(step)
        
        self.key_decisions = key_decisions
        return key_decisions


class EpisodeQuery(DomainModel):
    """事件查询条件.
    
    用于筛选学习事件。
    """
    
    student_id: Optional[str] = None
    event_types: List[LearningEventType] = Field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    question_id: Optional[str] = None
    subject: Optional[str] = None
    
    def matches(self, episode: LearningEpisode) -> bool:
        """检查事件是否匹配查询条件.
        
        Args:
            episode: 学习事件
            
        Returns:
            是否匹配
        """
        if self.student_id and episode.student_id != self.student_id:
            return False
        if self.event_types and episode.event_type not in self.event_types:
            return False
        if self.start_time and episode.timestamp < self.start_time:
            return False
        if self.end_time and episode.timestamp > self.end_time:
            return False
        if self.question_id and episode.problem_id != self.question_id:
            return False
        if self.subject and episode.subject != self.subject:
            return False
        return True


class EpisodicMemory:
    """Episodic记忆层管理器.
    
    管理学习事件的存储和查询。
    """
    
    def __init__(
        self,
        answer_repo: StudentAnswerRepository,
        trace_repo: AnswerTraceRepository,
        variant_repo: VariantQuestionRepository,
        variant_answer_repo: VariantAnswerRepository,
    ):
        """初始化Episodic记忆层.
        
        Args:
            answer_repo: 学生答案Repository
            trace_repo: 答题路径Repository
            variant_repo: 变形题Repository
            variant_answer_repo: 变形题答案Repository
        """
        self._answer_repo = answer_repo
        self._trace_repo = trace_repo
        self._variant_repo = variant_repo
        self._variant_answer_repo = variant_answer_repo
    
    async def record_attempt(
        self,
        student_id: str,
        question_id: str,
        answer_content: str,
        is_correct: Optional[bool],
        time_spent: int = 0,
        confidence: float = 0.5,
        error_type: Optional[ErrorType] = None,
    ) -> LearningEpisode:
        """记录解题尝试.
        
        Args:
            student_id: 学生ID
            question_id: 题目ID
            answer_content: 答案内容
            is_correct: 是否正确
            time_spent: 耗时(秒)
            confidence: 自信度
            error_type: 错误类型
            
        Returns:
            创建的学习事件
        """
        # 创建答案记录
        answer = StudentAnswer(
            answer_id=generate_id("answer"),
            question_id=question_id,
            student_id=student_id,
            answer_content=answer_content,
            is_correct=is_correct,
            confidence_score=confidence,
        )
        await self._answer_repo.create(answer)
        
        # 创建学习事件
        episode = LearningEpisode(
            student_id=student_id,
            event_type=LearningEventType.PROBLEM_ATTEMPT,
            problem_id=question_id,
            time_spent=time_spent,
            confidence=confidence,
            error_type=error_type,
            final_result="correct" if is_correct else "incorrect" if is_correct is False else "unknown",
            metadata={
                "answer_id": answer.answer_id,
                "answer_content": answer_content,
            },
        )
        
        return episode
    
    async def record_decision_trace(
        self,
        answer_id: str,
        decision_path: Dict[str, Any],
    ) -> DecisionTrace:
        """记录决策路径.
        
        Args:
            answer_id: 答案ID
            decision_path: 决策路径详情
            
        Returns:
            决策路径记录
        """
        trace = AnswerTrace(
            trace_id=generate_id("trace"),
            answer_id=answer_id,
            decision_path=decision_path,
        )
        await self._trace_repo.create(trace)
        
        return DecisionTrace(
            trace_id=trace.trace_id,
            answer_id=answer_id,
            steps=decision_path.get("steps", []),
            strategies_used=decision_path.get("strategies", []),
            hints_used=decision_path.get("hints_used", 0),
        )
    
    async def create_variant_lineage(
        self,
        original_question_id: str,
        variant_id: str,
        student_id: str,
        variant_type: str,
    ) -> VariantLineage:
        """创建变形题血缘关系.
        
        Args:
            original_question_id: 原题ID
            variant_id: 变形题ID
            student_id: 学生ID
            variant_type: 变形类型
            
        Returns:
            血缘关系记录
        """
        lineage = VariantLineage(
            original_question_id=original_question_id,
            variant_id=variant_id,
            student_id=student_id,
            variant_type=variant_type,
            original_attempted_at=now_timestamp(),
        )
        
        # 查找原题答案记录
        original_answer = await self._answer_repo.find_one(
            question_id=original_question_id,
            student_id=student_id,
        )
        if original_answer:
            lineage.original_result = original_answer.is_correct
        
        return lineage
    
    async def update_variant_result(
        self,
        lineage: VariantLineage,
        is_correct: bool,
    ) -> VariantLineage:
        """更新变形题结果.
        
        Args:
            lineage: 血缘关系
            is_correct: 变形题是否答对
            
        Returns:
            更新后的血缘关系
        """
        lineage.variant_result = is_correct
        lineage.variant_attempted_at = now_timestamp()
        lineage.validation_outcome = lineage.determine_validation()
        
        # 记录变形题答案
        variant_answer = VariantAnswer(
            variant_answer_id=generate_id("variant_ans"),
            variant_id=lineage.variant_id,
            student_id=lineage.student_id,
            answer_content="",  # 实际内容由调用方提供
            is_correct=is_correct,
        )
        await self._variant_answer_repo.create(variant_answer)
        
        return lineage
    
    async def get_episodes(
        self,
        query: EpisodeQuery,
        limit: int = 100,
    ) -> List[LearningEpisode]:
        """查询学习事件.
        
        Args:
            query: 查询条件
            limit: 返回数量限制
            
        Returns:
            学习事件列表
        """
        episodes = []
        
        # 从答案记录构建事件
        if query.student_id:
            answers = await self._answer_repo.find_many(
                student_id=query.student_id,
            )
            
            for answer in answers:
                # 获取决策路径
                trace = await self._trace_repo.find_one(answer_id=answer.answer_id)
                
                episode = LearningEpisode(
                    student_id=answer.student_id,
                    event_type=LearningEventType.PROBLEM_ATTEMPT,
                    problem_id=answer.question_id,
                    time_spent=trace.decision_path.get("time_spent", 0) if trace else 0,
                    confidence=answer.confidence_score or 0.5,
                    final_result="correct" if answer.is_correct else "incorrect",
                    metadata={
                        "answer_id": answer.answer_id,
                        "decision_path": trace.decision_path if trace else {},
                    },
                )
                
                if query.matches(episode):
                    episodes.append(episode)
                    
                if len(episodes) >= limit:
                    break
        
        return episodes[:limit]
    
    async def get_recent_episodes(
        self,
        student_id: str,
        hours: int = 24,
    ) -> List[LearningEpisode]:
        """获取最近的学习事件.
        
        Args:
            student_id: 学生ID
            hours: 时间范围(小时)
            
        Returns:
            最近的学习事件列表
        """
        cutoff_time = now_timestamp() - timedelta(hours=hours)
        
        query = EpisodeQuery(
            student_id=student_id,
            start_time=cutoff_time,
        )
        
        return await self.get_episodes(query)
    
    async def get_variant_lineages(
        self,
        student_id: str,
        original_question_id: Optional[str] = None,
    ) -> List[VariantLineage]:
        """获取变形题血缘关系.
        
        Args:
            student_id: 学生ID
            original_question_id: 原题ID(可选)
            
        Returns:
            血缘关系列表
        """
        lineages = []
        
        # 获取学生的变形题答案
        variant_answers = await self._variant_answer_repo.find_many(
            student_id=student_id,
        )
        
        for va in variant_answers:
            variant = await self._variant_repo.get_by_id(va.variant_id)
            if not variant:
                continue
            
            # 检查是否匹配原题筛选
            if original_question_id and variant.original_question_id != original_question_id:
                continue
            
            lineage = VariantLineage(
                variant_id=va.variant_id,
                original_question_id=variant.original_question_id,
                student_id=student_id,
                variant_type=variant.variant_type,
                variant_result=va.is_correct,
                variant_attempted_at=va.answered_at,
            )
            
            # 查找原题答案
            original_answer = await self._answer_repo.find_one(
                question_id=variant.original_question_id,
                student_id=student_id,
            )
            if original_answer:
                lineage.original_result = original_answer.is_correct
                lineage.original_attempted_at = original_answer.answered_at
            
            lineage.validation_outcome = lineage.determine_validation()
            lineages.append(lineage)
        
        return lineages
    
    async def get_decision_patterns(
        self,
        student_id: str,
        question_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取决策模式分析.
        
        Args:
            student_id: 学生ID
            question_id: 题目ID(可选)
            
        Returns:
            决策模式分析结果
        """
        patterns = {
            "total_attempts": 0,
            "avg_time_spent": 0,
            "common_strategies": [],
            "hint_usage_rate": 0.0,
        }
        
        # 获取学生的答题路径
        answers = await self._answer_repo.find_many(student_id=student_id)
        
        total_time = 0
        total_hints = 0
        strategy_counts = {}
        
        for answer in answers:
            if question_id and answer.question_id != question_id:
                continue
            
            trace = await self._trace_repo.find_one(answer_id=answer.answer_id)
            if not trace:
                continue
            
            patterns["total_attempts"] += 1
            total_time += trace.decision_path.get("time_spent", 0)
            total_hints += trace.decision_path.get("hints_used", 0)
            
            # 统计策略使用
            strategies = trace.decision_path.get("strategies", [])
            for strategy in strategies:
                strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        
        if patterns["total_attempts"] > 0:
            patterns["avg_time_spent"] = total_time / patterns["total_attempts"]
            patterns["hint_usage_rate"] = total_hints / patterns["total_attempts"]
            
            # 最常见的策略
            sorted_strategies = sorted(
                strategy_counts.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            patterns["common_strategies"] = [s[0] for s in sorted_strategies[:3]]
        
        return patterns
