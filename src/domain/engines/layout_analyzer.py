"""版面分析引擎.

自动检测作业图片中的题目区域，支持逐题裁切诊断。
采用 AI 轻量版面分析（Vision API），返回每道题的边界框坐标。
"""

import asyncio
import base64
import json
import os
import re
from typing import List, Optional

from src.infrastructure.config import get_settings
from src.infrastructure.logging import get_logger
from src.infrastructure.models import create_model_client
from src.infrastructure.models.base import Message

logger = get_logger(__name__)
settings = get_settings()

# 轻量版面分析提示词：要求模型只返回题目区域坐标，不做深度分析
LAYOUT_ANALYSIS_PROMPT = """你是一位版面分析专家。请仔细查看这张作业图片，识别出图片中包含的所有独立题目区域。

任务要求：
1. 按题号顺序（1、2、3...）识别每道题的完整区域
2. 每道题的区域应包含：题干、选项（如有）、学生的答题痕迹
3. 忽略页眉、页脚、无关文字
4. 如果图片中只有一道题，也返回该题的坐标

坐标格式说明：
- 坐标是相对于原图的比例值（0.0 ~ 1.0）
- x: 区域左上角的横向比例（左边缘为0）
- y: 区域左上角的纵向比例（上边缘为0）
- width: 区域宽度占原图宽度的比例
- height: 区域高度占原图高度的比例

请严格按照以下JSON格式返回，不要输出任何其他文字：
{
    "question_count": 3,
    "questions": [
        {"question_id": 1, "bbox": {"x": 0.05, "y": 0.05, "width": 0.90, "height": 0.25}},
        {"question_id": 2, "bbox": {"x": 0.05, "y": 0.35, "width": 0.90, "height": 0.25}},
        {"question_id": 3, "bbox": {"x": 0.05, "y": 0.65, "width": 0.90, "height": 0.25}}
    ]
}"""

# 单题诊断提示词（用于裁切后的子图）
PER_QUESTION_DIAGNOSIS_PROMPT = """你是一位专业的数学作业诊断助手。图片中只包含一道题目，请针对该题完成以下任务：

1. **识别题目内容**：提取这道题的完整题干
2. **识别学生答案**：找到学生写的答案（如有）
3. **判断对错**：分析答案是否正确
4. **错误诊断**：如果错了，分析错误原因（计算错误/概念错误/粗心/其他）
5. **给出建议**：提供针对性的学习建议

请严格按照以下JSON格式返回结果：
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
}"""


class LayoutAnalyzer:
    """版面分析器：检测作业图片中的题目区域."""

    def __init__(self, timeout: float = 30.0):
        """初始化版面分析器.

        Args:
            timeout: API 调用超时时间（秒）
        """
        self.timeout = timeout

    async def detect_questions(self, image_path: str) -> List[dict]:
        """检测图片中的题目区域.

        Args:
            image_path: 图片文件路径

        Returns:
            题目区域列表，每个元素包含 question_id 和 bbox（相对坐标）
            如果检测失败，返回空列表（调用方应 fallback 到整图诊断）
        """
        try:
            # 读取图片并转 base64
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")

            # 创建轻量模型客户端（低 temperature，短超时）
            model_client = create_model_client(vision=True, timeout=self.timeout)

            messages = [
                Message.system("你是一个版面分析专家，只返回JSON坐标数据。"),
                Message.user(LAYOUT_ANALYSIS_PROMPT),
            ]

            vision_model = settings.kimi.vision_model if settings.active_model_provider == "kimi" else "kimi-k2.5"

            logger.info("layout_analysis_start", image_path=image_path)

            response = await model_client.complete_with_vision(
                messages=messages,
                images=[image_base64],
                model=vision_model,
                temperature=0.1,
                max_tokens=1024,
            )

            raw_response = response.content
            logger.info("layout_analysis_response", response_length=len(raw_response))

            # 解析 JSON
            regions = self._parse_layout_response(raw_response)

            if regions:
                logger.info(
                    "layout_analysis_success",
                    question_count=len(regions),
                    regions=regions,
                )
            else:
                logger.warning("layout_analysis_empty", raw_preview=raw_response[:200])

            return regions

        except Exception as e:
            logger.exception("layout_analysis_failed", error=str(e))
            return []

    def _parse_layout_response(self, raw_response: str) -> List[dict]:
        """解析版面分析模型的 JSON 响应.

        Args:
            raw_response: 模型原始输出

        Returns:
            过滤并验证后的题目区域列表
        """
        result = None

        # 尝试1: 直接解析
        try:
            result = json.loads(raw_response)
        except json.JSONDecodeError:
            pass

        # 尝试2: 从 markdown 代码块中提取
        if result is None:
            try:
                match = re.search(r'```json\s*(.*?)\s*```', raw_response, re.DOTALL)
                if match:
                    result = json.loads(match.group(1))
            except (json.JSONDecodeError, AttributeError):
                pass

        # 尝试3: 从文本中提取 JSON 对象
        if result is None:
            try:
                match = re.search(r'\{[\s\S]*\}', raw_response)
                if match:
                    result = json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        if result is None:
            return []

        questions = result.get("questions", [])
        if not questions:
            return []

        # 验证并清理坐标
        valid_regions = []
        for q in questions:
            bbox = q.get("bbox", {})
            try:
                x = float(bbox.get("x", 0))
                y = float(bbox.get("y", 0))
                w = float(bbox.get("width", 0))
                h = float(bbox.get("height", 0))

                # 过滤无效区域
                if w <= 0 or h <= 0 or w > 1 or h > 1:
                    continue
                if x < 0 or y < 0 or x + w > 1 or y + h > 1:
                    # 尝试裁剪到边界
                    x = max(0.0, x)
                    y = max(0.0, y)
                    w = min(w, 1.0 - x)
                    h = min(h, 1.0 - y)
                    if w <= 0 or h <= 0:
                        continue

                valid_regions.append({
                    "question_id": int(q.get("question_id", len(valid_regions) + 1)),
                    "bbox": {
                        "x": round(x, 4),
                        "y": round(y, 4),
                        "width": round(w, 4),
                        "height": round(h, 4),
                    },
                })
            except (TypeError, ValueError):
                continue

        return valid_regions


async def diagnose_single_question(
    image_base64: str,
    question_id: int,
    model_client,
    vision_model: str,
    parent_description: Optional[str] = None,
) -> Optional[dict]:
    """对单道题目进行诊断.

    Args:
        image_base64: 裁切后的题目图片（base64）
        question_id: 题号
        model_client: 模型客户端
        vision_model: 视觉模型名称
        parent_description: 家长描述（可选）

    Returns:
        单题诊断结果字典，失败返回 None
    """
    try:
        user_content = f"请诊断这道题目。这是第 {question_id} 题。"
        if parent_description:
            user_content += f"\n\n用户补充说明：{parent_description}"

        messages = [
            Message.system(PER_QUESTION_DIAGNOSIS_PROMPT),
            Message.user(user_content),
        ]

        response = await model_client.complete_with_vision(
            messages=messages,
            images=[image_base64],
            model=vision_model,
            temperature=0.3,
            max_tokens=2048,
        )

        raw_response = response.content

        # 解析 JSON
        result = None

        # 尝试1: 直接解析
        try:
            result = json.loads(raw_response)
        except json.JSONDecodeError:
            pass

        # 尝试2: 从 markdown 代码块中提取
        if result is None:
            try:
                match = re.search(r'```json\s*(.*?)\s*```', raw_response, re.DOTALL)
                if match:
                    result = json.loads(match.group(1))
            except (json.JSONDecodeError, AttributeError):
                pass

        # 尝试3: 从文本中提取 JSON 对象
        if result is None:
            try:
                match = re.search(r'\{[\s\S]*\}', raw_response)
                if match:
                    result = json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        if result is None:
            logger.warning("per_question_parse_failed", question_id=question_id, preview=raw_response[:200])
            return None

        # 注入题号（如果模型返回了错误的题号）
        result["question_id"] = question_id
        return result

    except Exception as e:
        logger.exception("per_question_diagnosis_failed", question_id=question_id, error=str(e))
        return None
