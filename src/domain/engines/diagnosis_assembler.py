"""诊断结果组装引擎.

功能追溯ID: F-DIAG-005
整合所有诊断组件，生成诊断报告，更新记忆系统，触发推送。
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.infrastructure.logging import get_logger
from src.domain.models.diagnosis import (
    DiagnosisResult,
    DiagnosisStatus,
    ErrorType,
    Problem,
    WrongProblem,
)
from src.domain.models.base import generate_id, now_timestamp
from src.domain.memory.memory_manager import MemoryManager
from src.domain.engines.error_detection import ErrorDetectionResult
from src.domain.engines.error_attribution import ErrorAttributionResult
from src.domain.engines.explanation_generator import ExplanationResult
from src.domain.engines.layered_diagnosis import DiagnosisPath

logger = get_logger(__name__)


@dataclass
class DiagnosisReport:
    """诊断报告.
    
    Attributes:
        report_id: 报告ID
        task_id: 任务ID
        student_id: 学生ID
        created_at: 创建时间
        diagnosis_summary: 诊断摘要
        wrong_problems: 错题列表
        explanations: 讲解内容
        knowledge_update: 知识图谱更新
        recommendations: 学习建议
        next_steps: 下一步行动
        statistics: 统计信息
    """
    report_id: str
    task_id: str
    student_id: str
    created_at: datetime
    diagnosis_summary: Dict[str, Any] = field(default_factory=dict)
    wrong_problems: List[Dict[str, Any]] = field(default_factory=list)
    explanations: List[Dict[str, Any]] = field(default_factory=list)
    knowledge_update: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "report_id": self.report_id,
            "task_id": self.task_id,
            "student_id": self.student_id,
            "created_at": self.created_at.isoformat(),
            "diagnosis_summary": self.diagnosis_summary,
            "wrong_problems": self.wrong_problems,
            "explanations": self.explanations,
            "knowledge_update": self.knowledge_update,
            "recommendations": self.recommendations,
            "next_steps": self.next_steps,
            "statistics": self.statistics,
        }


class DiagnosisAssembler:
    """诊断结果组装引擎.
    
    负责：
    1. 整合所有诊断组件结果
    2. 生成完整的诊断报告
    3. 更新记忆系统
    4. 触发推送通知
    
    Example:
        >>> assembler = DiagnosisAssembler(memory_manager)
        >>> result = await assembler.assemble(
        ...     task_id="task_123",
        ...     student_id="stu_456",
        ...     problems=problems,
        ...     detection_results=detection_results,
        ...     attribution_results=attribution_results,
        ...     explanation_results=explanation_results,
        ...     diagnosis_paths=diagnosis_paths,
        ... )
    """
    
    def __init__(self, memory_manager: MemoryManager):
        """初始化组装引擎.
        
        Args:
            memory_manager: 记忆管理器
        """
        self.memory_manager = memory_manager
        self.logger = get_logger(__name__)
    
    async def assemble(
        self,
        task_id: str,
        student_id: str,
        problems: List[Problem],
        detection_results: List[ErrorDetectionResult],
        attribution_results: List[ErrorAttributionResult],
        explanation_results: List[ExplanationResult],
        diagnosis_paths: List[Optional[DiagnosisPath]],
        processing_time: float = 0.0,
        variant_results: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[DiagnosisResult, DiagnosisReport]:
        """组装诊断结果.
        
        Args:
            task_id: 任务ID
            student_id: 学生ID
            problems: 题目列表
            detection_results: 错题识别结果
            attribution_results: 归因分析结果
            explanation_results: 讲解生成结果
            diagnosis_paths: 诊断路径列表
            processing_time: 处理时间
            variant_results: 变形题结果（可选）
            
        Returns:
            (DiagnosisResult, DiagnosisReport)
        """
        self.logger.info(
            "diagnosis_assemble_start",
            task_id=task_id,
            student_id=student_id,
            problem_count=len(problems),
        )
        
        # 1. 构建错题列表
        wrong_problems = self._build_wrong_problems(
            detection_results, attribution_results
        )
        
        # 2. 生成诊断摘要
        diagnosis_summary = self._generate_diagnosis_summary(
            problems, wrong_problems, attribution_results
        )
        
        # 3. 组装讲解内容
        explanations = self._assemble_explanations(explanation_results)
        
        # 4. 生成学习建议
        recommendations = self._generate_recommendations(
            attribution_results, diagnosis_paths
        )
        
        # 5. 确定下一步行动
        next_steps = self._determine_next_steps(
            wrong_problems, attribution_results, variant_results
        )
        
        # 6. 计算统计信息
        statistics = self._calculate_statistics(
            problems, wrong_problems, attribution_results, processing_time
        )
        
        # 7. 准备知识图谱更新
        knowledge_update = self._prepare_knowledge_update(
            student_id, problems, wrong_problems, attribution_results
        )
        
        # 创建诊断结果对象
        diagnosis_result = DiagnosisResult(
            task_id=task_id,
            status=DiagnosisStatus.COMPLETED,
            original_problems=problems,
            wrong_problems=wrong_problems,
            generated_variants=variant_results or [],
            knowledge_update=knowledge_update,
            processing_time=processing_time,
        )
        
        # 创建诊断报告
        report = DiagnosisReport(
            report_id=generate_id("report"),
            task_id=task_id,
            student_id=student_id,
            created_at=now_timestamp(),
            diagnosis_summary=diagnosis_summary,
            wrong_problems=[self._wrong_problem_to_dict(wp) for wp in wrong_problems],
            explanations=explanations,
            knowledge_update=knowledge_update,
            recommendations=recommendations,
            next_steps=next_steps,
            statistics=statistics,
        )
        
        # 8. 更新记忆系统
        await self._update_memory_system(
            student_id, problems, wrong_problems, attribution_results, diagnosis_paths
        )
        
        self.logger.info(
            "diagnosis_assemble_complete",
            task_id=task_id,
            wrong_count=len(wrong_problems),
            report_id=report.report_id,
        )
        
        return diagnosis_result, report
    
    def _build_wrong_problems(
        self,
        detection_results: List[ErrorDetectionResult],
        attribution_results: List[ErrorAttributionResult],
    ) -> List[WrongProblem]:
        """构建错题列表.
        
        Args:
            detection_results: 错题识别结果
            attribution_results: 归因结果
            
        Returns:
            错题列表
        """
        wrong_problems = []
        
        attribution_map = {
            ar.problem_id: ar for ar in attribution_results
        }
        
        for dr in detection_results:
            if not dr.is_wrong:
                continue
            
            attribution = attribution_map.get(dr.problem_id)
            
            # 构建错题信息
            root_cause = dr.error_location.description if dr.error_location else "未知错误"
            
            if attribution:
                root_cause = attribution.primary_cause
                knowledge_gaps = attribution.knowledge_gaps
            else:
                knowledge_gaps = dr.details.get("knowledge_gaps", [])
            
            wrong_problem = WrongProblem(
                problem_id=dr.problem_id,
                error_type=dr.error_type or ErrorType.KNOWLEDGE_GAP,
                root_cause=root_cause,
                concept_gap=knowledge_gaps,
                confidence=dr.confidence,
                student_answer=dr.student_answer,
                error_position=dr.error_location.__dict__ if dr.error_location else None,
            )
            
            wrong_problems.append(wrong_problem)
        
        return wrong_problems
    
    def _generate_diagnosis_summary(
        self,
        problems: List[Problem],
        wrong_problems: List[WrongProblem],
        attribution_results: List[ErrorAttributionResult],
    ) -> Dict[str, Any]:
        """生成诊断摘要.
        
        Args:
            problems: 题目列表
            wrong_problems: 错题列表
            attribution_results: 归因结果
            
        Returns:
            诊断摘要
        """
        total = len(problems)
        wrong = len(wrong_problems)
        correct = total - wrong
        
        # 统计错误类型分布
        error_type_count: Dict[str, int] = {}
        for wp in wrong_problems:
            et = wp.error_type.value if wp.error_type else "unknown"
            error_type_count[et] = error_type_count.get(et, 0) + 1
        
        # 获取主要问题
        main_issues = []
        for ar in sorted(attribution_results, key=lambda x: x.confidence, reverse=True)[:3]:
            main_issues.append({
                "problem_id": ar.problem_id,
                "primary_cause": ar.primary_cause,
                "confidence": ar.confidence,
            })
        
        return {
            "total_problems": total,
            "correct_count": correct,
            "wrong_count": wrong,
            "accuracy_rate": correct / total if total > 0 else 0,
            "error_type_distribution": error_type_count,
            "main_issues": main_issues,
        }
    
    def _assemble_explanations(
        self,
        explanation_results: List[ExplanationResult],
    ) -> List[Dict[str, Any]]:
        """组装讲解内容.
        
        Args:
            explanation_results: 讲解结果
            
        Returns:
            讲解内容列表
        """
        explanations = []
        
        for er in explanation_results:
            if not er.content:
                continue
            
            content = er.content
            explanations.append({
                "problem_id": er.problem_id,
                "main_explanation": content.main_explanation,
                "analogy": content.analogy,
                "step_hints": content.step_hints,
                "key_points": content.key_points,
                "visual_description": content.visual_description,
                "practice_suggestion": content.practice_suggestion,
                "safety_score": er.safety_score,
                "estimated_reading_time": er.estimated_reading_time,
            })
        
        return explanations
    
    def _generate_recommendations(
        self,
        attribution_results: List[ErrorAttributionResult],
        diagnosis_paths: List[Optional[DiagnosisPath]],
    ) -> List[str]:
        """生成学习建议.
        
        Args:
            attribution_results: 归因结果
            diagnosis_paths: 诊断路径
            
        Returns:
            建议列表
        """
        recommendations = []
        
        # 收集所有建议
        all_gaps = []
        is_careless_heavy = False
        
        for ar in attribution_results:
            recommendations.extend(ar.recommendations[:2])
            all_gaps.extend(ar.knowledge_gaps)
            if ar.is_careless_pattern:
                is_careless_heavy = True
        
        # 去重
        recommendations = list(dict.fromkeys(recommendations))
        
        # 添加基于诊断路径的建议
        if is_careless_heavy and "粗心" not in str(recommendations):
            recommendations.insert(0, "你最近粗心错误较多，建议做题时更加专注")
        
        if all_gaps:
            unique_gaps = list(dict.fromkeys(all_gaps))[:3]
            recommendations.append(f"重点巩固知识点：{', '.join(unique_gaps)}")
        
        return recommendations[:5]  # 最多5条
    
    def _determine_next_steps(
        self,
        wrong_problems: List[WrongProblem],
        attribution_results: List[ErrorAttributionResult],
        variant_results: Optional[List[Dict[str, Any]]],
    ) -> List[str]:
        """确定下一步行动.
        
        Args:
            wrong_problems: 错题列表
            attribution_results: 归因结果
            variant_results: 变形题结果
            
        Returns:
            行动列表
        """
        steps = []
        
        if wrong_problems:
            steps.append("查看错题讲解，理解错误原因")
            
            # 如果有变形题
            if variant_results:
                steps.append("尝试完成变形题，验证是否真正掌握")
            
            steps.append("整理错题到错题本")
        
        # 检查是否有知识缺口需要重点复习
        has_knowledge_gap = any(
            ar.knowledge_gaps for ar in attribution_results
        )
        if has_knowledge_gap:
            steps.append("根据薄弱点清单进行针对性复习")
        
        steps.append("明天尝试同类题目，检验学习效果")
        
        return steps[:4]
    
    def _calculate_statistics(
        self,
        problems: List[Problem],
        wrong_problems: List[WrongProblem],
        attribution_results: List[ErrorAttributionResult],
        processing_time: float,
    ) -> Dict[str, Any]:
        """计算统计信息.
        
        Args:
            problems: 题目列表
            wrong_problems: 错题列表
            attribution_results: 归因结果
            processing_time: 处理时间
            
        Returns:
            统计信息
        """
        total = len(problems)
        wrong = len(wrong_problems)
        
        # 归因置信度统计
        confidences = [ar.confidence for ar in attribution_results]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # 错误类型统计
        error_types: Dict[str, int] = {}
        for wp in wrong_problems:
            et = wp.error_type.value if wp.error_type else "unknown"
            error_types[et] = error_types.get(et, 0) + 1
        
        return {
            "total_problems": total,
            "correct_count": total - wrong,
            "wrong_count": wrong,
            "accuracy_rate": (total - wrong) / total if total > 0 else 0,
            "average_attribution_confidence": round(avg_confidence, 4),
            "processing_time_seconds": round(processing_time, 2),
            "error_type_breakdown": error_types,
        }
    
    def _prepare_knowledge_update(
        self,
        student_id: str,
        problems: List[Problem],
        wrong_problems: List[WrongProblem],
        attribution_results: List[ErrorAttributionResult],
    ) -> Dict[str, Any]:
        """准备知识图谱更新.
        
        Args:
            student_id: 学生ID
            problems: 题目列表
            wrong_problems: 错题列表
            attribution_results: 归因结果
            
        Returns:
            更新信息
        """
        # 构建问题ID到归因的映射
        attribution_map = {
            ar.problem_id: ar for ar in attribution_results
        }
        
        # 收集所有相关概念及其掌握度更新
        concept_updates = []
        
        for wp in wrong_problems:
            ar = attribution_map.get(wp.problem_id)
            if not ar:
                continue
            
            # 找到对应的题目
            problem = next((p for p in problems if p.id == wp.problem_id), None)
            if not problem:
                continue
            
            for concept_id in problem.knowledge_points:
                concept_updates.append({
                    "concept_id": concept_id,
                    "mastery_delta": -0.2,  # 错误降低掌握度
                    "reason": f"错题：{ar.primary_cause}",
                })
        
        return {
            "student_id": student_id,
            "concept_updates": concept_updates,
            "weak_points_identified": list(set(
                gap for ar in attribution_results for gap in ar.knowledge_gaps
            )),
        }
    
    async def _update_memory_system(
        self,
        student_id: str,
        problems: List[Problem],
        wrong_problems: List[WrongProblem],
        attribution_results: List[ErrorAttributionResult],
        diagnosis_paths: List[Optional[DiagnosisPath]],
    ) -> None:
        """更新记忆系统.
        
        Args:
            student_id: 学生ID
            problems: 题目列表
            wrong_problems: 错题列表
            attribution_results: 归因结果
            diagnosis_paths: 诊断路径
        """
        try:
            # 记录每个题目的答题尝试
            for i, problem in enumerate(problems):
                is_correct = problem.id not in [wp.problem_id for wp in wrong_problems]
                
                # 找到对应的归因
                ar = next(
                    (a for a in attribution_results if a.problem_id == problem.id),
                    None
                )
                
                # 找到对应的诊断路径
                path = diagnosis_paths[i] if i < len(diagnosis_paths) else None
                
                await self.memory_manager.record_problem_attempt(
                    student_id=student_id,
                    question_id=problem.id,
                    answer_content="",  # 实际应从OCR结果获取
                    is_correct=is_correct,
                    time_spent=0,
                    confidence=ar.confidence if ar else 0.5,
                    error_type=ar.error_type if ar else None,
                    decision_path=path.to_dict() if path else None,
                    concept_ids=problem.knowledge_points,
                )
            
            self.logger.info(
                "memory_system_updated",
                student_id=student_id,
                recorded_count=len(problems),
            )
            
        except Exception as e:
            self.logger.error(
                "memory_system_update_failed",
                student_id=student_id,
                error=str(e),
            )
            # 记忆系统更新失败不影响主流程
    
    def _wrong_problem_to_dict(self, wp: WrongProblem) -> Dict[str, Any]:
        """转换WrongProblem为字典.
        
        Args:
            wp: 错题对象
            
        Returns:
            字典
        """
        return {
            "problem_id": wp.problem_id,
            "error_type": wp.error_type.value if wp.error_type else None,
            "root_cause": wp.root_cause,
            "concept_gap": wp.concept_gap,
            "confidence": wp.confidence,
            "student_answer": wp.student_answer,
            "error_position": wp.error_position,
        }
    
    async def create_push_notification(
        self,
        report: DiagnosisReport,
    ) -> Dict[str, Any]:
        """创建推送通知内容.
        
        Args:
            report: 诊断报告
            
        Returns:
            推送内容
        """
        summary = report.diagnosis_summary
        wrong_count = summary.get("wrong_count", 0)
        total = summary.get("total_problems", 0)
        
        if wrong_count == 0:
            title = "🎉 作业诊断完成 - 全对！"
            body = f"太棒了！{total}道题全部正确，继续保持！"
        elif wrong_count == 1:
            title = "✅ 作业诊断完成"
            body = "只有1道错题，点击查看详细讲解"
        else:
            title = f"📋 作业诊断完成 - {wrong_count}道错题"
            body = f"共{total}道题，{wrong_count}道需要关注，点击查看讲解"
        
        return {
            "title": title,
            "body": body,
            "data": {
                "report_id": report.report_id,
                "task_id": report.task_id,
                "student_id": report.student_id,
                "type": "diagnosis_complete",
            },
            "priority": "high" if wrong_count > 0 else "normal",
        }
