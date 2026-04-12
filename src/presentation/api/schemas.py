"""API请求/响应Schema定义.

使用Pydantic模型定义所有API的数据结构.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from src.domain.models.base import generate_id


# ========== 基础Schema ==========

class BaseResponse(BaseModel):
    """统一响应格式基类."""
    
    code: int = Field(default=0, description="业务状态码，0表示成功")
    message: str = Field(default="success", description="状态描述")
    data: Optional[Any] = Field(default=None, description="业务数据")
    request_id: Optional[str] = Field(default=None, description="请求追踪ID")
    timestamp: int = Field(
        default_factory=lambda: int(datetime.utcnow().timestamp()),
        description="响应时间戳"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: int(v.timestamp()),
        }


class PaginationData(BaseModel):
    """分页数据."""
    
    has_more: bool = Field(description="是否有更多数据")
    next_cursor: Optional[str] = Field(None, description="下一页游标")
    total: Optional[int] = Field(None, description="总数")


class PaginatedResponse(BaseResponse):
    """分页响应格式."""
    
    data: Dict[str, Any] = Field(default_factory=dict)
    
    @classmethod
    def create(
        cls,
        items: List[Any],
        pagination: PaginationData,
        request_id: Optional[str] = None,
    ) -> "PaginatedResponse":
        """创建分页响应."""
        return cls(
            code=0,
            message="success",
            data={
                "list": items,
                "pagination": pagination.model_dump(),
            },
            request_id=request_id,
        )


# ========== 作业相关Schema ==========

class SubjectType(str, Enum):
    """学科类型."""
    MATH = "math"
    CHINESE = "chinese"
    ENGLISH = "english"
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"
    BIOLOGY = "biology"


class HomeworkStatus(str, Enum):
    """作业状态."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DiagnosisMode(str, Enum):
    """诊断模式."""
    DIAGNOSIS = "diagnosis"      # 智能诊断（默认）
    SOLUTION = "solution"        # 查看解答
    EXPLAIN = "explain"          # 知识点讲解
    SINGLE = "single"            # 单题深度分析


class HomeworkUploadRequest(BaseModel):
    """作业上传请求.
    
    使用multipart/form-data格式上传.
    """
    
    student_id: str = Field(..., description="学生ID")
    subject: SubjectType = Field(..., description="学科")
    description: Optional[str] = Field(
        None,
        max_length=140,
        description="家长描述，≤140字"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "student_id": "stu_123456",
                "subject": "math",
                "description": "孩子这道题做错了，不太理解进位",
            }
        }


class HomeworkUploadResponse(BaseModel):
    """作业上传响应数据."""
    
    homework_id: str = Field(..., description="作业ID")
    status: HomeworkStatus = Field(..., description="作业状态")
    created_at: int = Field(..., description="创建时间戳")
    estimated_time: int = Field(default=30, description="预计处理时间(秒)")


class HomeworkSummary(BaseModel):
    """作业摘要."""
    
    homework_id: str = Field(..., description="作业ID")
    subject: str = Field(..., description="学科")
    status: HomeworkStatus = Field(..., description="状态")
    thumbnail_url: Optional[str] = Field(None, description="缩略图URL")
    created_at: int = Field(..., description="创建时间戳")
    completed_at: Optional[int] = Field(None, description="完成时间戳")
    error_count: int = Field(default=0, description="错题数量")
    total_count: int = Field(default=0, description="总题数")


class QuestionInfo(BaseModel):
    """题目信息."""
    
    question_id: str = Field(..., description="题目ID")
    type: str = Field(..., description="题型")
    content: str = Field(..., description="题目内容")
    student_answer: Optional[str] = Field(None, description="学生答案")
    correct_answer: Optional[str] = Field(None, description="正确答案")
    is_correct: Optional[bool] = Field(None, description="是否正确")
    knowledge_point: Optional[str] = Field(None, description="知识点")
    difficulty: Optional[str] = Field(None, description="难度")


class HomeworkSummaryStats(BaseModel):
    """作业统计摘要."""
    
    total_count: int = Field(..., description="总题数")
    correct_count: int = Field(..., description="正确题数")
    error_count: int = Field(..., description="错题数")
    accuracy_rate: float = Field(..., description="正确率")


class HomeworkDetail(BaseModel):
    """作业详情."""
    
    homework_id: str = Field(..., description="作业ID")
    student_id: str = Field(..., description="学生ID")
    subject: str = Field(..., description="学科")
    status: HomeworkStatus = Field(..., description="状态")
    image_url: Optional[str] = Field(None, description="图片URL")
    parent_description: Optional[str] = Field(None, description="家长描述")
    created_at: int = Field(..., description="创建时间戳")
    completed_at: Optional[int] = Field(None, description="完成时间戳")
    questions: List[QuestionInfo] = Field(default_factory=list, description="题目列表")
    summary: Optional[HomeworkSummaryStats] = None
    diagnosis_result: Optional[Dict[str, Any]] = Field(None, description="诊断结果")
    ocr_result: Optional[Dict[str, Any]] = Field(None, description="OCR识别结果")
    raw_model_response: Optional[str] = Field(None, description="模型原始响应")


# ========== 诊断相关Schema ==========

class DiagnosisLevel(str, Enum):
    """诊断层级."""
    STEP1_CARELESS = "careless"
    STEP1_CONCEPT = "concept"
    STEP1_UNKNOWN = "unknown"
    STEP2_SPECIFIC = "specific"


class DiagnosisOption(BaseModel):
    """诊断选项."""
    
    option_id: str = Field(..., description="选项ID")
    level: int = Field(..., ge=1, le=3, description="层级")
    label: str = Field(..., description="标签")
    description: str = Field(..., description="描述")
    icon: Optional[str] = Field(None, description="图标")


class DiagnosisOptionsResponse(BaseModel):
    """诊断选项响应."""
    
    question_id: str = Field(..., description="题目ID")
    options: List[DiagnosisOption] = Field(..., description="选项列表")


class DiagnosisSelectRequest(BaseModel):
    """提交诊断选择请求."""
    
    level: int = Field(..., ge=1, le=3, description="选择层级: 1/2/3")
    notes: Optional[str] = Field(None, max_length=200, description="补充说明")


class DiagnosisResult(BaseModel):
    """诊断结果数据."""
    
    diagnosis_id: str = Field(..., description="诊断ID")
    question_id: str = Field(..., description="题目ID")
    level: int = Field(..., description="诊断层级")
    analysis: Dict[str, Any] = Field(..., description="分析结果")
    explanation: Dict[str, Any] = Field(..., description="讲解内容")
    variant_ready: bool = Field(default=False, description="变形题是否就绪")


class ErrorAnalysis(BaseModel):
    """错误分析."""
    
    error_type: str = Field(..., description="错误类型")
    root_cause: str = Field(..., description="根因分析")
    knowledge_points: List[str] = Field(default_factory=list, description="相关知识点")


class ExplanationStep(BaseModel):
    """讲解步骤."""
    
    step: int = Field(..., description="步骤序号")
    content: str = Field(..., description="步骤内容")
    highlight: Optional[str] = Field(None, description="高亮部分")


class ExplanationData(BaseModel):
    """讲解数据."""
    
    text: str = Field(..., description="讲解文本")
    steps: List[ExplanationStep] = Field(default_factory=list, description="步骤列表")
    tips: List[str] = Field(default_factory=list, description="提示列表")


class DiagnosisDetailResponse(BaseModel):
    """诊断详情响应."""
    
    diagnosis_id: str = Field(..., description="诊断ID")
    question_id: str = Field(..., description="题目ID")
    level: int = Field(..., description="诊断层级")
    analysis: ErrorAnalysis = Field(..., description="分析结果")
    explanation: ExplanationData = Field(..., description="讲解内容")
    variant_ready: bool = Field(default=False, description="变形题是否就绪")


# ========== 变形题相关Schema ==========

class VariantDifficulty(str, Enum):
    """变形题难度."""
    SAME = "same"
    EASIER = "easier"
    HARDER = "harder"


class VariantGenerateRequest(BaseModel):
    """生成变形题请求."""
    
    question_id: str = Field(..., description="原题ID")
    difficulty: VariantDifficulty = Field(
        default=VariantDifficulty.SAME,
        description="难度调整"
    )
    count: int = Field(default=3, ge=1, le=5, description="生成数量")


class CredibilityRating(BaseModel):
    """可信度评分."""
    
    stars: int = Field(..., ge=1, le=5, description="星级(1-5星)")
    score: float = Field(..., ge=0.0, le=1.0, description="分数(0-1)")
    confidence: str = Field(..., description="置信度等级")


class VariantInfo(BaseModel):
    """变形题信息."""
    
    variant_id: str = Field(..., description="变形题ID")
    content: str = Field(..., description="题目内容")
    type: str = Field(..., description="题型")
    difficulty: str = Field(..., description="难度")
    knowledge_point: str = Field(..., description="知识点")
    credibility: CredibilityRating = Field(..., description="可信度评分")


class VariantGenerateResponse(BaseModel):
    """生成变形题响应."""
    
    variant_set_id: str = Field(..., description="变形题组ID")
    variants: List[VariantInfo] = Field(..., description="变形题列表")


class VariantAnswerItem(BaseModel):
    """变形题答案项."""
    
    variant_id: str = Field(..., description="变形题ID")
    answer: str = Field(..., description="答案")


class VariantAnswerRequest(BaseModel):
    """提交变形题答案请求."""
    
    answers: List[VariantAnswerItem] = Field(..., min_length=1, description="答案列表")
    
    @field_validator('answers')
    @classmethod
    def validate_unique_variant_ids(cls, v):
        """验证variant_id不重复."""
        variant_ids = [item.variant_id for item in v]
        if len(variant_ids) != len(set(variant_ids)):
            raise ValueError("variant_id不能重复")
        return v


class VariantResultItem(BaseModel):
    """变形题结果项."""
    
    variant_id: str = Field(..., description="变形题ID")
    correct: bool = Field(..., description="是否正确")
    answer: str = Field(..., description="学生答案")
    correct_answer: str = Field(..., description="正确答案")


class VariantValidationResponse(BaseModel):
    """变形题验证响应."""
    
    validated: bool = Field(..., description="是否验证完成")
    results: List[VariantResultItem] = Field(..., description="结果列表")
    score: int = Field(..., ge=0, le=100, description="得分")
    passed: bool = Field(..., description="是否通过")


class VariantFeedback(BaseModel):
    """变形题反馈."""
    
    summary: str = Field(..., description="总结")
    encouragement: str = Field(..., description="鼓励语")
    next_steps: List[str] = Field(default_factory=list, description="下一步建议")


class KnowledgeUpdate(BaseModel):
    """知识更新."""
    
    mastered: bool = Field(..., description="是否掌握")
    mastery_level: float = Field(..., ge=0.0, le=1.0, description="掌握度")


class VariantResultResponse(BaseModel):
    """变形题结果完整响应."""
    
    variant_set_id: str = Field(..., description="变形题组ID")
    score: int = Field(..., description="得分")
    passed: bool = Field(..., description="是否通过")
    feedback: VariantFeedback = Field(..., description="反馈")
    knowledge_update: KnowledgeUpdate = Field(..., description="知识更新")


# ========== 统计相关Schema ==========

class KnowledgeNode(BaseModel):
    """知识图谱节点."""
    
    id: str = Field(..., description="节点ID")
    name: str = Field(..., description="节点名称")
    category: str = Field(..., description="分类")
    mastery_level: float = Field(..., ge=0.0, le=1.0, description="掌握度")
    status: str = Field(..., description="状态: mastered/learning/weak")
    x: Optional[float] = Field(None, description="X坐标")
    y: Optional[float] = Field(None, description="Y坐标")


class KnowledgeEdge(BaseModel):
    """知识图谱边."""
    
    source: str = Field(..., description="源节点ID")
    target: str = Field(..., description="目标节点ID")
    relation: str = Field(..., description="关系类型")


class KnowledgeGraphData(BaseModel):
    """知识图谱数据."""
    
    nodes: List[KnowledgeNode] = Field(..., description="节点列表")
    edges: List[KnowledgeEdge] = Field(..., description="边列表")


class KnowledgeGraphResponse(BaseModel):
    """知识图谱响应."""
    
    student_id: str = Field(..., description="学生ID")
    subject: str = Field(..., description="学科")
    graph: KnowledgeGraphData = Field(..., description="图谱数据")
    updated_at: int = Field(..., description="更新时间戳")


class WeakPointItem(BaseModel):
    """薄弱点项."""
    
    rank: int = Field(..., ge=1, description="排名")
    knowledge_point_id: str = Field(..., description="知识点ID")
    name: str = Field(..., description="名称")
    category: str = Field(..., description="分类")
    mastery_level: float = Field(..., ge=0.0, le=1.0, description="掌握度")
    error_count: int = Field(..., description="错误次数")
    last_error_at: int = Field(..., description="最后错误时间戳")
    priority: str = Field(..., description="优先级: high/medium/low")


class WeakPointsResponse(BaseModel):
    """薄弱点响应."""
    
    student_id: str = Field(..., description="学生ID")
    weaknesses: List[WeakPointItem] = Field(..., description="薄弱点列表")
    total: int = Field(..., description="总数")


class TrendDataPoint(BaseModel):
    """趋势数据点."""
    
    date: str = Field(..., description="日期")
    value: float = Field(..., description="值")
    homework_count: int = Field(..., description="作业数量")


class TrendData(BaseModel):
    """趋势数据."""
    
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    data_points: List[TrendDataPoint] = Field(..., description="数据点列表")
    trend_direction: str = Field(..., description="趋势方向: up/down/stable")
    improvement: float = Field(..., description="提升幅度")


class StatisticsTrendResponse(BaseModel):
    """统计趋势响应."""
    
    student_id: str = Field(..., description="学生ID")
    metric: str = Field(..., description="指标")
    period: str = Field(..., description="周期")
    subject: Optional[str] = Field(None, description="学科")
    trend: TrendData = Field(..., description="趋势数据")


class SubjectStat(BaseModel):
    """学科统计."""
    
    subject: str = Field(..., description="学科")
    homework_count: int = Field(..., description="作业数量")
    accuracy_rate: float = Field(..., description="正确率")
    weakness_count: int = Field(..., description="薄弱点数量")


class Achievement(BaseModel):
    """成就."""
    
    id: str = Field(..., description="成就ID")
    name: str = Field(..., description="名称")
    icon: str = Field(..., description="图标")
    earned_at: int = Field(..., description="获得时间戳")


class OverviewStats(BaseModel):
    """概览统计."""
    
    total_homework: int = Field(..., description="总作业数")
    total_questions: int = Field(..., description="总题数")
    accuracy_rate: float = Field(..., description="正确率")
    practice_time: int = Field(..., description="练习时间(分钟)")
    streak_days: int = Field(..., description="连续天数")


class StatisticsOverviewResponse(BaseModel):
    """统计概览响应."""
    
    student_id: str = Field(..., description="学生ID")
    period: str = Field(..., description="周期")
    overview: OverviewStats = Field(..., description="概览数据")
    subject_stats: List[SubjectStat] = Field(default_factory=list, description="学科统计")
    achievements: List[Achievement] = Field(default_factory=list, description="成就列表")


# ========== 通用Schema ==========

class DeleteResponse(BaseModel):
    """删除响应."""
    
    deleted: bool = Field(..., description="是否删除成功")


class HealthCheckResponse(BaseModel):
    """健康检查响应."""
    
    status: str = Field(..., description="状态")
    version: str = Field(..., description="版本")
    timestamp: int = Field(..., description="时间戳")
