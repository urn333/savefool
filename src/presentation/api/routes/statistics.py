"""统计路由.

提供学习统计、知识图谱、成长趋势等API接口.
所有数据从数据库真实查询，替代原有 mock 数据.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from src.application.services.memory_service import MemoryService
from src.infrastructure.db import (
    CognitiveGap,
    Homework,
    StudentKnowledgeMastery,
)
from src.infrastructure.db.enums import HomeworkStatus
from src.infrastructure.logging import get_logger
from src.infrastructure.storage.database import db_manager
from src.presentation.api.exceptions import NotFoundException, ValidationException
from src.presentation.api.schemas import (
    Achievement,
    BaseResponse,
    KnowledgeEdge,
    KnowledgeGraphData,
    KnowledgeGraphResponse,
    KnowledgeNode,
    OverviewStats,
    StatisticsOverviewResponse,
    StatisticsTrendResponse,
    SubjectStat,
    TrendData,
    TrendDataPoint,
    WeakPointItem,
    WeakPointsResponse,
)

logger = get_logger(__name__)
router = APIRouter()


# ========== 辅助查询函数 ==========

async def _get_homework_stats(
    student_id: str,
    period: str = "month",
    subject: Optional[str] = None,
) -> dict:
    """查询作业统计.

    Args:
        student_id: 学生ID
        period: 周期
        subject: 学科筛选

    Returns:
        统计字典
    """
    # 确定时间范围
    now = datetime.utcnow()
    if period == "week":
        start_date = now - timedelta(days=7)
    elif period == "semester":
        start_date = now - timedelta(days=90)
    elif period == "year":
        start_date = now - timedelta(days=365)
    else:
        start_date = now - timedelta(days=30)

    async with db_manager.session() as session:
        # 查询作业总数
        stmt = select(func.count()).where(
            Homework.student_id == student_id,
            Homework.created_at >= start_date,
        )
        if subject:
            stmt = stmt.where(Homework.subject == subject)
        result = await session.execute(stmt)
        total_homework = result.scalar() or 0

        # 查询已完成作业
        stmt = select(func.count(), func.sum(Homework.total_count), func.sum(Homework.error_count)).where(
            Homework.student_id == student_id,
            Homework.status == HomeworkStatus.COMPLETED.value,
            Homework.created_at >= start_date,
        )
        if subject:
            stmt = stmt.where(Homework.subject == subject)
        result = await session.execute(stmt)
        row = result.one_or_none()
        completed_homework = row[0] or 0
        total_questions = row[1] or 0
        total_errors = row[2] or 0

        # 正确率
        accuracy_rate = 0.0
        if total_questions > 0:
            accuracy_rate = (total_questions - total_errors) / total_questions

        # 学科统计
        subject_stats = []
        stmt = select(
            Homework.subject,
            func.count(),
            func.sum(Homework.total_count),
            func.sum(Homework.error_count),
        ).where(
            Homework.student_id == student_id,
            Homework.status == HomeworkStatus.COMPLETED.value,
            Homework.created_at >= start_date,
        ).group_by(Homework.subject)
        result = await session.execute(stmt)
        for row in result.all():
            sub, hw_count, q_count, err_count = row
            sub_accuracy = 0.0
            if q_count and q_count > 0:
                sub_accuracy = (q_count - (err_count or 0)) / q_count
            subject_stats.append({
                "subject": sub,
                "homework_count": hw_count or 0,
                "accuracy_rate": round(sub_accuracy, 2),
            })

        return {
            "total_homework": total_homework,
            "completed_homework": completed_homework,
            "total_questions": total_questions or 0,
            "total_errors": total_errors or 0,
            "accuracy_rate": round(accuracy_rate, 2),
            "subject_stats": subject_stats,
        }


async def _get_weekly_trend(
    student_id: str,
    metric: str,
    period: str,
    subject: Optional[str] = None,
) -> TrendData:
    """按周聚合趋势数据.

    Args:
        student_id: 学生ID
        metric: 指标
        period: 周期
        subject: 学科

    Returns:
        趋势数据
    """
    now = datetime.utcnow()
    if period == "week":
        weeks = 1
        start_date = now - timedelta(days=7)
    elif period == "semester":
        weeks = 12
        start_date = now - timedelta(days=84)
    elif period == "year":
        weeks = 52
        start_date = now - timedelta(days=364)
    else:
        weeks = 4
        start_date = now - timedelta(days=28)

    data_points = []
    current_start = start_date

    async with db_manager.session() as session:
        for i in range(weeks):
            week_end = current_start + timedelta(days=7)

            stmt = select(
                func.sum(Homework.total_count),
                func.sum(Homework.error_count),
                func.count(),
            ).where(
                Homework.student_id == student_id,
                Homework.status == HomeworkStatus.COMPLETED.value,
                Homework.completed_at >= current_start,
                Homework.completed_at < week_end,
            )
            if subject:
                stmt = stmt.where(Homework.subject == subject)

            result = await session.execute(stmt)
            row = result.one_or_none()
            q_count = row[0] or 0
            err_count = row[1] or 0
            hw_count = row[2] or 0

            if metric == "accuracy":
                value = 0.0
                if q_count > 0:
                    value = (q_count - err_count) / q_count
            elif metric == "mastery":
                # 查询该周结束时的平均掌握度
                stmt_m = select(func.avg(StudentKnowledgeMastery.mastery_level)).where(
                    StudentKnowledgeMastery.student_id == student_id,
                    StudentKnowledgeMastery.last_practiced <= week_end,
                )
                result_m = await session.execute(stmt_m)
                value = result_m.scalar() or 0.0
            else:
                value = float(hw_count)

            data_points.append(TrendDataPoint(
                date=week_end.strftime("%Y-%m-%d"),
                value=round(value, 2),
                homework_count=hw_count,
            ))

            current_start = week_end

    # 计算趋势
    valid_points = [p for p in data_points if p.homework_count > 0]
    if len(valid_points) >= 2:
        improvement = valid_points[-1].value - valid_points[0].value
        if improvement > 0.05:
            trend_direction = "up"
        elif improvement < -0.05:
            trend_direction = "down"
        else:
            trend_direction = "stable"
    else:
        improvement = 0
        trend_direction = "stable"

    return TrendData(
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=now.strftime("%Y-%m-%d"),
        data_points=data_points,
        trend_direction=trend_direction,
        improvement=round(improvement, 2),
    )


# ========== API 路由 ==========

@router.get(
    "/knowledge-graph",
    response_model=BaseResponse,
    summary="获取知识图谱",
    description="获取学生个人知识星系数据",
)
async def get_knowledge_graph(
    student_id: str = Query(..., description="学生ID"),
    subject: str = Query(default="math", description="学科筛选"),
) -> BaseResponse:
    """获取知识图谱.

    从 student_knowledge_mastery 表查询真实掌握度数据构建知识图谱.
    """
    logger.info("get_knowledge_graph", student_id=student_id, subject=subject)

    nodes: List[KnowledgeNode] = []
    edges: List[KnowledgeEdge] = []

    async with db_manager.session() as session:
        # 查询学生的知识掌握度
        memory_service = MemoryService(session)
        weak_points = await memory_service.get_weak_points(student_id, subject, limit=20)

        # 从掌握度表查询所有知识点
        stmt = select(StudentKnowledgeMastery).where(
            StudentKnowledgeMastery.student_id == student_id,
        )
        result = await session.execute(stmt)
        masteries = result.scalars().all()

        # 构建节点
        for i, m in enumerate(masteries):
            mastery = m.mastery_level or 0.0
            if mastery >= 0.8:
                status = "mastered"
            elif mastery >= 0.5:
                status = "learning"
            else:
                status = "weak"

            nodes.append(KnowledgeNode(
                id=m.knowledge_id,
                name=m.knowledge_id,  # 没有关联 knowledge_point 表，用 ID 作为名称
                category="未知",
                mastery_level=round(mastery, 2),
                status=status,
                x=100 + (i % 5) * 150,
                y=100 + (i // 5) * 100,
            ))

        # 如果没有掌握度数据，从薄弱点构建节点
        if not nodes and weak_points:
            for i, wp in enumerate(weak_points):
                nodes.append(KnowledgeNode(
                    id=f"wp_{i}",
                    name=wp["concept"],
                    category="薄弱点",
                    mastery_level=0.3,
                    status="weak",
                    x=100 + (i % 5) * 150,
                    y=100 + (i // 5) * 100,
                ))

    return BaseResponse(
        code=0,
        message="success",
        data=KnowledgeGraphResponse(
            student_id=student_id,
            subject=subject,
            graph=KnowledgeGraphData(nodes=nodes, edges=edges),
            updated_at=int(datetime.utcnow().timestamp()),
        ).model_dump()
    )


@router.get(
    "/weak-points",
    response_model=BaseResponse,
    summary="获取薄弱点",
    description="获取Top5薄弱知识点",
)
async def get_weak_points(
    student_id: str = Query(..., description="学生ID"),
    subject: Optional[str] = Query(None, description="学科筛选"),
    limit: int = Query(default=5, ge=1, le=10, description="数量限制"),
) -> BaseResponse:
    """获取薄弱点.

    从 cognitive_gap 和 student_knowledge_mastery 查询真实薄弱点.
    """
    logger.info("get_weak_points", student_id=student_id, subject=subject, limit=limit)

    weaknesses: List[WeakPointItem] = []

    async with db_manager.session() as session:
        memory_service = MemoryService(session)

        # 1. 查询 pending/crystallized 的认知缺口
        stmt = select(CognitiveGap).where(
            CognitiveGap.student_id == student_id,
        ).order_by(CognitiveGap.occurrence_count.desc())
        result = await session.execute(stmt)
        gaps = result.scalars().all()

        rank = 1
        for gap in gaps:
            if rank > limit:
                break
            for knowledge in gap.related_knowledge:
                if rank > limit:
                    break
                priority = "high" if gap.occurrence_count >= 2 else "medium"
                last_error = int(gap.discovered_at.timestamp()) if gap.discovered_at else int(datetime.utcnow().timestamp())

                weaknesses.append(WeakPointItem(
                    rank=rank,
                    knowledge_point_id=knowledge,
                    name=knowledge,
                    category="认知缺口",
                    mastery_level=0.2,
                    error_count=gap.occurrence_count,
                    last_error_at=last_error,
                    priority=priority,
                ))
                rank += 1

        # 2. 补充掌握度较低的知识点
        if rank <= limit:
            stmt = select(StudentKnowledgeMastery).where(
                StudentKnowledgeMastery.student_id == student_id,
                StudentKnowledgeMastery.mastery_level < 0.5,
            ).order_by(StudentKnowledgeMastery.mastery_level.asc())
            result = await session.execute(stmt)
            low_masteries = result.scalars().all()

            for m in low_masteries:
                if rank > limit:
                    break
                # 去重
                if any(w.knowledge_point_id == m.knowledge_id for w in weaknesses):
                    continue

                last_practiced = int(m.last_practiced.timestamp()) if m.last_practiced else int(datetime.utcnow().timestamp())
                weaknesses.append(WeakPointItem(
                    rank=rank,
                    knowledge_point_id=m.knowledge_id,
                    name=m.knowledge_id,
                    category="低掌握度",
                    mastery_level=round(m.mastery_level or 0.0, 2),
                    error_count=m.practice_count or 0,
                    last_error_at=last_practiced,
                    priority="medium",
                ))
                rank += 1

    return BaseResponse(
        code=0,
        message="success",
        data=WeakPointsResponse(
            student_id=student_id,
            weaknesses=weaknesses,
            total=len(weaknesses),
        ).model_dump()
    )


@router.get(
    "/trends",
    response_model=BaseResponse,
    summary="获取成长趋势",
    description="获取学习成长趋势曲线",
)
async def get_trends(
    student_id: str = Query(..., description="学生ID"),
    metric: str = Query(default="accuracy", description="指标: accuracy/mastery/practice_time"),
    period: str = Query(default="month", description="周期: week/month/semester/year"),
    subject: Optional[str] = Query(None, description="学科筛选"),
) -> BaseResponse:
    """获取成长趋势.

    从 homework 表按周聚合真实趋势数据.
    """
    logger.info("get_trends", student_id=student_id, metric=metric, period=period, subject=subject)

    valid_metrics = ["accuracy", "mastery", "practice_time"]
    if metric not in valid_metrics:
        raise ValidationException(
            message=f"不支持的指标: {metric}",
            errors=[{"field": "metric", "message": f"必须是: {valid_metrics}"}],
        )

    trend = await _get_weekly_trend(student_id, metric, period, subject)

    return BaseResponse(
        code=0,
        message="success",
        data=StatisticsTrendResponse(
            student_id=student_id,
            metric=metric,
            period=period,
            subject=subject,
            trend=trend,
        ).model_dump()
    )


@router.get(
    "/overview",
    response_model=BaseResponse,
    summary="获取统计概览",
    description="获取学习统计概览",
)
async def get_statistics_overview(
    student_id: str = Query(..., description="学生ID"),
    period: str = Query(default="month", description="周期: week/month/semester"),
) -> BaseResponse:
    """获取统计概览.

    从 homework 表查询真实统计数据.
    """
    logger.info("get_statistics_overview", student_id=student_id, period=period)

    stats = await _get_homework_stats(student_id, period)

    # 学科统计
    subject_stats = [
        SubjectStat(
            subject=s["subject"],
            homework_count=s["homework_count"],
            accuracy_rate=s["accuracy_rate"],
            weakness_count=0,  # 暂不从这里计算
        )
        for s in stats["subject_stats"]
    ]

    # 成就（简化实现，基于真实数据触发）
    now = int(datetime.utcnow().timestamp())
    achievements: List[Achievement] = []

    if stats["accuracy_rate"] >= 0.9 and stats["total_questions"] >= 10:
        achievements.append(Achievement(
            id="ach_perfect",
            name="高正确率",
            icon="trophy",
            earned_at=now,
        ))
    if stats["total_homework"] >= 5:
        achievements.append(Achievement(
            id="ach_active",
            name="积极学习者",
            icon="fire",
            earned_at=now,
        ))

    overview = OverviewStats(
        total_homework=stats["total_homework"],
        total_questions=stats["total_questions"],
        accuracy_rate=stats["accuracy_rate"],
        practice_time=stats["total_questions"] * 2,  # 估算：每题2分钟
        streak_days=0,  # 需要额外的打卡记录
    )

    result = StatisticsOverviewResponse(
        student_id=student_id,
        period=period,
        overview=overview,
        subject_stats=subject_stats,
        achievements=achievements,
    )

    return BaseResponse(
        code=0,
        message="success",
        data=result.model_dump()
    )
