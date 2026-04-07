"""统计路由.

提供学习统计、知识图谱、成长趋势等API接口.
"""

import random
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Query

from src.infrastructure.logging import get_logger
from src.presentation.api.exceptions import NotFoundException, ValidationException
from src.presentation.api.schemas import (
    BaseResponse,
    KnowledgeEdge,
    KnowledgeGraphData,
    KnowledgeGraphResponse,
    KnowledgeNode,
    StatisticsOverviewResponse,
    StatisticsTrendResponse,
    SubjectStat,
    TrendData,
    TrendDataPoint,
    WeakPointItem,
    WeakPointsResponse,
    OverviewStats,
    Achievement,
)

logger = get_logger(__name__)
router = APIRouter()

# 内存存储
_knowledge_graph_store: dict = {}
_statistics_store: dict = {}


# 模拟知识数据
MOCK_KNOWLEDGE_POINTS = [
    {"id": "kp_001", "name": "加法运算", "category": "计算"},
    {"id": "kp_002", "name": "进位加法", "category": "计算"},
    {"id": "kp_003", "name": "减法借位", "category": "计算"},
    {"id": "kp_004", "name": "乘法口诀", "category": "计算"},
    {"id": "kp_005", "name": "除法基础", "category": "计算"},
    {"id": "kp_006", "name": "分数认识", "category": "数与代数"},
    {"id": "kp_007", "name": "小数运算", "category": "数与代数"},
    {"id": "kp_008", "name": "平面图形", "category": "几何"},
    {"id": "kp_009", "name": "立体图形", "category": "几何"},
    {"id": "kp_010", "name": "数据统计", "category": "统计"},
]

MOCK_KNOWLEDGE_EDGES = [
    {"source": "kp_001", "target": "kp_002", "relation": "prerequisite"},
    {"source": "kp_001", "target": "kp_003", "relation": "prerequisite"},
    {"source": "kp_001", "target": "kp_004", "relation": "prerequisite"},
    {"source": "kp_004", "target": "kp_005", "relation": "prerequisite"},
    {"source": "kp_005", "target": "kp_006", "relation": "related"},
    {"source": "kp_001", "target": "kp_007", "relation": "prerequisite"},
    {"source": "kp_008", "target": "kp_009", "relation": "prerequisite"},
]


def _generate_mock_knowledge_graph(student_id: str, subject: str) -> KnowledgeGraphResponse:
    """生成模拟知识图谱.
    
    Args:
        student_id: 学生ID
        subject: 学科
        
    Returns:
        知识图谱响应
    """
    # 生成节点（带掌握度）
    nodes = []
    for i, kp in enumerate(MOCK_KNOWLEDGE_POINTS):
        # 模拟不同的掌握度
        mastery = random.uniform(0.3, 0.95)
        
        # 根据掌握度确定状态
        if mastery >= 0.8:
            status = "mastered"
        elif mastery >= 0.5:
            status = "learning"
        else:
            status = "weak"
        
        nodes.append(KnowledgeNode(
            id=kp["id"],
            name=kp["name"],
            category=kp["category"],
            mastery_level=round(mastery, 2),
            status=status,
            x=100 + (i % 5) * 150,
            y=100 + (i // 5) * 100,
        ))
    
    # 边
    edges = [
        KnowledgeEdge(
            source=e["source"],
            target=e["target"],
            relation=e["relation"],
        )
        for e in MOCK_KNOWLEDGE_EDGES
    ]
    
    return KnowledgeGraphResponse(
        student_id=student_id,
        subject=subject,
        graph=KnowledgeGraphData(nodes=nodes, edges=edges),
        updated_at=int(datetime.utcnow().timestamp()),
    )


def _generate_mock_weak_points(student_id: str, limit: int = 5) -> WeakPointsResponse:
    """生成模拟薄弱点.
    
    Args:
        student_id: 学生ID
        limit: 数量限制
        
    Returns:
        薄弱点响应
    """
    # 按掌握度排序（低的在前）
    weak_points = []
    
    weak_knowledge = [
        {"id": "kp_003", "name": "减法借位", "category": "计算", "mastery": 0.35, "errors": 12},
        {"id": "kp_004", "name": "乘法口诀", "category": "计算", "mastery": 0.45, "errors": 8},
        {"id": "kp_006", "name": "分数认识", "category": "数与代数", "mastery": 0.50, "errors": 6},
        {"id": "kp_009", "name": "立体图形", "category": "几何", "mastery": 0.55, "errors": 5},
        {"id": "kp_010", "name": "数据统计", "category": "统计", "mastery": 0.60, "errors": 4},
    ]
    
    now = int(datetime.utcnow().timestamp())
    
    for i, kp in enumerate(weak_knowledge[:limit], 1):
        # 确定优先级
        if kp["mastery"] < 0.4:
            priority = "high"
        elif kp["mastery"] < 0.6:
            priority = "medium"
        else:
            priority = "low"
        
        # 随机最后错误时间（最近7天内）
        last_error = now - random.randint(0, 7 * 24 * 3600)
        
        weak_points.append(WeakPointItem(
            rank=i,
            knowledge_point_id=kp["id"],
            name=kp["name"],
            category=kp["category"],
            mastery_level=kp["mastery"],
            error_count=kp["errors"],
            last_error_at=last_error,
            priority=priority,
        ))
    
    return WeakPointsResponse(
        student_id=student_id,
        weaknesses=weak_points,
        total=len(weak_points),
    )


def _generate_mock_trend(
    student_id: str,
    metric: str,
    period: str,
    subject: Optional[str] = None,
) -> StatisticsTrendResponse:
    """生成模拟趋势数据.
    
    Args:
        student_id: 学生ID
        metric: 指标
        period: 周期
        subject: 学科（可选）
        
    Returns:
        趋势响应
    """
    # 确定时间范围
    now = datetime.utcnow()
    
    if period == "week":
        days = 7
        start_date = now - timedelta(days=7)
    elif period == "month":
        days = 30
        start_date = now - timedelta(days=30)
    elif period == "semester":
        days = 90
        start_date = now - timedelta(days=90)
    elif period == "year":
        days = 365
        start_date = now - timedelta(days=365)
    else:
        days = 30
        start_date = now - timedelta(days=30)
    
    # 生成数据点（每周一个点）
    data_points = []
    current_date = start_date
    current_value = 0.6  # 起始值
    
    while current_date <= now:
        # 模拟上升趋势
        current_value += random.uniform(-0.05, 0.08)
        current_value = max(0.3, min(0.95, current_value))
        
        data_points.append(TrendDataPoint(
            date=current_date.strftime("%Y-%m-%d"),
            value=round(current_value, 2),
            homework_count=random.randint(1, 5),
        ))
        
        current_date += timedelta(days=7)
    
    # 计算趋势
    if len(data_points) >= 2:
        improvement = data_points[-1].value - data_points[0].value
        if improvement > 0.1:
            trend_direction = "up"
        elif improvement < -0.1:
            trend_direction = "down"
        else:
            trend_direction = "stable"
    else:
        improvement = 0
        trend_direction = "stable"
    
    trend = TrendData(
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=now.strftime("%Y-%m-%d"),
        data_points=data_points,
        trend_direction=trend_direction,
        improvement=round(improvement, 2),
    )
    
    return StatisticsTrendResponse(
        student_id=student_id,
        metric=metric,
        period=period,
        subject=subject,
        trend=trend,
    )


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
    
    返回学生个人知识图谱，包含知识点节点和依赖关系边。
    
    Args:
        student_id: 学生ID
        subject: 学科（默认math）
        
    Returns:
        知识图谱数据
    """
    logger.info(
        "get_knowledge_graph",
        student_id=student_id,
        subject=subject,
    )
    
    # 检查缓存
    cache_key = f"{student_id}_{subject}"
    if cache_key not in _knowledge_graph_store:
        _knowledge_graph_store[cache_key] = _generate_mock_knowledge_graph(
            student_id, subject
        )
    
    graph = _knowledge_graph_store[cache_key]
    
    return BaseResponse(
        code=0,
        message="success",
        data=graph.model_dump()
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
    
    返回学生薄弱知识点Top列表，按掌握度排序。
    
    Args:
        student_id: 学生ID
        subject: 学科筛选（可选）
        limit: 数量（默认5，最大10）
        
    Returns:
        薄弱点列表
    """
    logger.info(
        "get_weak_points",
        student_id=student_id,
        subject=subject,
        limit=limit,
    )
    
    weak_points = _generate_mock_weak_points(student_id, limit)
    
    return BaseResponse(
        code=0,
        message="success",
        data=weak_points.model_dump()
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
    
    返回学生在指定指标上的成长趋势曲线。
    
    Args:
        student_id: 学生ID
        metric: 指标（accuracy/mastery/practice_time）
        period: 周期（week/month/semester/year）
        subject: 学科筛选（可选）
        
    Returns:
        趋势数据
    """
    logger.info(
        "get_trends",
        student_id=student_id,
        metric=metric,
        period=period,
        subject=subject,
    )
    
    # 验证指标
    valid_metrics = ["accuracy", "mastery", "practice_time"]
    if metric not in valid_metrics:
        raise ValidationException(
            message=f"不支持的指标: {metric}",
            errors=[{"field": "metric", "message": f"必须是: {valid_metrics}"}],
        )
    
    trend = _generate_mock_trend(student_id, metric, period, subject)
    
    return BaseResponse(
        code=0,
        message="success",
        data=trend.model_dump()
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
    
    返回学生学习概览统计信息。
    
    Args:
        student_id: 学生ID
        period: 周期（week/month/semester）
        
    Returns:
        统计概览
    """
    logger.info(
        "get_statistics_overview",
        student_id=student_id,
        period=period,
    )
    
    # 模拟概览数据
    overview = OverviewStats(
        total_homework=45,
        total_questions=450,
        accuracy_rate=0.78,
        practice_time=1800,
        streak_days=7,
    )
    
    # 学科统计
    subject_stats = [
        SubjectStat(
            subject="math",
            homework_count=20,
            accuracy_rate=0.75,
            weakness_count=3,
        ),
        SubjectStat(
            subject="chinese",
            homework_count=15,
            accuracy_rate=0.82,
            weakness_count=2,
        ),
        SubjectStat(
            subject="english",
            homework_count=10,
            accuracy_rate=0.80,
            weakness_count=1,
        ),
    ]
    
    # 成就
    now = int(datetime.utcnow().timestamp())
    achievements = [
        Achievement(
            id="ach_001",
            name="连续7天打卡",
            icon="streak_7",
            earned_at=now - 86400,
        ),
        Achievement(
            id="ach_002",
            name="首次全对",
            icon="perfect",
            earned_at=now - 172800,
        ),
    ]
    
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
