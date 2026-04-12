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
_progress_store: dict = {}  # 进度存储: homework_id -> {"stage": "", "progress": 0, "message": ""}


def _update_progress(homework_id: str, stage: str, progress: int, message: str) -> None:
    """更新作业处理进度.
    
    Args:
        homework_id: 作业ID
        stage: 当前阶段
        progress: 进度百分比(0-100)
        message: 进度描述
    """
    _progress_store[homework_id] = {
        "stage": stage,
        "progress": progress,
        "message": message,
        "timestamp": int(datetime.utcnow().timestamp()),
    }
    logger.info("progress_update", homework_id=homework_id, stage=stage, progress=progress)


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



async def _process_diagnosis(homework_id: str, image_path: str, student_id: str, parent_description: Optional[str] = None) -> None:
    """简化版诊断流程: 本地预处理 -> Kimi直接诊断.
    
    Args:
        homework_id: 作业ID
        image_path: 图片路径
        student_id: 学生ID
        parent_description: 家长描述
    """
    import time
    import asyncio
    import json
    import re
    start_time = time.time()
    
    try:
        logger.info("diagnosis_start", homework_id=homework_id, student_id=student_id)
        _update_progress(homework_id, "init", 5, "正在初始化...")
        
        # 创建模型客户端
        try:
            model_client = create_model_client(vision=True)
            logger.info("model_client_ready", provider=settings.active_model_provider)
        except ValueError as e:
            logger.error("api_key_error", error=str(e))
            _homework_store[homework_id]["status"] = HomeworkStatus.FAILED.value
            _homework_store[homework_id]["error_message"] = str(e)
            return
        
        # 步骤1: 本地图像预处理
        logger.info("preprocessing_start", homework_id=homework_id)
        _update_progress(homework_id, "preprocessing", 15, "正在预处理图像...")
        
        try:
            from src.domain.engines.image_preprocessor import ImagePreprocessor, PreprocessOptions
            
            preprocess_options = PreprocessOptions(
                correct_perspective=True,
                correct_rotation=True,
                remove_background=False,
                enhance_contrast=True,
                auto_crop=True,
                content_margin=20,
                white_threshold=240,
            )
            
            preprocessor = ImagePreprocessor(preprocess_options)
            loop = asyncio.get_event_loop()
            prep_result = await loop.run_in_executor(None, preprocessor.process, image_path)
            
            if prep_result.success:
                logger.info("preprocessing_complete", corrections=prep_result.applied_corrections)
                image_base64 = preprocessor.to_base64(prep_result.image)
            else:
                logger.warning("preprocessing_failed", fallback="original")
                with open(image_path, "rb") as f:
                    image_base64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.warning("preprocessing_error", error=str(e), fallback="original")
            with open(image_path, "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode("utf-8")
        
        # 步骤2: Kimi直接诊断（一次API调用完成识别+诊断）
        logger.info("kimi_diagnosis_start", homework_id=homework_id)
        _update_progress(homework_id, "diagnosis", 40, "Kimi正在分析...")
        
        # 构建端到端诊断Prompt
        system_prompt = """你是一位专业的数学作业诊断助手。请仔细分析学生上传的作业图片，完成以下任务：

1. **识别题目内容**：提取图片中的题目文本
2. **识别学生答案**：找到学生写的答案（如果有）
3. **判断对错**：分析学生的答案是否正确
4. **错误诊断**：如果错了，分析错误原因（计算错误/概念错误/粗心等）
5. **给出建议**：提供针对性的学习建议

请严格按照以下JSON格式返回结果：
{
    "content": "识别的题目内容",
    "student_answer": "学生答案",
    "correct_answer": "正确答案",
    "is_correct": true/false,
    "error_type": "错误类型：calculation_error(计算错误)/concept_error(概念错误)/careless(粗心)/none(无错误)",
    "diagnosis": "详细的诊断分析",
    "knowledge_points": ["涉及的知识点1", "知识点2"],
    "suggestion": "给学生的学习建议",
    "confidence": 0.95
}"""

        user_content = "请分析这张作业图片"
        if parent_description:
            user_content += f"\n\n家长描述：{parent_description}"
        
        _update_progress(homework_id, "analyzing", 70, "AI正在深度分析...")
        
        # 调用Kimi视觉模型
        from src.infrastructure.models.base import Message
        
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_content),
        ]
        
        vision_model = settings.kimi.vision_model if settings.active_model_provider == "kimi" else "kimi-k2.5"
        
        model_response = await model_client.complete_with_vision(
            messages=messages,
            images=[image_base64],
            model=vision_model,
            temperature=1.0,  # kimi-k2.5要求
            max_tokens=2048,
        )
        
        _update_progress(homework_id, "parsing", 90, "正在解析结果...")
        
        # 解析模型返回的JSON
        raw_response = model_response.content
        logger.info("kimi_response_received", homework_id=homework_id, response_length=len(raw_response))
        
        # 提取JSON部分
        try:
            # 尝试直接解析
            result = json.loads(raw_response)
        except json.JSONDecodeError:
            # 尝试从markdown代码块中提取
            json_match = re.search(r'```json\s*(.*?)\s*```', raw_response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                # 尝试从文本中提取最像JSON的部分
                json_match = re.search(r'\{[\s\S]*\}', raw_response)
                if json_match:
                    result = json.loads(json_match.group(0))
                else:
                    raise ValueError("无法解析模型返回的JSON")
        
        elapsed_time = time.time() - start_time
        logger.info("diagnosis_complete", homework_id=homework_id, elapsed=elapsed_time)
        
        # 更新进度：完成
        _update_progress(homework_id, "complete", 100, "诊断完成！")
        
        # 保存结果
        if homework_id in _homework_store:
            _homework_store[homework_id]["status"] = HomeworkStatus.COMPLETED.value
            _homework_store[homework_id]["completed_at"] = int(datetime.utcnow().timestamp())
            _homework_store[homework_id]["ocr_result"] = {
                "content": result.get("content", ""),
                "student_answer": result.get("student_answer"),
                "subject": "math",
                "problem_type": "unknown",
                "knowledge_points": result.get("knowledge_points", []),
                "confidence": result.get("confidence", 0.8),
            }
            _homework_store[homework_id]["diagnosis_result"] = {
                "is_correct": result.get("is_correct", True),
                "error_type": result.get("error_type") if not result.get("is_correct") else None,
                "confidence": result.get("confidence", 0.8),
                "diagnosis": result.get("diagnosis", ""),
            }
            _homework_store[homework_id]["questions"] = [
                {
                    "question_id": generate_id("q"),
                    "type": "unknown",
                    "content": result.get("content", "")[:200],
                    "student_answer": result.get("student_answer", "未识别"),
                    "correct_answer": result.get("correct_answer", "待确认"),
                    "is_correct": result.get("is_correct", True),
                    "knowledge_point": result.get("knowledge_points", ["未知"])[0] if result.get("knowledge_points") else "未知",
                    "difficulty": "unknown",
                },
            ]
            _homework_store[homework_id]["error_count"] = 0 if result.get("is_correct", True) else 1
            _homework_store[homework_id]["total_count"] = 1
            _homework_store[homework_id]["raw_model_response"] = raw_response
        
        logger.info("diagnosis_task_complete", homework_id=homework_id, elapsed_time=elapsed_time)
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.exception("diagnosis_failed", homework_id=homework_id, error=str(e))
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
    background_tasks.add_task(_process_diagnosis, homework_id, image_path, student_id, description)
    
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
        diagnosis_result=hw.get("diagnosis_result"),
        ocr_result=hw.get("ocr_result"),
        raw_model_response=hw.get("raw_model_response"),
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


@router.get(
    "/{homework_id}/progress",
    response_model=BaseResponse,
    summary="获取作业处理进度",
    description="查询作业诊断的实时进度",
)
async def get_homework_progress(homework_id: str) -> BaseResponse:
    """获取作业处理进度.
    
    Args:
        homework_id: 作业ID
        
    Returns:
        进度信息
    """
    # 检查作业是否存在
    if homework_id not in _homework_store:
        raise NotFoundException(resource_type="作业", resource_id=homework_id)
    
    # 获取进度
    progress = _progress_store.get(homework_id, {
        "stage": "unknown",
        "progress": 0,
        "message": "等待开始...",
    })
    
    # 获取作业状态
    hw = _homework_store[homework_id]
    status = hw["status"]
    
    # 如果已完成，进度设为100
    if status == HomeworkStatus.COMPLETED.value:
        progress = {
            "stage": "complete",
            "progress": 100,
            "message": "诊断完成！",
        }
    elif status == HomeworkStatus.FAILED.value:
        progress = {
            "stage": "error",
            "progress": 0,
            "message": hw.get("error_message", "诊断失败"),
        }
    
    return BaseResponse(
        code=0,
        message="success",
        data={
            "homework_id": homework_id,
            "status": status,
            "stage": progress["stage"],
            "progress": progress["progress"],
            "message": progress["message"],
        }
    )
