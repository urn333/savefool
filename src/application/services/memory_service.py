"""记忆服务.

封装记忆系统的查询和写入操作，
为诊断流程提供学生历史数据读取和诊断结果持久化.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.memory.memory_manager import MemoryManager
from src.domain.models.diagnosis import ErrorType
from src.infrastructure.logging import get_logger
from src.infrastructure.storage.repositories import (
    AnswerTraceRepository,
    CognitiveGapRepository,
    CognitiveProfileRepository,
    ErrorDiagnosisRepository,
    GapEvidenceRepository,
    KnowledgeDependencyRepository,
    KnowledgePointRepository,
    MisconceptionRepository,
    StudentAnswerRepository,
    StudentKnowledgeMasteryRepository,
    VariantAnswerRepository,
    VariantQuestionRepository,
)

logger = get_logger(__name__)


class MemoryService:
    """记忆服务.

    提供学生认知画像查询、薄弱环节分析、诊断结果记录等功能.
    """

    def __init__(self, session: AsyncSession):
        """初始化记忆服务.

        Args:
            session: 数据库会话.
        """
        self.session = session
        self.memory_manager = MemoryManager(
            profile_repo=CognitiveProfileRepository(session),
            answer_repo=StudentAnswerRepository(session),
            trace_repo=AnswerTraceRepository(session),
            variant_repo=VariantQuestionRepository(session),
            variant_answer_repo=VariantAnswerRepository(session),
            knowledge_repo=KnowledgePointRepository(session),
            mastery_repo=StudentKnowledgeMasteryRepository(session),
            dependency_repo=KnowledgeDependencyRepository(session),
            misconception_repo=MisconceptionRepository(session),
            gap_repo=CognitiveGapRepository(session),
            evidence_repo=GapEvidenceRepository(session),
            diagnosis_repo=ErrorDiagnosisRepository(session),
        )

    async def get_weak_points(
        self,
        student_id: str,
        subject: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """获取学生薄弱环节.

        综合查询 pending gaps 和低掌握度知识点.

        Args:
            student_id: 学生ID.
            subject: 学科筛选.
            limit: 返回数量上限.

        Returns:
            薄弱环节列表，每个元素包含 concept, severity, reason, source.
        """
        weak_points: List[Dict[str, Any]] = []
        seen_concepts: set = set()

        try:
            # 1. 查询 Pending Gaps（待验证的认知缺口）
            pending_gaps = await self.memory_manager.meta.get_pending_gaps(student_id)
            for gap in pending_gaps:
                # 筛选学科（如果 gap 有关联知识点，尝试匹配学科）
                for knowledge in gap.related_knowledge:
                    if knowledge in seen_concepts:
                        continue
                    seen_concepts.add(knowledge)
                    weak_points.append({
                        "concept": knowledge,
                        "severity": "high" if gap.occurrence_count >= 2 else "medium",
                        "reason": f"认知缺口（{gap.gap_type}），已出现 {gap.occurrence_count} 次",
                        "source": "cognitive_gap",
                        "gap_type": gap.gap_type,
                        "occurrence_count": gap.occurrence_count,
                    })

            # 2. 查询低掌握度知识点
            knowledge_graph = await self.memory_manager.semantic.get_knowledge_graph(student_id)
            if knowledge_graph and knowledge_graph.weak_points:
                for wp in knowledge_graph.weak_points:
                    if wp.concept_id in seen_concepts:
                        continue
                    seen_concepts.add(wp.concept_id)
                    weak_points.append({
                        "concept": wp.concept_id,
                        "severity": wp.severity,
                        "reason": f"掌握度较低（{wp.severity}）",
                        "source": "knowledge_graph",
                    })

            # 按严重程度排序
            severity_order = {"high": 0, "medium": 1, "low": 2}
            weak_points.sort(
                key=lambda x: severity_order.get(x.get("severity", "low"), 3)
            )

            return weak_points[:limit]

        except Exception as e:
            logger.error("get_weak_points_failed", student_id=student_id, error=str(e))
            return []

    async def format_weak_points_for_prompt(
        self,
        student_id: str,
        subject: Optional[str] = None,
    ) -> str:
        """格式化薄弱环节为 Prompt 文本.

        Args:
            student_id: 学生ID.
            subject: 学科.

        Returns:
            格式化的文本，可直接拼入 AI Prompt.
        """
        weak_points = await self.get_weak_points(student_id, subject, limit=5)
        if not weak_points:
            return ""

        lines = ["【该学生历史薄弱环节（供诊断参考）】"]
        for i, wp in enumerate(weak_points, 1):
            lines.append(f"{i}. {wp['concept']} — {wp['reason']}")

        lines.append(
            "\n请特别关注以上薄弱点："
            "如果本次作业涉及这些知识点，请重点分析学生是否已改善；"
            "如果学生再次在这些知识点上出错，请提高诊断的严格性。"
        )
        return "\n".join(lines)

    async def record_diagnosis_result(
        self,
        student_id: str,
        homework_id: str,
        questions_data: List[Dict[str, Any]],
    ) -> None:
        """记录诊断结果到记忆系统.

        逐题记录答题尝试，更新掌握度和认知缺口.

        Args:
            student_id: 学生ID.
            homework_id: 作业ID.
            questions_data: 题目数据列表，每项包含:
                - content: 题目内容
                - student_answer: 学生答案
                - correct_answer: 正确答案
                - is_correct: 是否正确
                - knowledge_points: 知识点列表
                - error_type: 错误类型（如果是错题）
        """
        if not questions_data:
            return

        try:
            for q in questions_data:
                is_correct = q.get("is_correct", True)

                # 提取知识点列表
                concept_ids = []
                kps = q.get("knowledge_points", [])
                if isinstance(kps, list):
                    for kp in kps:
                        if isinstance(kp, dict):
                            name = kp.get("name", "")
                            if name:
                                concept_ids.append(name)
                        elif isinstance(kp, str):
                            concept_ids.append(kp)

                # 确定错误类型
                error_type = None
                if not is_correct:
                    et = q.get("error_type", "unknown")
                    error_type = self._parse_error_type(et)

                # 记录答题尝试
                await self.memory_manager.record_problem_attempt(
                    student_id=student_id,
                    question_id=str(q.get("question_id", homework_id)),
                    answer_content=q.get("student_answer", ""),
                    is_correct=is_correct,
                    time_spent=0,
                    confidence=q.get("confidence", 0.8),
                    error_type=error_type,
                    decision_path=None,
                    concept_ids=concept_ids,
                )

            logger.info(
                "diagnosis_recorded_to_memory",
                student_id=student_id,
                homework_id=homework_id,
                question_count=len(questions_data),
            )

        except Exception as e:
            logger.error(
                "record_diagnosis_result_failed",
                student_id=student_id,
                homework_id=homework_id,
                error=str(e),
            )
            # 记忆写入失败不影响主流程

    def _parse_error_type(self, error_type_str: str) -> Optional[ErrorType]:
        """解析错误类型字符串.

        Args:
            error_type_str: 错误类型字符串.

        Returns:
            ErrorType 枚举值，解析失败返回 None.
        """
        mapping = {
            "careless": ErrorType.CARELESS_MISTAKE,
            "careless_mistake": ErrorType.CARELESS_MISTAKE,
            "method_error": ErrorType.LOGICAL_FLAW,
            "concept_error": ErrorType.CONCEPT_MISUNDERSTANDING,
            "concept_gap": ErrorType.KNOWLEDGE_GAP,
            "concept_misunderstanding": ErrorType.CONCEPT_MISUNDERSTANDING,
            "calculation_error": ErrorType.CALCULATION_ERROR,
            "reading_error": ErrorType.READING_ERROR,
            "logic_error": ErrorType.LOGICAL_FLAW,
            "logical_flaw": ErrorType.LOGICAL_FLAW,
            "knowledge_gap": ErrorType.KNOWLEDGE_GAP,
            "unknown": ErrorType.KNOWLEDGE_GAP,
            "none": None,
        }
        return mapping.get(str(error_type_str).lower().strip(), ErrorType.KNOWLEDGE_GAP)

    async def run_crystallization(self, student_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """运行记忆结晶.

        将 pending gaps 转化为 crystallized features.

        Args:
            student_id: 学生ID，None 则处理所有学生.

        Returns:
            结晶结果列表.
        """
        try:
            results = await self.memory_manager.process_crystallization(student_id)
            return [
                {
                    "gap_id": r.gap_id,
                    "student_id": r.student_id,
                    "success": r.success,
                    "new_status": r.new_status,
                }
                for r in results
            ]
        except Exception as e:
            logger.error("crystallization_failed", student_id=student_id, error=str(e))
            return []
