"""错题识别引擎.

功能追溯ID: F-DIAG-001
实现错题识别、位置定位和错误类型分类。
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.infrastructure.logging import get_logger
from src.domain.models.diagnosis import ErrorType, Problem, WrongProblem
from src.domain.models.arbitration import ArbitrationResult
from src.domain.models.base import generate_id

logger = get_logger(__name__)


@dataclass
class ErrorLocation:
    """错误位置信息.
    
    Attributes:
        line: 错误所在行号
        column: 错误所在列号
        x: 图片中的X坐标
        y: 图片中的Y坐标
        width: 宽度
        height: 高度
        description: 位置描述
    """
    line: Optional[int] = None
    column: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    description: str = ""


@dataclass
class ErrorDetectionResult:
    """错题识别结果.
    
    Attributes:
        problem_id: 题目ID
        is_wrong: 是否错误
        error_type: 错误类型
        student_answer: 学生答案
        correct_answer: 正确答案
        error_location: 错误位置
        confidence: 识别置信度
        details: 详细信息
    """
    problem_id: str
    is_wrong: bool
    error_type: Optional[ErrorType] = None
    student_answer: Optional[str] = None
    correct_answer: Optional[str] = None
    error_location: Optional[ErrorLocation] = None
    confidence: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


class ErrorDetectionEngine:
    """错题识别引擎.
    
    负责对比学生答案与正确答案，识别错误位置，
    分类错误类型，并生成错题截图坐标。
    
    Example:
        >>> engine = ErrorDetectionEngine()
        >>> result = await engine.detect(
        ...     problem=problem,
        ...     arbitration_result=arbitration_result,
        ...     ocr_result=ocr_result,
        ... )
    """
    
    # 错误类型关键词映射
    ERROR_KEYWORDS = {
        ErrorType.CALCULATION_ERROR: [
            "计算", "算错", "加减", "乘除", "运算", "小数点", "进位", "借位",
            "arithmetic", "calculation", "computation"
        ],
        ErrorType.CONCEPT_MISUNDERSTANDING: [
            "概念", "理解", "混淆", "误解", "错误理解", "概念不清",
            "concept", "misunderstanding", "confusion"
        ],
        ErrorType.LOGICAL_FLAW: [
            "逻辑", "推理", "推导", "论证", "漏洞", "矛盾",
            "logic", "reasoning", "deduction"
        ],
        ErrorType.CARELESS_MISTAKE: [
            "粗心", "马虎", "漏写", "看错", "抄错", "忘记", "手误",
            "careless", "inattention", "slip", "mistake"
        ],
        ErrorType.KNOWLEDGE_GAP: [
            "知识", "不会", "不懂", "未掌握", "缺失", "缺漏", "空白",
            "knowledge", "gap", "missing", "unfamiliar"
        ],
    }
    
    def __init__(self):
        """初始化错题识别引擎."""
        self.logger = get_logger(__name__)
    
    async def detect(
        self,
        problem: Problem,
        arbitration_result: ArbitrationResult,
        ocr_result: Optional[Dict[str, Any]] = None,
    ) -> ErrorDetectionResult:
        """识别错题.
        
        Args:
            problem: 题目信息
            arbitration_result: 仲裁结果
            ocr_result: OCR识别结果（可选）
            
        Returns:
            错题识别结果
        """
        self.logger.info(
            "error_detection_start",
            problem_id=problem.id,
            is_correct=arbitration_result.is_correct,
        )
        
        # 判断是否有错
        is_wrong = not arbitration_result.is_correct
        
        if not is_wrong:
            return ErrorDetectionResult(
                problem_id=problem.id,
                is_wrong=False,
                confidence=arbitration_result.confidence,
            )
        
        # 提取答案信息
        student_answer = ocr_result.get("student_answer") if ocr_result else None
        correct_answer = problem.answer
        
        # 确定错误类型
        error_type = arbitration_result.error_type
        if error_type is None:
            error_type = await self._classify_error_type(
                problem, arbitration_result, ocr_result
            )
        
        # 定位错误位置
        error_location = await self._locate_error(
            problem, student_answer, correct_answer, error_type, ocr_result
        )
        
        # 计算置信度
        confidence = self._calculate_confidence(
            arbitration_result, error_type, error_location
        )
        
        result = ErrorDetectionResult(
            problem_id=problem.id,
            is_wrong=True,
            error_type=error_type,
            student_answer=student_answer,
            correct_answer=correct_answer,
            error_location=error_location,
            confidence=confidence,
            details={
                "arbitration_confidence": arbitration_result.confidence,
                "model_votes": {
                    k: v.is_correct for k, v in arbitration_result.model_votes.items()
                },
            },
        )
        
        self.logger.info(
            "error_detection_complete",
            problem_id=problem.id,
            error_type=error_type.value if error_type else None,
            confidence=confidence,
        )
        
        return result
    
    async def detect_batch(
        self,
        problems: List[Problem],
        arbitration_results: List[ArbitrationResult],
        ocr_results: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ErrorDetectionResult]:
        """批量识别错题.
        
        Args:
            problems: 题目列表
            arbitration_results: 仲裁结果列表
            ocr_results: OCR结果列表（可选）
            
        Returns:
            错题识别结果列表
        """
        results = []
        ocr_map = {i: r for i, r in enumerate(ocr_results or [])}
        
        for i, (problem, arb_result) in enumerate(zip(problems, arbitration_results)):
            ocr_result = ocr_map.get(i)
            result = await self.detect(problem, arb_result, ocr_result)
            results.append(result)
        
        return results
    
    async def _classify_error_type(
        self,
        problem: Problem,
        arbitration_result: ArbitrationResult,
        ocr_result: Optional[Dict[str, Any]] = None,
    ) -> ErrorType:
        """分类错误类型.
        
        基于模型投票和文本分析确定错误类型。
        
        Args:
            problem: 题目信息
            arbitration_result: 仲裁结果
            ocr_result: OCR结果
            
        Returns:
            错误类型
        """
        # 收集各模型的诊断文本
        diagnosis_texts = []
        
        for model_id, vote in arbitration_result.model_votes.items():
            if not vote.is_correct and vote.reason:
                diagnosis_texts.append(vote.reason)
        
        if ocr_result:
            diagnosis_texts.append(str(ocr_result.get("analysis", "")))
        
        combined_text = " ".join(diagnosis_texts).lower()
        
        # 基于关键词匹配
        type_scores: Dict[ErrorType, int] = {}
        
        for error_type, keywords in self.ERROR_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in combined_text)
            if score > 0:
                type_scores[error_type] = score
        
        # 返回得分最高的类型，默认知识缺口
        if type_scores:
            return max(type_scores.items(), key=lambda x: x[1])[0]
        
        # 检查是否有明显的计算特征
        if self._has_calculation_features(problem, combined_text):
            return ErrorType.CALCULATION_ERROR
        
        return ErrorType.KNOWLEDGE_GAP
    
    def _has_calculation_features(
        self,
        problem: Problem,
        text: str,
    ) -> bool:
        """检查是否有计算错误特征.
        
        Args:
            problem: 题目
            text: 诊断文本
            
        Returns:
            是否有计算特征
        """
        # 数字运算相关特征
        calc_patterns = [
            r'\d+\s*[\+\-\*\/]\s*\d+',  # 数字运算
            r'[=＝]\s*\d+\.?\d*\s*$',  # 以数字结尾
            r'得数', '结果', '等于',
        ]
        
        for pattern in calc_patterns:
            if re.search(pattern, text) or pattern in text:
                return True
        
        return False
    
    async def _locate_error(
        self,
        problem: Problem,
        student_answer: Optional[str],
        correct_answer: Optional[str],
        error_type: Optional[ErrorType],
        ocr_result: Optional[Dict[str, Any]],
    ) -> Optional[ErrorLocation]:
        """定位错误位置.
        
        Args:
            problem: 题目信息
            student_answer: 学生答案
            correct_answer: 正确答案
            error_type: 错误类型
            ocr_result: OCR结果
            
        Returns:
            错误位置信息
        """
        location = ErrorLocation()
        
        # 从OCR结果中提取位置信息
        if ocr_result and "position" in ocr_result:
            pos = ocr_result["position"]
            location.x = pos.get("x")
            location.y = pos.get("y")
            location.width = pos.get("width")
            location.height = pos.get("height")
        
        # 分析答案差异
        if student_answer and correct_answer:
            diff_info = self._analyze_answer_difference(
                student_answer, correct_answer
            )
            location.description = diff_info.get("description", "")
            
            # 尝试定位到具体字符位置
            if "diff_position" in diff_info:
                location.column = diff_info["diff_position"]
        
        # 根据错误类型设置描述
        if not location.description and error_type:
            location.description = self._get_error_description(error_type)
        
        return location
    
    def _analyze_answer_difference(
        self,
        student_answer: str,
        correct_answer: str,
    ) -> Dict[str, Any]:
        """分析答案差异.
        
        Args:
            student_answer: 学生答案
            correct_answer: 正确答案
            
        Returns:
            差异信息
        """
        # 简化比较
        sa = student_answer.strip().replace(" ", "").replace("　", "")
        ca = correct_answer.strip().replace(" ", "").replace("　", "")
        
        if sa == ca:
            return {"description": "答案形式相同"}
        
        # 找第一个不同字符
        min_len = min(len(sa), len(ca))
        diff_pos = None
        
        for i in range(min_len):
            if sa[i] != ca[i]:
                diff_pos = i
                break
        
        if diff_pos is None:
            if len(sa) != len(ca):
                diff_pos = min_len
                return {
                    "description": f"答案长度不同（学生{len(sa)} vs 正确{len(ca)}）",
                    "diff_position": diff_pos,
                }
        
        # 数字计算错误特征
        if sa.isdigit() and ca.isdigit():
            diff = abs(int(sa) - int(ca))
            if diff < 10:
                return {
                    "description": f"计算结果偏差{diff}，可能在个位数计算出错",
                    "diff_position": diff_pos,
                    "calc_diff": diff,
                }
        
        return {
            "description": f"第{diff_pos + 1}个字符不同",
            "diff_position": diff_pos,
        }
    
    def _get_error_description(self, error_type: ErrorType) -> str:
        """获取错误类型描述.
        
        Args:
            error_type: 错误类型
            
        Returns:
            描述文本
        """
        descriptions = {
            ErrorType.CALCULATION_ERROR: "计算过程出现错误",
            ErrorType.CONCEPT_MISUNDERSTANDING: "概念理解有误",
            ErrorType.LOGICAL_FLAW: "逻辑推理存在问题",
            ErrorType.CARELESS_MISTAKE: "粗心导致的错误",
            ErrorType.KNOWLEDGE_GAP: "知识点掌握有缺漏",
        }
        return descriptions.get(error_type, "未知错误类型")
    
    def _calculate_confidence(
        self,
        arbitration_result: ArbitrationResult,
        error_type: Optional[ErrorType],
        error_location: Optional[ErrorLocation],
    ) -> float:
        """计算识别置信度.
        
        Args:
            arbitration_result: 仲裁结果
            error_type: 错误类型
            error_location: 错误位置
            
        Returns:
            置信度分数
        """
        base_confidence = arbitration_result.confidence
        
        # 错误类型确定增加置信度
        if error_type:
            base_confidence = min(1.0, base_confidence + 0.1)
        
        # 错误位置定位增加置信度
        if error_location and error_location.x is not None:
            base_confidence = min(1.0, base_confidence + 0.05)
        
        # 共识度高增加置信度
        if arbitration_result.is_consensus:
            base_confidence = min(1.0, base_confidence + 0.1)
        
        return round(base_confidence, 4)
    
    def to_wrong_problem(
        self,
        detection_result: ErrorDetectionResult,
    ) -> WrongProblem:
        """转换为WrongProblem对象.
        
        Args:
            detection_result: 错题识别结果
            
        Returns:
            WrongProblem对象
        """
        error_position = None
        if detection_result.error_location:
            loc = detection_result.error_location
            error_position = {
                "line": loc.line,
                "column": loc.column,
                "x": loc.x,
                "y": loc.y,
                "width": loc.width,
                "height": loc.height,
                "description": loc.description,
            }
        
        return WrongProblem(
            problem_id=detection_result.problem_id,
            error_type=detection_result.error_type or ErrorType.KNOWLEDGE_GAP,
            root_cause=detection_result.error_location.description 
                      if detection_result.error_location else "未知错误",
            concept_gap=[],
            confidence=detection_result.confidence,
            student_answer=detection_result.student_answer,
            error_position=error_position,
        )
