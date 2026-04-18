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
from src.domain.engines.layout_analyzer import LayoutAnalyzer, diagnose_single_question
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
    DiagnosisMode,
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


def _extract_fallback_result(raw_response: str, mode: DiagnosisMode) -> dict:
    """当JSON解析失败时，从文本中提取关键信息构造fallback结果.
    
    Args:
        raw_response: 模型原始响应
        mode: 诊断模式
        
    Returns:
        构造的结果字典
    """
    import re
    
    if mode == DiagnosisMode.EXPLAIN:
        # 提取知识点名称
        knowledge_points = []
        # 匹配 "知识点名称" 或 "name": "xxx"
        name_patterns = [
            r'["\']name["\']\s*:\s*["\']([^"\']+)["\']',
            r'知识点["\']?\s*[:：]\s*["\']?([^"\'\n]+)',
        ]
        for pattern in name_patterns:
            matches = re.findall(pattern, raw_response)
            for match in matches[:3]:  # 最多3个知识点
                if match.strip() and len(match.strip()) > 1:
                    knowledge_points.append({
                        "name": match.strip(),
                        "explanation": "（AI返回格式异常，仅提取到知识点名称）",
                        "examples": [],
                        "common_mistakes": []
                    })
        
        # 如果没有提取到，使用默认
        if not knowledge_points:
            knowledge_points = [{"name": "知识点提取失败", "explanation": "AI返回格式异常，请重试", "examples": [], "common_mistakes": []}]
        
        return {
            "questions": [{
                "question_id": 1,
                "content": "题目内容提取失败",
                "knowledge_points": knowledge_points,
                "learning_suggestion": "请尝试重新上传或选择其他模式"
            }],
            "summary": {"knowledge_summary": "部分内容提取失败", "learning_path": []},
            "confidence": 0.5
        }
    
    elif mode == DiagnosisMode.SOLUTION:
        # 提取解题步骤
        steps = []
        step_pattern = r'(?:步骤|Step)\s*\d+[\.:\s]+([^\n]+)'
        matches = re.findall(step_pattern, raw_response, re.IGNORECASE)
        for match in matches[:5]:
            if match.strip():
                steps.append(match.strip())
        
        if not steps:
            steps = ["解题步骤提取失败，请查看原始响应"]
        
        return {
            "questions": [{
                "question_id": 1,
                "content": "题目内容提取失败",
                "solution_steps": steps,
                "final_answer": "提取失败",
                "key_points": [],
                "formula_used": []
            }],
            "summary": {"total_count": 1, "difficulty_distribution": {"unknown": 1}},
            "confidence": 0.5
        }
    
    return {"questions": [], "confidence": 0.5}


# ========== 多模式提示词定义 ==========

MODE_PROMPTS = {
    DiagnosisMode.DIAGNOSIS: {
        "name": "智能诊断",
        "system_prompt": """你是一位专业的数学作业诊断助手。请仔细分析学生上传的作业图片，完成以下任务：

1. **识别所有题目**：图片中可能有多个题目，请识别每一道题
2. **识别学生答案**：找到每道题学生写的答案（如果有）
3. **判断对错**：分析每道题的答案是否正确
4. **错误诊断**：如果错了，分析错误原因（计算错误/概念错误/粗心等）
5. **给出建议**：提供针对性的学习建议

请严格按照以下JSON格式返回结果：
{
    "questions": [
        {
            "question_id": 1,
            "content": "题目内容",
            "student_answer": "学生答案",
            "correct_answer": "正确答案",
            "is_correct": true/false,
            "error_type": "calculation_error/concept_error/careless/none",
            "diagnosis": "详细的诊断分析",
            "knowledge_points": ["知识点1", "知识点2"],
            "suggestion": "学习建议"
        }
    ],
    "summary": {
        "total_count": 3,
        "correct_count": 2,
        "error_count": 1,
        "overall_suggestion": "总体学习建议"
    },
    "confidence": 0.95
}""",
        "user_template": "请诊断这张作业图片中的所有题目"
    },
    
    DiagnosisMode.SOLUTION: {
        "name": "查看解答",
        "system_prompt": """你是一位数学解题助手。请分析图片中的题目，给出详细的解题步骤。

1. **识别所有题目**：图片中可能有多个题目，请识别每一道题
2. **给出完整解答**：为每道题提供详细的解题步骤
3. **关键思路**：说明解题的关键思路和方法

请严格按照以下JSON格式返回结果：
{
    "questions": [
        {
            "question_id": 1,
            "content": "题目内容",
            "solution_steps": ["步骤1：...", "步骤2：...", "步骤3：..."],
            "final_answer": "最终答案",
            "key_points": ["解题关键点1", "关键点2"],
            "formula_used": ["使用的公式1", "公式2"],
            "difficulty": "easy/medium/hard"
        }
    ],
    "summary": {
        "total_count": 3,
        "difficulty_distribution": {"easy": 1, "medium": 1, "hard": 1}
    },
    "confidence": 0.95
}""",
        "user_template": "请给出这张图片中所有题目的详细解答"
    },
    
    DiagnosisMode.EXPLAIN: {
        "name": "知识点讲解",
        "system_prompt": """你是一位数学知识讲解助手。请针对图片中题目涉及的知识点进行详细讲解。

【重要】你必须严格按以下JSON格式返回，确保JSON格式合法：
- 所有字符串使用双引号"
- 数组和对象不要有尾随逗号
- 不要包含任何注释
- 不要输出markdown代码块标记

JSON格式：
{
    "questions": [
        {
            "question_id": 1,
            "content": "题目内容",
            "knowledge_points": [
                {
                    "name": "知识点名称",
                    "explanation": "详细讲解，包含定义、原理、应用场景",
                    "examples": ["简单例子1", "例子2"],
                    "common_mistakes": ["常见错误1", "错误2"],
                    "related_knowledge": ["相关知识点1", "知识点2"]
                }
            ],
            "learning_suggestion": "针对此题的学习建议"
        }
    ],
    "summary": {
        "knowledge_summary": "涉及的知识点概览",
        "learning_path": ["建议学习路径1", "路径2"]
    },
    "confidence": 0.95
}

请识别图片中的所有题目，为每道题提取知识点并详细讲解。""",
        "user_template": "请讲解这张图片中题目涉及的知识点"
    },
    
    DiagnosisMode.SINGLE: {
        "name": "单题深度分析",
        "system_prompt": """你是一位专业的数学辅导老师。用户通过框选指定了图片中的某一道题，请针对该题进行深度分析。

【重要】框选坐标说明：
- 用户会在图片上框选一个矩形区域来指定要分析的题目
- 坐标格式：{"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.3}
- x, y 是框选区域左上角的相对坐标（0-1范围，相对于原图宽高的比例）
- width, height 是框选区域的相对宽高（0-1范围）
- 你需要根据这些坐标，定位到图片中对应的题目进行分析

任务要求：
1. **定位题目**：根据用户提供的框选坐标，找到对应的题目
2. **完整解析**：只分析该指定题目的内容、学生答案、正误判断
3. **深度讲解**：题目分析、解题步骤、知识点、易错点、拓展延伸

请严格按照以下JSON格式返回结果：
{
    "target_question": {
        "question_id": 1,
        "content": "题目内容（框选区域内的完整题目文字）",
        "student_answer": "学生答案（如果有）",
        "correct_answer": "正确答案"
    },
    "analysis": {
        "difficulty": "easy/medium/hard",
        "estimated_time": "预计解题时间",
        "knowledge_points": ["知识点1", "知识点2"]
    },
    "solution": {
        "steps": ["详细步骤1", "步骤2", "步骤3"],
        "key_insight": "解题关键思路",
        "formula_used": ["公式1", "公式2"]
    },
    "explanation": {
        "core_concept": "核心概念讲解",
        "why_this_works": "为什么这样解",
        "common_mistakes": ["常见错误1", "错误2"],
        "prevention_tips": "避免错误的方法"
    },
    "extension": {
        "similar_problems": ["类似题目思路1", "思路2"],
        "variation_ideas": ["变形方向1", "方向2"],
        "next_level": "进阶挑战"
    },
    "confidence": 0.95
}""",
        "user_template": "请深度分析图片中我框选的这道题目"
    }
}


async def _process_diagnosis(
    homework_id: str, 
    image_path: str, 
    student_id: str, 
    mode: DiagnosisMode = DiagnosisMode.DIAGNOSIS,
    selected_regions: Optional[List[dict]] = None,
    parent_description: Optional[str] = None
) -> None:
    """多模式诊断流程: 本地预处理 -> Kimi直接诊断.
    
    Args:
        homework_id: 作业ID
        image_path: 图片路径
        student_id: 学生ID
        mode: 诊断模式
        selected_regions: 用户框选的题目区域（单题模式用）
        parent_description: 家长描述
    """
    import time
    import asyncio
    import json
    import re
    start_time = time.time()
    
    # 初始化变量（避免后续条件分支中未定义）
    user_content_addition = ""
    
    try:
        logger.info("diagnosis_start", homework_id=homework_id, student_id=student_id, mode=mode.value)
        _update_progress(homework_id, "init", 5, f"正在初始化[{MODE_PROMPTS[mode]['name']}]...")
        
        # 创建模型客户端
        try:
            model_client = create_model_client(vision=True, timeout=180.0)
            logger.info("model_client_ready", provider=settings.active_model_provider)
        except ValueError as e:
            logger.error("api_key_error", error=str(e))
            _homework_store[homework_id]["status"] = HomeworkStatus.FAILED.value
            _homework_store[homework_id]["error_message"] = str(e)
            return
        
        # 智能诊断模式：尝试自动分题逐题诊断（提高多题准确率）
        if mode == DiagnosisMode.DIAGNOSIS:
            success = await _process_per_question_diagnosis(
                homework_id, image_path, student_id, parent_description
            )
            if success:
                return
        
        # 步骤1: 本地图像预处理
        if mode == DiagnosisMode.SINGLE and selected_regions:
            # 单题模式：根据框选坐标裁切题目区域，然后对裁切区域进行预处理
            logger.info("single_mode_crop_start", homework_id=homework_id)
            _update_progress(homework_id, "preprocessing", 15, "单题模式：正在裁切选定区域...")
            
            try:
                import cv2
                from src.domain.engines.image_preprocessor import ImagePreprocessor, PreprocessOptions
                
                # 加载原图
                original_image = cv2.imread(image_path)
                h, w = original_image.shape[:2]
                
                # 获取框选区域（相对坐标）
                region = selected_regions[0]
                x_ratio = region.get('x', 0)
                y_ratio = region.get('y', 0)
                w_ratio = region.get('width', 0)
                h_ratio = region.get('height', 0)
                
                # 转换为像素坐标
                x1 = int(x_ratio * w)
                y1 = int(y_ratio * h)
                x2 = int((x_ratio + w_ratio) * w)
                y2 = int((y_ratio + h_ratio) * h)
                
                # 确保坐标在有效范围内
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                
                # 裁切题目区域
                cropped = original_image[y1:y2, x1:x2]
                
                logger.info("image_cropped", 
                    homework_id=homework_id,
                    original_size=(w, h),
                    crop_box=(x1, y1, x2, y2),
                    cropped_size=(cropped.shape[1], cropped.shape[0]))
                
                # 对裁切区域进行预处理
                preprocess_options = PreprocessOptions(
                    correct_perspective=True,
                    correct_rotation=True,
                    remove_background=False,
                    enhance_contrast=True,
                    auto_crop=False,  # 已经裁切过了，不再自动裁剪
                    content_margin=10,
                    white_threshold=240,
                )
                
                preprocessor = ImagePreprocessor(preprocess_options)
                loop = asyncio.get_event_loop()
                prep_result = await loop.run_in_executor(None, preprocessor.process, cropped)
                
                # 获取最终要传给API的图片
                if prep_result.success:
                    final_image = prep_result.image
                    logger.info("crop_preprocess_complete", 
                        homework_id=homework_id,
                        corrections=prep_result.applied_corrections)
                else:
                    final_image = cropped
                    logger.warning("crop_preprocess_failed", homework_id=homework_id)
                
                # 保存裁切后的图片到 uploads/homework/ 目录（用于调试）
                try:
                    import os
                    upload_dir = os.path.join(settings.UPLOAD_DIR or "./uploads", "homework")
                    os.makedirs(upload_dir, exist_ok=True)
                    # 使用函数开头已导入的 datetime，避免局部变量冲突
                    timestamp_str = datetime.now().strftime('%H%M%S')
                    crop_filename = f"{homework_id}_crop_{timestamp_str}.jpg"
                    crop_path = os.path.join(upload_dir, crop_filename)
                    cv2.imwrite(crop_path, final_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    logger.info("cropped_image_saved", 
                        homework_id=homework_id,
                        path=crop_path,
                        size=(final_image.shape[1], final_image.shape[0]))
                except Exception as save_err:
                    logger.warning("save_cropped_image_failed", 
                        homework_id=homework_id, 
                        error=str(save_err))
                
                # 转换为base64传给API
                image_base64 = preprocessor.to_base64(final_image)
                
                # 更新提示词，告诉AI这是裁切后的单题图片
                user_content_addition = f"\n\n【题目图片说明】这是一道数学题的特写图片，请对这道题进行深度分析。图片中只包含这一道题目。"
                
            except Exception as e:
                logger.error("single_mode_crop_error", homework_id=homework_id, error=str(e))
                # 出错则回退到原图
                with open(image_path, "rb") as f:
                    image_base64 = base64.b64encode(f.read()).decode("utf-8")
                user_content_addition = ""
        else:
            # 其他模式：正常预处理整张图片
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
            
            user_content_addition = ""
        
        # 步骤2: Kimi直接诊断（根据模式选择不同提示词）
        logger.info("kimi_diagnosis_start", homework_id=homework_id, mode=mode.value)
        _update_progress(homework_id, "diagnosis", 40, "Kimi正在分析...")
        
        # 获取模式配置
        mode_config = MODE_PROMPTS[mode]
        system_prompt = mode_config["system_prompt"]
        user_content = mode_config["user_template"]
        
        # 添加用户补充描述
        if parent_description:
            user_content += f"\n\n用户补充说明：{parent_description}"
        
        # 添加单题模式的额外提示（裁切后的题目图片说明）
        if user_content_addition:
            user_content += user_content_addition
        
        # 单题模式（未裁切成功时）：添加框选区域信息作为fallback
        if mode == DiagnosisMode.SINGLE and selected_regions and not user_content_addition:
            region = selected_regions[0]  # 取第一个框选区域
            x, y, w, h = region.get('x', 0), region.get('y', 0), region.get('width', 0), region.get('height', 0)
            user_content += f"\n\n【框选区域坐标】"
            user_content += f"\n- 左上角：x={x:.3f}, y={y:.3f}（相对于原图左上角的比例）"
            user_content += f"\n- 区域大小：宽={w:.3f}, 高={h:.3f}（相对于原图宽高的比例）"
            user_content += f"\n- 该区域位于图片的{('左上' if x < 0.5 and y < 0.5 else '右上' if x >= 0.5 and y < 0.5 else '左下' if x < 0.5 and y >= 0.5 else '右下')}部分"
            user_content += f"\n\n请根据上述坐标，定位到图片中对应位置的题目进行分析。只分析该框选区域内的题目内容，忽略其他题目。"
        
        _update_progress(homework_id, "analyzing", 70, "AI正在深度分析...")
        
        # 调用Kimi视觉模型
        from src.infrastructure.models.base import Message
        
        messages = [
            Message.system(system_prompt),
            Message.user(user_content),
        ]
        
        vision_model = settings.kimi.vision_model if settings.active_model_provider == "kimi" else "kimi-k2.5"
        
        model_response = await model_client.complete_with_vision(
            messages=messages,
            images=[image_base64],
            model=vision_model,
            temperature=1.0,
            max_tokens=4096 if mode == DiagnosisMode.SINGLE else 2048,
        )
        
        _update_progress(homework_id, "parsing", 90, "正在解析结果...")
        
        # 解析模型返回的JSON
        raw_response = model_response.content
        logger.info("kimi_response_received", homework_id=homework_id, response_length=len(raw_response))
        
        # 提取JSON部分
        result = None
        parse_error = None
        
        # 尝试1: 直接解析
        try:
            result = json.loads(raw_response)
        except json.JSONDecodeError as e:
            parse_error = str(e)
        
        # 尝试2: 从markdown代码块中提取
        if result is None:
            try:
                json_match = re.search(r'```json\s*(.*?)\s*```', raw_response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
            except json.JSONDecodeError as e:
                parse_error = str(e)
        
        # 尝试3: 从文本中提取JSON对象
        if result is None:
            try:
                json_match = re.search(r'\{[\s\S]*\}', raw_response)
                if json_match:
                    result = json.loads(json_match.group(0))
            except json.JSONDecodeError as e:
                parse_error = str(e)
        
        # 尝试4: 清理转义字符后解析
        if result is None:
            try:
                cleaned = raw_response.replace('\\n', '\n').replace('\\t', '\t')
                result = json.loads(cleaned)
            except json.JSONDecodeError:
                pass
        
        # 尝试5: 修复常见JSON语法错误（单引号、尾随逗号等）
        if result is None:
            try:
                import re
                # 修复单引号（但避免修复英文缩写中的撇号）
                cleaned = raw_response
                # 将对象/数组中的单引号替换为双引号
                cleaned = re.sub(r"(?<!\\)'", '"', cleaned)
                # 修复尾随逗号（在}或]前的逗号）
                cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)
                # 修复缺少逗号的情况（某些模型会漏掉）
                cleaned = re.sub(r'"\s*"', '", "', cleaned)
                result = json.loads(cleaned)
            except json.JSONDecodeError:
                pass
        
        # 尝试6: 使用更宽松的提取策略（针对讲解模式的复杂结构）
        if result is None and mode == DiagnosisMode.EXPLAIN:
            try:
                # 查找 questions 数组
                questions_match = re.search(r'"questions"\s*:\s*(\[[\s\S]*?\])\s*,\s*"summary"', raw_response, re.DOTALL)
                if questions_match:
                    questions_json = questions_match.group(1)
                    # 清理并解析
                    questions_json = questions_json.replace("'", '"')
                    questions_json = re.sub(r',(\s*[}\]])', r'\1', questions_json)
                    questions = json.loads(questions_json)
                    result = {"questions": questions, "summary": {}, "confidence": 0.8}
            except Exception:
                pass
        
        # 如果所有解析都失败，对于非诊断模式使用fallback
        if result is None:
            if mode in (DiagnosisMode.EXPLAIN, DiagnosisMode.SOLUTION):
                # 使用文本提取构造fallback结果
                logger.warning("json_parse_failed_using_fallback", error=parse_error, mode=mode.value)
                result = _extract_fallback_result(raw_response, mode)
            else:
                logger.error("json_parse_failed", error=parse_error, response_preview=raw_response[:200])
                raise ValueError(f"无法解析模型返回的JSON: {parse_error}")
        
        elapsed_time = time.time() - start_time
        logger.info("diagnosis_complete", homework_id=homework_id, elapsed=elapsed_time, mode=mode.value)
        
        # 更新进度：完成
        _update_progress(homework_id, "complete", 100, "诊断完成！")
        
        # 保存结果
        if homework_id in _homework_store:
            _homework_store[homework_id]["status"] = HomeworkStatus.COMPLETED.value
            _homework_store[homework_id]["completed_at"] = int(datetime.utcnow().timestamp())
            _homework_store[homework_id]["diagnosis_mode"] = mode.value
            
            # 根据模式存储不同的结果格式
            if mode == DiagnosisMode.SINGLE:
                # 单题模式：直接存储深度分析结果
                _homework_store[homework_id]["single_analysis"] = result
                _homework_store[homework_id]["ocr_result"] = {
                    "content": result.get("target_question", {}).get("content", ""),
                    "student_answer": result.get("target_question", {}).get("student_answer"),
                    "subject": "math",
                    "knowledge_points": result.get("analysis", {}).get("knowledge_points", []),
                    "confidence": result.get("confidence", 0.8),
                }
                # 提取知识点（支持字符串或字典格式）
                analysis_kps = result.get("analysis", {}).get("knowledge_points", [])
                if analysis_kps:
                    first_kp = analysis_kps[0]
                    knowledge_point = first_kp.get("name") if isinstance(first_kp, dict) else str(first_kp)
                else:
                    knowledge_point = "未知"
                
                _homework_store[homework_id]["questions"] = [
                    {
                        "question_id": generate_id("q"),
                        "type": "unknown",
                        "content": result.get("target_question", {}).get("content", "")[:200],
                        "student_answer": result.get("target_question", {}).get("student_answer", "未识别"),
                        "correct_answer": result.get("target_question", {}).get("correct_answer", "待确认"),
                        "is_correct": None,  # 单题模式不提供对错判断
                        "knowledge_point": knowledge_point,
                        "difficulty": result.get("analysis", {}).get("difficulty", "unknown"),
                    }
                ]
                _homework_store[homework_id]["error_count"] = 0
                _homework_store[homework_id]["total_count"] = 1
            else:
                # 多题模式：提取questions列表
                questions_data = result.get("questions", [])
                summary = result.get("summary", {})
                
                _homework_store[homework_id]["ocr_result"] = {
                    "content": f"共识别 {len(questions_data)} 道题目",
                    "subject": "math",
                    "knowledge_points": [],
                    "confidence": result.get("confidence", 0.8),
                }
                
                # 转换题目列表
                def _extract_knowledge_point(q):
                    """提取知识点名称（支持字符串或字典格式）."""
                    kps = q.get("knowledge_points", [])
                    if not kps:
                        return "未知"
                    first_kp = kps[0]
                    # 讲解模式下是字典，取 name 字段
                    if isinstance(first_kp, dict):
                        return first_kp.get("name", "未知")
                    # 诊断/解答模式下是字符串
                    return str(first_kp)
                
                _homework_store[homework_id]["questions"] = [
                    {
                        "question_id": generate_id("q"),
                        "type": "unknown",
                        "content": q.get("content", "")[:200],
                        "student_answer": q.get("student_answer", "未识别") if mode == DiagnosisMode.DIAGNOSIS else q.get("final_answer", "见解答"),
                        "correct_answer": q.get("correct_answer", "待确认") if mode == DiagnosisMode.DIAGNOSIS else q.get("final_answer", "见解答"),
                        "is_correct": q.get("is_correct", True) if mode == DiagnosisMode.DIAGNOSIS else None,
                        "knowledge_point": _extract_knowledge_point(q),
                        "difficulty": q.get("difficulty", "unknown"),
                    }
                    for q in questions_data
                ]
                
                # 诊断模式特有的统计
                if mode == DiagnosisMode.DIAGNOSIS:
                    _homework_store[homework_id]["diagnosis_result"] = {
                        "mode": mode.value,
                        "summary": summary,
                        "questions_detail": questions_data,
                    }
                    _homework_store[homework_id]["error_count"] = summary.get("error_count", 0)
                    _homework_store[homework_id]["total_count"] = summary.get("total_count", len(questions_data))
                else:
                    # 解答模式/讲解模式
                    _homework_store[homework_id]["solution_result"] = {
                        "mode": mode.value,
                        "summary": summary,
                        "questions_detail": questions_data,
                    } if mode == DiagnosisMode.SOLUTION else {
                        "mode": mode.value,
                        "summary": result.get("summary", {}),
                        "questions_detail": questions_data,
                    }
                    _homework_store[homework_id]["total_count"] = len(questions_data)
                    _homework_store[homework_id]["error_count"] = 0
            
            _homework_store[homework_id]["raw_model_response"] = raw_response
        
        logger.info("diagnosis_task_complete", homework_id=homework_id, elapsed_time=elapsed_time, mode=mode.value)
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.exception("diagnosis_failed", homework_id=homework_id, error=str(e))
        if homework_id in _homework_store:
            _homework_store[homework_id]["status"] = HomeworkStatus.FAILED.value
            _homework_store[homework_id]["error_message"] = str(e)


async def _process_per_question_diagnosis(
    homework_id: str,
    image_path: str,
    student_id: str,
    parent_description: Optional[str] = None,
) -> bool:
    """智能诊断模式：自动检测题目并逐题裁切诊断.

    返回 True 表示成功完成逐题诊断，False 表示 fallback 到整图诊断。
    """
    import asyncio
    import cv2
    import time
    from src.domain.engines.image_preprocessor import ImagePreprocessor, PreprocessOptions

    start_time = time.time()

    try:
        logger.info("per_question_diagnosis_start", homework_id=homework_id)
        _update_progress(homework_id, "init", 5, "正在初始化[智能诊断]...")

        # 创建模型客户端
        try:
            model_client = create_model_client(vision=True, timeout=180.0)
        except ValueError as e:
            logger.error("api_key_error", error=str(e))
            return False

        # 步骤1: 版面分析（检测题目区域）
        _update_progress(homework_id, "layout_analysis", 10, "正在识别题目区域...")
        analyzer = LayoutAnalyzer(timeout=30.0)
        regions = await analyzer.detect_questions(image_path)

        # 如果检测失败或只有1道题，fallback 到整图诊断
        if not regions or len(regions) <= 1:
            logger.info(
                "layout_analysis_fallback",
                homework_id=homework_id,
                region_count=len(regions) if regions else 0,
            )
            return False

        logger.info(
            "layout_analysis_success",
            homework_id=homework_id,
            question_count=len(regions),
        )

        # 步骤2: 加载原图并逐题裁切
        _update_progress(homework_id, "preprocessing", 15, f"正在裁切 {len(regions)} 道题目...")
        original_image = cv2.imread(image_path)
        if original_image is None:
            logger.error("cv2_read_failed", homework_id=homework_id)
            return False

        h, w = original_image.shape[:2]
        preprocess_options = PreprocessOptions(
            correct_perspective=True,
            correct_rotation=True,
            remove_background=False,
            enhance_contrast=True,
            auto_crop=False,
            content_margin=10,
            white_threshold=240,
        )
        preprocessor = ImagePreprocessor(preprocess_options)
        loop = asyncio.get_event_loop()

        question_images = []
        for region in regions:
            bbox = region["bbox"]
            x1 = int(bbox["x"] * w)
            y1 = int(bbox["y"] * h)
            x2 = int((bbox["x"] + bbox["width"]) * w)
            y2 = int((bbox["y"] + bbox["height"]) * h)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            cropped = original_image[y1:y2, x1:x2]
            if cropped.size == 0:
                continue

            prep_result = await loop.run_in_executor(None, preprocessor.process, cropped)
            final_image = prep_result.image if prep_result.success else cropped
            image_base64 = preprocessor.to_base64(final_image)

            question_images.append({
                "question_id": region["question_id"],
                "image_base64": image_base64,
            })

        if not question_images:
            logger.warning("no_valid_question_images", homework_id=homework_id)
            return False

        # 步骤3: 逐题并行诊断（限制并发数避免限流）
        vision_model = settings.kimi.vision_model if settings.active_model_provider == "kimi" else "kimi-k2.5"
        semaphore = asyncio.Semaphore(3)
        total = len(question_images)

        async def _diagnose_with_semaphore(idx: int, q: dict):
            async with semaphore:
                progress = 20 + int((idx / total) * 65)
                _update_progress(
                    homework_id, "diagnosing", progress,
                    f"正在分析第 {q['question_id']} 题 ({idx + 1}/{total})..."
                )
                result = await diagnose_single_question(
                    image_base64=q["image_base64"],
                    question_id=q["question_id"],
                    model_client=model_client,
                    vision_model=vision_model,
                    parent_description=parent_description,
                )
                return result

        tasks = [
            _diagnose_with_semaphore(i, q)
            for i, q in enumerate(question_images)
        ]
        results = await asyncio.gather(*tasks)

        # 步骤4: 合并结果
        _update_progress(homework_id, "merging", 90, "正在合并诊断结果...")

        valid_results = [r for r in results if r is not None]
        if not valid_results:
            logger.warning("all_per_question_diagnosis_failed", homework_id=homework_id)
            return False

        # 组装为 DIAGNOSIS 模式输出格式
        questions_data = []
        error_count = 0
        for r in valid_results:
            is_correct = r.get("is_correct", True)
            if not is_correct:
                error_count += 1
            questions_data.append(r)

        summary = {
            "total_count": len(questions_data),
            "correct_count": len(questions_data) - error_count,
            "error_count": error_count,
            "overall_suggestion": f"共{len(questions_data)}题，错{error_count}题。请重点关注错题涉及的知识点。",
        }

        elapsed_time = time.time() - start_time
        logger.info(
            "per_question_diagnosis_complete",
            homework_id=homework_id,
            elapsed=elapsed_time,
            total=len(questions_data),
            errors=error_count,
        )

        _update_progress(homework_id, "complete", 100, "诊断完成！")

        # 保存结果
        if homework_id in _homework_store:
            _homework_store[homework_id]["status"] = HomeworkStatus.COMPLETED.value
            _homework_store[homework_id]["completed_at"] = int(datetime.utcnow().timestamp())
            _homework_store[homework_id]["diagnosis_mode"] = DiagnosisMode.DIAGNOSIS.value
            _homework_store[homework_id]["diagnosis_result"] = {
                "mode": DiagnosisMode.DIAGNOSIS.value,
                "summary": summary,
                "questions_detail": questions_data,
            }
            _homework_store[homework_id]["ocr_result"] = {
                "content": f"共识别 {len(questions_data)} 道题目（逐题裁切诊断）",
                "subject": "math",
                "knowledge_points": [],
                "confidence": 0.95,
            }

            def _extract_knowledge_point(q):
                kps = q.get("knowledge_points", [])
                if not kps:
                    return "未知"
                first_kp = kps[0]
                return first_kp.get("name") if isinstance(first_kp, dict) else str(first_kp)

            _homework_store[homework_id]["questions"] = [
                {
                    "question_id": generate_id("q"),
                    "type": "unknown",
                    "content": q.get("content", "")[:200],
                    "student_answer": q.get("student_answer", "未识别"),
                    "correct_answer": q.get("correct_answer", "待确认"),
                    "is_correct": q.get("is_correct", True),
                    "knowledge_point": _extract_knowledge_point(q),
                    "difficulty": q.get("difficulty", "unknown"),
                }
                for q in questions_data
            ]
            _homework_store[homework_id]["error_count"] = error_count
            _homework_store[homework_id]["total_count"] = len(questions_data)

        return True

    except Exception as e:
        logger.exception("per_question_diagnosis_error", homework_id=homework_id, error=str(e))
        return False


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
    mode: DiagnosisMode = Form(DiagnosisMode.DIAGNOSIS, description="诊断模式: diagnosis/solution/explain/single"),
    selected_regions: Optional[str] = Form(None, description="框选区域JSON（单题模式用）"),
    image: UploadFile = File(..., description="作业照片"),
) -> BaseResponse:
    """上传作业.
    
    接收作业图片上传，返回作业ID，并触发异步诊断流程。
    
    Args:
        background_tasks: 后台任务
        student_id: 学生ID
        subject: 学科
        description: 家长描述（可选，最多140字）
        mode: 诊断模式（可选，默认diagnosis）
        selected_regions: 用户框选的题目区域JSON（单题模式用）
        image: 作业照片（支持jpg/png/webp，最大10MB）
        
    Returns:
        包含作业ID的响应
    """
    import json
    
    logger.info(
        "upload_homework",
        student_id=student_id,
        subject=subject.value,
        mode=mode.value,
        has_description=bool(description),
        has_regions=bool(selected_regions),
        filename=image.filename,
    )
    
    # 验证图片
    _validate_image(image)
    
    # 解析框选区域
    regions = None
    if selected_regions:
        try:
            regions = json.loads(selected_regions)
        except json.JSONDecodeError:
            raise ValidationException(message="框选区域格式错误")
    
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
        "diagnosis_mode": mode.value,
        "created_at": now,
        "completed_at": None,
        "error_count": 0,
        "total_count": 0,
        "questions": [],
    }
    
    # 启动后台诊断任务
    background_tasks.add_task(_process_diagnosis, homework_id, image_path, student_id, mode, regions, description)
    
    logger.info(
        "homework_created",
        homework_id=homework_id,
        student_id=student_id,
        mode=mode.value,
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
        diagnosis_result=hw.get("diagnosis_result") or hw.get("solution_result") or hw.get("single_analysis"),
        ocr_result=hw.get("ocr_result"),
        raw_model_response=hw.get("raw_model_response"),
    )
    
    # 添加诊断模式信息
    result_data = detail.model_dump()
    result_data["diagnosis_mode"] = hw.get("diagnosis_mode", "diagnosis")
    
    return BaseResponse(
        code=0,
        message="success",
        data=result_data
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
