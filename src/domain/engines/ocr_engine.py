"""OCR识别引擎.

使用GPT-4V进行图片识别，提取题目文本、学生答案等信息。
"""

import base64
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.infrastructure.logging import get_logger
from src.infrastructure.models.base import Message, ModelClient, ModelResponse
from src.domain.engines.model_schedulers import ParsedProblem

logger = get_logger(__name__)


class SubjectType(str, Enum):
    """学科类型."""
    MATH = "math"
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"
    UNKNOWN = "unknown"


class ProblemType(str, Enum):
    """题目类型."""
    CHOICE = "choice"           # 选择题
    FILL_BLANK = "fill_blank"   # 填空题
    CALCULATION = "calculation" # 计算题
    APPLICATION = "application" # 应用题
    PROOF = "proof"             # 证明题
    UNKNOWN = "unknown"


@dataclass
class OCROptions:
    """OCR选项.
    
    Attributes:
        detect_subject: 是否自动检测学科
        detect_problem_type: 是否自动检测题目类型
        extract_student_answer: 是否提取学生答案
        language_hint: 语言提示(zh/en)
        preprocess: 是否进行图像预处理
        preprocess_options: 预处理选项
    """
    detect_subject: bool = True
    detect_problem_type: bool = True
    extract_student_answer: bool = True
    language_hint: str = "zh"
    preprocess: bool = True
    preprocess_options: Optional[Dict[str, Any]] = None


@dataclass
class OCRResult:
    """OCR识别结果.
    
    Attributes:
        success: 是否成功
        content: 题目文本内容
        student_answer: 学生答案
        subject: 学科类型
        problem_type: 题目类型
        knowledge_points: 识别出的知识点
        confidence: 识别置信度
        raw_response: 原始响应
        error: 错误信息
    """
    success: bool = False
    content: str = ""
    student_answer: Optional[str] = None
    subject: str = "unknown"
    problem_type: str = "unknown"
    knowledge_points: List[str] = field(default_factory=list)
    confidence: float = 0.0
    raw_response: str = ""
    error: Optional[str] = None
    
    def to_parsed_problem(self) -> ParsedProblem:
        """转换为ParsedProblem对象.
        
        Returns:
            解析后的题目对象
        """
        return ParsedProblem(
            content=self.content,
            student_answer=self.student_answer,
            subject=self.subject if self.subject != "unknown" else None,
            problem_type=self.problem_type if self.problem_type != "unknown" else None,
            knowledge_points=self.knowledge_points,
        )


class OCREngine:
    """OCR识别引擎.
    
    使用GPT-4V进行图片识别，提取题目文本、学生答案等信息。
    支持图像预处理（透视校正、对比度增强等）以提高识别准确率。
    
    Example:
        >>> engine = OCREngine(client)
        >>> result = await engine.recognize("/path/to/image.jpg")
        >>> print(result.content)
    """
    
    SYSTEM_PROMPT = """你是一位专业的OCR识别专家。请仔细识别图片中的题目内容，并按以下JSON格式输出：

{
    "content": "题目文本内容（包含题干和要求）",
    "student_answer": "学生填写的答案（如果有）",
    "subject": "学科类型（math/physics/chemistry/unknown）",
    "problem_type": "题目类型（choice/fill_blank/calculation/application/proof/unknown）",
    "knowledge_points": ["识别出的知识点1", "知识点2"],
    "confidence": 0.0-1.0
}

注意事项：
1. 保留原题的数学公式和符号，用LaTeX格式表示
2. 区分题目内容和学生的答题内容
3. 如果无法识别某些内容，标记为[无法识别]
4. 置信度表示你对识别结果的确信程度"""
    
    def __init__(
        self,
        client: ModelClient,
        default_options: Optional[OCROptions] = None,
    ):
        """初始化OCR引擎.
        
        Args:
            client: 模型客户端(需支持视觉)
            default_options: 默认OCR选项
        """
        self.client = client
        self.default_options = default_options or OCROptions()
        self.logger = get_logger(__name__)
        
        # 初始化图像预处理器
        self._preprocessor = None
        if self.default_options.preprocess:
            try:
                from src.domain.engines.image_preprocessor import (
                    ImagePreprocessor, PreprocessOptions
                )
                prep_opts = PreprocessOptions(
                    **(self.default_options.preprocess_options or {})
                )
                self._preprocessor = ImagePreprocessor(prep_opts)
                self.logger.info("ocr_preprocessor_initialized")
            except ImportError as e:
                self.logger.warning("ocr_preprocessor_import_failed", error=str(e))
    
    async def recognize(
        self,
        image_path: Union[str, Path, str],
        subject_hint: Optional[str] = None,
        options: Optional[OCROptions] = None,
    ) -> OCRResult:
        """识别图片中的题目.
        
        支持自动图像预处理以提高识别准确率。
        
        Args:
            image_path: 图片路径或base64编码的图像数据
            subject_hint: 学科提示(可选)
            options: OCR选项
            
        Returns:
            OCR识别结果
        """
        opts = options or self.default_options
        
        self.logger.info(
            "ocr_start",
            image_path=str(image_path)[:50] if not isinstance(image_path, str) or len(image_path) < 100 else "base64_data",
            subject_hint=subject_hint,
            preprocess_enabled=opts.preprocess,
        )
        
        try:
            # 判断是否已经是base64数据
            if isinstance(image_path, str) and len(image_path) > 1000:
                # 可能是base64数据
                image_data = image_path
                self.logger.debug("using_provided_base64_data")
            else:
                # 文件路径，进行预处理和读取
                image_path = Path(image_path)
                
                # 图像预处理
                if opts.preprocess and self._preprocessor is not None:
                    import asyncio
                    
                    # 在后台线程执行预处理
                    loop = asyncio.get_event_loop()
                    prep_result = await loop.run_in_executor(
                        None,
                        self._preprocessor.process,
                        image_path,
                    )
                    
                    if prep_result.success:
                        self.logger.info(
                            "ocr_preprocess_complete",
                            corrections=prep_result.applied_corrections,
                            confidence=prep_result.confidence,
                            original_size=prep_result.original_size,
                            processed_size=prep_result.processed_size,
                        )
                        # 使用处理后的图像
                        image_data = self._preprocessor.to_base64(prep_result.image)
                    else:
                        self.logger.warning(
                            "ocr_preprocess_failed",
                            error=prep_result.error,
                            fallback="using_original_image"
                        )
                        # 预处理失败，使用原图
                        image_data = self._read_image(image_path)
                else:
                    # 不预处理，直接读取
                    image_data = self._read_image(image_path)
            
            # 构建提示
            user_prompt = "请识别这张图片中的题目内容。"
            if subject_hint:
                user_prompt += f"这是一道{subject_hint}题目。"
            
            messages = [
                Message.system(self.SYSTEM_PROMPT),
                Message.user(user_prompt),
            ]
            
            # 调用视觉模型
            response = await self.client.complete_with_vision(
                messages=messages,
                images=[image_data],
            )
            
            # 解析响应
            result = self._parse_response(response)
            
            self.logger.info(
                "ocr_success",
                confidence=result.confidence,
                content_length=len(result.content),
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "ocr_error",
                error=str(e),
            )
            return OCRResult(
                success=False,
                error=str(e),
            )
    
    async def recognize_batch(
        self,
        image_paths: List[Union[str, Path]],
        subject_hint: Optional[str] = None,
        options: Optional[OCROptions] = None,
    ) -> List[OCRResult]:
        """批量识别多张图片.
        
        Args:
            image_paths: 图片路径列表
            subject_hint: 学科提示
            options: OCR选项
            
        Returns:
            OCR结果列表
        """
        self.logger.info(
            "ocr_batch_start",
            image_count=len(image_paths),
        )
        
        results = []
        for path in image_paths:
            result = await self.recognize(path, subject_hint, options)
            results.append(result)
        
        success_count = sum(1 for r in results if r.success)
        self.logger.info(
            "ocr_batch_complete",
            total=len(image_paths),
            success=success_count,
            failed=len(image_paths) - success_count,
        )
        
        return results
    
    def _read_image(self, image_path: Union[str, Path]) -> str:
        """读取图片并转为base64.
        
        Args:
            image_path: 图片路径
            
        Returns:
            base64编码的图片数据
        """
        path = Path(image_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        with open(path, "rb") as f:
            image_bytes = f.read()
        
        return base64.b64encode(image_bytes).decode("utf-8")
    
    def _parse_response(self, response: ModelResponse) -> OCRResult:
        """解析模型响应.
        
        Args:
            response: 模型响应
            
        Returns:
            OCR结果
        """
        import json
        import re
        
        content = response.content.strip()
        
        try:
            # 尝试直接解析JSON
            data = json.loads(content)
        except json.JSONDecodeError:
            # 尝试从代码块中提取
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    data = self._fallback_parse(content)
            else:
                # 尝试找花括号
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        data = self._fallback_parse(content)
                else:
                    data = self._fallback_parse(content)
        
        # 验证和标准化学科类型
        subject = data.get("subject", "unknown").lower()
        valid_subjects = ["math", "physics", "chemistry"]
        if subject not in valid_subjects:
            subject = "unknown"
        
        # 验证和标准化题目类型
        problem_type = data.get("problem_type", "unknown").lower()
        valid_types = ["choice", "fill_blank", "calculation", "application", "proof"]
        if problem_type not in valid_types:
            problem_type = "unknown"
        
        # 提取知识点
        knowledge_points = data.get("knowledge_points", [])
        if isinstance(knowledge_points, str):
            knowledge_points = [kp.strip() for kp in knowledge_points.split(",") if kp.strip()]
        
        return OCRResult(
            success=True,
            content=data.get("content", ""),
            student_answer=data.get("student_answer"),
            subject=subject,
            problem_type=problem_type,
            knowledge_points=knowledge_points[:5],  # 最多5个
            confidence=data.get("confidence", 0.7),
            raw_response=content,
        )
    
    def _fallback_parse(self, content: str) -> Dict[str, Any]:
        """降级解析.
        
        当JSON解析失败时，尝试从文本中提取信息。
        
        Args:
            content: 原始响应文本
            
        Returns:
            解析后的数据字典
        """
        return {
            "content": content[:2000],  # 限制长度
            "student_answer": None,
            "subject": "unknown",
            "problem_type": "unknown",
            "knowledge_points": [],
            "confidence": 0.5,
        }
    
    async def extract_text_only(
        self,
        image_path: Union[str, Path],
    ) -> str:
        """仅提取文本内容.
        
        Args:
            image_path: 图片路径
            
        Returns:
            提取的文本
        """
        result = await self.recognize(
            image_path,
            options=OCROptions(
                detect_subject=False,
                detect_problem_type=False,
                extract_student_answer=True,
            ),
        )
        
        if result.success:
            return result.content
        else:
            return ""
    
    def estimate_confidence(self, result: OCRResult) -> str:
        """评估识别置信度等级.
        
        Args:
            result: OCR结果
            
        Returns:
            置信度等级(high/medium/low)
        """
        if result.confidence >= 0.8:
            return "high"
        elif result.confidence >= 0.6:
            return "medium"
        else:
            return "low"
