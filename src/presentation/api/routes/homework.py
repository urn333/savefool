"""作业管理路由.

提供作业上传、查询、管理等API接口.
"""

import os
import shutil
import uuid
import base64
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.background import BackgroundTasks

from src.infrastructure.config import get_settings
from src.infrastructure.logging import get_logger
from src.infrastructure.models import create_model_client
from src.domain.engines.ocr_engine import OCREngine, OCROptions
from src.domain.engines.model_schedulers import ModelAScheduler, SchedulerConfig, ParsedProblem
from src.presentation.api.exceptions import (
    BusinessException,
    ErrorCode,
    NotFoundException,
    ValidationException,
)
from src.presentation.api.schemas import (
    BaseResponse,
    DeleteResponse,
    HomeworkDetail,
    HomeworkStatus,
    HomeworkSummary,
    HomeworkSummaryStats,
    HomeworkUploadResponse,
    PaginationData,
    PaginatedResponse,
    QuestionInfo,
    SubjectType,
)
from src.domain.models.base import generate_id

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter()

# 内存存储（实际项目应使用数据库）
_homework_store: dict = {}
_processing_tasks: dict = {}


# 支持的图片格式
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB


def _save_upload_file(upload_file: UploadFile, destination: str) -> str:
    """保存上传的文件.
    
    Args:
        upload_file: 上传的文件
        destination: 目标目录
        
    Returns:
        保存的文件路径
    """
    os.makedirs(destination, exist_ok=True)
    file_ext = os.path.splitext(upload_file.filename)[1] or ".jpg"
    filename = f"{uuid.uuid4().hex}{file_ext}"
    filepath = os.path.join(destination, filename)
    
    with open(filepath, "wb") as f:
        shutil.copyfileobj(upload_file.file, f)
    
    return filepath


def _validate_image(file: UploadFile) -> None:
    """验证图片文件.
    
    Args:
        file: 上传的文件
        
    Raises:
        ValidationException: 验证失败
    """
    # 检查文件类型
    content_type = file.content_type or ""
    if content_type not in SUPPORTED_IMAGE_TYPES:
        raise ValidationException(
            message=f"不支持的图片格式: {content_type}，请使用jpg、png或webp格式"
        )
    
    # 检查文件大小
    file.file.seek(0, 2)  # 移动到文件末尾
    file_size = file.file.tell()
    file.file.seek(0)  # 重置文件指针
    
    if file_size > MAX_IMAGE_SIZE:
        raise ValidationException(
            message=f"图片大小超过限制: {file_size / 1024 / 1024:.2f}MB > 10MB"
        )


async def _process_diagnosis(homework_id: str, image_path: str, student_id: str) -> None:
    """异步处理诊断流程.
    
    使用真实的大模型进行OCR识别和诊断。
    
    Args:
        homework_id: 作业ID
        image_path: 图片路径
        student_id: 学生ID
    """
    import time
    start_time = time.time()
    
    try:
        logger.info(
            "diagnosis_task_start",
            homework_id=homework_id,
            student_id=student_id,
            image_path=image_path,
        )
        
        # 检查API Key是否配置
        try:
            model_client = create_model_client()
            logger.info("model_client_created", provider=settings.active_model_provider)
        except ValueError as e:
            logger.error("api_key_not_configured", error=str(e))
            _homework_store[homework_id]["status"] = HomeworkStatus.FAILED.value
            _homework_store[homework_id]["error_message"] = str(e)
            return
        
        # 创建OCR引擎
        ocr_engine = OCREngine(model_client)
        
        # 读取图片并转换为base64
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        
        logger.info("ocr_recognition_start", homework_id=homework_id)
        
        # 执行OCR识别
        ocr_result = await ocr_engine.recognize(
            image_base64=image_base64,
            options=OCROptions(
                detect_subject=True,
                detect_problem_type=True,
                extract_student_answer=True,
                language_hint="zh",
            ),
        )
        
        if not ocr_result.success:
            logger.error("ocr_failed", homework_id=homework_id, error=ocr_result.error)
            _homework_store[homework_id]["status"] = HomeworkStatus.FAILED.value
            _homework_store[homework_id]["error_message"] = f"OCR识别失败: {ocr_result.error}"
            return
        
        logger.info(
            "ocr_complete",
            homework_id=homework_id,
            subject=ocr_result.subject,
            problem_type=ocr_result.problem_type,
            confidence=ocr_result.confidence,
        )
        
        # 创建模型调度器进行详细诊断
        scheduler = ModelAScheduler(
            client=model_client,
            config=SchedulerConfig(
                model_id="model_a",
                model_name=settings.kimi.model if settings.active_model_provider == "kimi" else settings.openai.model,
                temperature=0.3,
                max_tokens=2048,
                timeout=30.0,
                weight=0.4,
            ),
        )
        
        # 解析题目
        parsed_problem = ocr_result.to_parsed_problem()
        
        logger.info("model_diagnosis_start", homework_id=homework_id)
        
        # 执行模型诊断
        model_result = await scheduler.schedule(
            problem=parsed_problem,
            images=[image_base64],
        )
        
        elapsed_time = time.time() - start_time
        
        logger.info(
            "diagnosis_complete",
            homework_id=homework_id,
            is_correct=model_result.is_correct,
            error_type=model_result.error_type.value if model_result.error_type else None,
            confidence=model_result.confidence,
            elapsed_time=elapsed_time,
        )
        
        # 更新作业状态
        if homework_id in _homework_store:
            _homework_store[homework_id]["status"] = HomeworkStatus.COMPLETED.value
            _homework_store[homework_id]["completed_at"] = int(datetime.utcnow().timestamp())
            _homework_store[homework_id]["ocr_result"] = {
                "content": ocr_result.content,
                "student_answer": ocr_result.student_answer,
                "subject": ocr_result.subject,
                "problem_type": ocr_result.problem_type,
                "knowledge_points": ocr_result.knowledge_points,
                "confidence": ocr_result.confidence,
            }
            _homework_store[homework_id]["diagnosis_result"] = {
                "is_correct": model_result.is_correct,
                "error_type": model_result.error_type.value if model_result.error_type else None,
                "confidence": model_result.confidence,
                "diagnosis": model_result.diagnosis,
            }
            _homework_store[homework_id]["questions"] = [
                {
                    "question_id": generate_id("q"),
                    "type": ocr_result.problem_type,
                    "content": ocr_result.content[:200] if ocr_result.content else "未知题目",
                    "student_answer": ocr_result.student_answer or "未识别",
                    "correct_answer": "待确认",  # 大模型未提供标准答案
                    "is_correct": model_result.is_correct,
                    "knowledge_point": ocr_result.knowledge_points[0] if ocr_result.knowledge_points else "未知",
                    "difficulty": "unknown",
                },
            ]
            _homework_store[homework_id]["error_count"] = 0 if model_result.is_correct else 1
            _homework_store[homework_id]["total_count"] = 1
            _homework_store[homework_id]["raw_model_response"] = model_result.diagnosis.get("raw_response", "")
        
        logger.info(
            "diagnosis_task_complete",
            homework_id=homework_id,
            elapsed_time=elapsed_time,
        )
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.exception(
            "diagnosis_task_failed",
            homework_id=homework_id,
            error=str(e),
            elapsed_time=elapsed_time,
        )
        if homework_id in _homework_store:
            _homework_store[homework_id]["status"] = HomeworkStatus.FAILED.value
            _homework_store[homework_id]["error_message"] = str(e)


@router.post(
    "",
    response_model=BaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="上传作业",
    description="上传作业照片和家长描述，触发异步诊断流程",
)
async def upload_homework(
    background_tasks: BackgroundTasks,
    student_id: str = Form(..., description="学生ID"),
    subject: SubjectType = Form(..., description="学科"),
    description: Optional[str] = Form(None, max_length=140, description="家长描述"),
    image: UploadFile = File(..., description="作业照片"),
) -> BaseResponse:
    """上传作业.
    
    接收作业图片上传，返回作业ID，并触发异步诊断流程。
    
    Args:
        background_tasks: 后台任务
        student_id: 学生ID
        subject: 学科
        description: 家长描述（可选，最多140字）
        image: 作业照片（支持jpg/png/webp，最大10MB）
        
    Returns:
        包含作业ID的响应
    """
    logger.info(
        "upload_homework",
        student_id=student_id,
        subject=subject.value,
        has_description=bool(description),
        filename=image.filename,
    )
    
    # 验证图片
    _validate_image(image)
    
    # 生成作业ID
    homework_id = generate_id("hw")
    
    # 保存图片
    upload_dir = os.path.join(settings.UPLOAD_DIR or "./uploads", "homework")
    image_path = _save_upload_file(image, upload_dir)
    
    # 创建作业记录
    now = int(datetime.utcnow().timestamp())
    _homework_store[homework_id] = {
        "homework_id": homework_id,
        "student_id": student_id,
        "subject": subject.value,
        "status": HomeworkStatus.PROCESSING.value,
        "image_url": f"/uploads/homework/{os.path.basename(image_path)}",
        "parent_description": description,
        "created_at": now,
        "completed_at": None,
        "error_count": 0,
        "total_count": 0,
        "questions": [],
    }
    
    # 启动后台诊断任务
    background_tasks.add_task(_process_diagnosis, homework_id, image_path, student_id)
    
    logger.info(
        "homework_created",
        homework_id=homework_id,
        student_id=student_id,
    )
    
    return BaseResponse(
        code=0,
        message="success",
        data=HomeworkUploadResponse(
            homework_id=homework_id,
            status=HomeworkStatus.PROCESSING,
            created_at=now,
            estimated_time=30,
        ).model_dump()
    )


@router.get(
    "",
    response_model=BaseResponse,
    summary="获取作业列表",
    description="获取学生作业列表，支持分页和筛选",
)
async def list_homework(
    student_id: str = Query(..., description="学生ID"),
    subject: Optional[SubjectType] = Query(None, description="学科筛选"),
    status: Optional[HomeworkStatus] = Query(None, description="状态筛选"),
    cursor: Optional[str] = Query(None, description="分页游标"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
) -> BaseResponse:
    """获取作业列表.
    
    Args:
        student_id: 学生ID
        subject: 学科筛选（可选）
        status: 状态筛选（可选）
        cursor: 分页游标（可选）
        limit: 每页数量（默认20，最大100）
        
    Returns:
        作业列表
    """
    # 筛选作业
    filtered = [
        hw for hw in _homework_store.values()
        if hw["student_id"] == student_id
    ]
    
    if subject:
        filtered = [hw for hw in filtered if hw["subject"] == subject.value]
    
    if status:
        filtered = [hw for hw in filtered if hw["status"] == status.value]
    
    # 按创建时间倒序
    filtered.sort(key=lambda x: x["created_at"], reverse=True)
    
    # 游标分页（简化实现）
    start_idx = 0
    if cursor:
        try:
            start_idx = int(cursor)
        except ValueError:
            pass
    
    items = filtered[start_idx:start_idx + limit]
    has_more = len(filtered) > start_idx + limit
    next_cursor = str(start_idx + limit) if has_more else None
    
    # 转换为响应模型
    summaries = [
        HomeworkSummary(
            homework_id=hw["homework_id"],
            subject=hw["subject"],
            status=HomeworkStatus(hw["status"]),
            thumbnail_url=hw.get("image_url"),
            created_at=hw["created_at"],
            completed_at=hw.get("completed_at"),
            error_count=hw.get("error_count", 0),
            total_count=hw.get("total_count", 0),
        ).model_dump()
        for hw in items
    ]
    
    return BaseResponse(
        code=0,
        message="success",
        data={
            "list": summaries,
            "pagination": PaginationData(
                has_more=has_more,
                next_cursor=next_cursor,
                total=len(filtered),
            ).model_dump(),
        }
    )


@router.get(
    "/{homework_id}",
    response_model=BaseResponse,
    summary="获取作业详情",
    description="获取作业详细信息和诊断结果",
)
async def get_homework(homework_id: str) -> BaseResponse:
    """获取作业详情.
    
    Args:
        homework_id: 作业ID
        
    Returns:
        作业详情
        
    Raises:
        NotFoundException: 作业不存在
    """
    if homework_id not in _homework_store:
        raise NotFoundException(resource_type="作业", resource_id=homework_id)
    
    hw = _homework_store[homework_id]
    
    # 构建统计摘要
    summary = None
    if hw.get("total_count", 0) > 0:
        correct_count = hw["total_count"] - hw.get("error_count", 0)
        summary = HomeworkSummaryStats(
            total_count=hw["total_count"],
            correct_count=correct_count,
            error_count=hw.get("error_count", 0),
            accuracy_rate=correct_count / hw["total_count"],
        )
    
    # 构建题目列表
    questions = [
        QuestionInfo(**q).model_dump()
        for q in hw.get("questions", [])
    ]
    
    detail = HomeworkDetail(
        homework_id=hw["homework_id"],
        student_id=hw["student_id"],
        subject=hw["subject"],
        status=HomeworkStatus(hw["status"]),
        image_url=hw.get("image_url"),
        parent_description=hw.get("parent_description"),
        created_at=hw["created_at"],
        completed_at=hw.get("completed_at"),
        questions=questions,
        summary=summary,
    )
    
    return BaseResponse(
        code=0,
        message="success",
        data=detail.model_dump()
    )


@router.delete(
    "/{homework_id}",
    response_model=BaseResponse,
    summary="删除作业",
    description="删除指定作业",
)
async def delete_homework(homework_id: str) -> BaseResponse:
    """删除作业.
    
    Args:
        homework_id: 作业ID
        
    Returns:
        删除结果
        
    Raises:
        NotFoundException: 作业不存在
    """
    if homework_id not in _homework_store:
        raise NotFoundException(resource_type="作业", resource_id=homework_id)
    
    del _homework_store[homework_id]
    
    logger.info("homework_deleted", homework_id=homework_id)
    
    return BaseResponse(
        code=0,
        message="success",
        data=DeleteResponse(deleted=True).model_dump()
    )
