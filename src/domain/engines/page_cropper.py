"""AI 页面裁切引擎.

使用轻量级 Vision API 检测作业照片中的纸张边界，返回四个角点坐标，
然后执行透视变换裁切。相比传统 CV，对复杂背景（桌面、床单、深色背景）更鲁棒。

作为 "小模型" 方案：prompt 极简（只返4个坐标），调用成本低、响应快。
"""

import base64
import json
import os
from typing import Optional

import cv2
import numpy as np

from src.infrastructure.config import get_settings
from src.infrastructure.logging import get_logger
from src.infrastructure.models import create_model_client
from src.infrastructure.models.base import Message

logger = get_logger(__name__)
settings = get_settings()

# 极简 prompt：只让模型返4个角点，不做任何其他分析
PAGE_DETECTION_PROMPT = """你是一位文档图像处理专家。请查看这张图片，找出其中作业纸张的四个角点坐标。

要求：
1. 只返回作业纸张的四个角点（左上、右上、右下、左下）
2. 坐标是相对于原图的比例值（0.0 ~ 1.0）
3. 如果图片中没有明显的纸张边界，返回 has_page=false
4. 不要输出任何解释文字，只返回 JSON

输出格式：
{
    "has_page": true/false,
    "corners": [
        {"x": 0.05, "y": 0.05},
        {"x": 0.95, "y": 0.05},
        {"x": 0.95, "y": 0.95},
        {"x": 0.05, "y": 0.95}
    ]
}"""


class PageCropper:
    """AI 页面裁切器：用 Vision API 检测纸张边界并透视校正."""

    def __init__(self, timeout: float = 15.0):
        """初始化页面裁切器.

        Args:
            timeout: API 调用超时（秒）
        """
        self.timeout = timeout

    async def detect_page_boundary(self, image_path: str) -> Optional[np.ndarray]:
        """检测图片中的作业页面边界.

        Args:
            image_path: 图片文件路径

        Returns:
            4x2 的角点数组（np.float32，顺序：左上、右上、右下、左下），
            未检测到则返回 None
        """
        try:
            # 读取图片并转 base64
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")

            # 创建轻量模型客户端
            model_client = create_model_client(vision=True, timeout=self.timeout)
            vision_model = settings.kimi.vision_model if settings.active_model_provider == "kimi" else "kimi-k2.5"

            messages = [
                Message.system("你是一个文档图像处理专家，只返回JSON坐标数据。"),
                Message.user(PAGE_DETECTION_PROMPT),
            ]

            logger.info("page_detection_start", image_path=image_path)

            response = await model_client.complete_with_vision(
                messages=messages,
                images=[image_base64],
                model=vision_model,
                temperature=0.1,
                max_tokens=512,
            )

            raw_response = response.content
            logger.info("page_detection_response", response_length=len(raw_response))

            # 解析 JSON
            result = self._parse_detection_response(raw_response)

            if result is None or not result.get("has_page"):
                logger.info("page_detection_no_page_found", image_path=image_path)
                return None

            corners = result.get("corners", [])
            if len(corners) != 4:
                logger.warning("page_detection_invalid_corners", count=len(corners))
                return None

            # 转换为 numpy 数组（按顺序：左上、右上、右下、左下）
            pts = np.array([
                [corners[0]["x"], corners[0]["y"]],
                [corners[1]["x"], corners[1]["y"]],
                [corners[2]["x"], corners[2]["y"]],
                [corners[3]["x"], corners[3]["y"]],
            ], dtype=np.float32)

            # 验证坐标有效性
            if not self._validate_corners(pts):
                logger.warning("page_detection_invalid_coordinates", corners=pts.tolist())
                return None

            # 转换为像素坐标
            image = cv2.imread(image_path)
            if image is None:
                logger.error("page_detection_cv2_read_failed", image_path=image_path)
                return None

            h, w = image.shape[:2]
            pixel_pts = pts * np.array([[w, h]], dtype=np.float32)

            logger.info(
                "page_detection_success",
                image_path=image_path,
                corners=pts.tolist(),
                pixel_corners=pixel_pts.tolist(),
            )
            return pixel_pts

        except Exception as e:
            logger.exception("page_detection_failed", image_path=image_path, error=str(e))
            return None

    def crop_and_transform(
        self,
        image: np.ndarray,
        corners: np.ndarray,
        margin_ratio: float = 0.01,
    ) -> np.ndarray:
        """根据角点执行透视变换裁切.

        Args:
            image: 原始图像（OpenCV BGR 格式）
            corners: 4x2 的像素角点数组（左上、右上、右下、左下）
            margin_ratio: 保留边距比例（默认 1%）

        Returns:
            透视校正后的图像
        """
        # 排序角点（确保顺序正确）
        ordered = self._order_points(corners)

        # 计算目标尺寸
        width_top = np.linalg.norm(ordered[1] - ordered[0])
        width_bottom = np.linalg.norm(ordered[2] - ordered[3])
        max_width = int(max(width_top, width_bottom))

        height_left = np.linalg.norm(ordered[3] - ordered[0])
        height_right = np.linalg.norm(ordered[2] - ordered[1])
        max_height = int(max(height_left, height_right))

        # 添加边距
        margin_w = int(max_width * margin_ratio)
        margin_h = int(max_height * margin_ratio)
        dst_width = max_width + margin_w * 2
        dst_height = max_height + margin_h * 2

        # 目标点
        dst = np.array([
            [margin_w, margin_h],
            [dst_width - margin_w - 1, margin_h],
            [dst_width - margin_w - 1, dst_height - margin_h - 1],
            [margin_w, dst_height - margin_h - 1],
        ], dtype=np.float32)

        # 透视变换
        matrix = cv2.getPerspectiveTransform(ordered, dst)
        warped = cv2.warpPerspective(
            image, matrix, (dst_width, dst_height),
            borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255)
        )

        logger.info(
            "page_crop_complete",
            original_size=(image.shape[1], image.shape[0]),
            cropped_size=(dst_width, dst_height),
        )
        return warped

    @staticmethod
    def _parse_detection_response(raw_response: str) -> Optional[dict]:
        """解析模型返回的 JSON 响应."""
        result = None

        # 尝试1: 直接解析
        try:
            result = json.loads(raw_response)
        except json.JSONDecodeError:
            pass

        # 尝试2: 从 markdown 代码块中提取
        if result is None:
            import re
            try:
                match = re.search(r'```json\s*(.*?)\s*```', raw_response, re.DOTALL)
                if match:
                    result = json.loads(match.group(1))
            except (json.JSONDecodeError, AttributeError):
                pass

        # 尝试3: 从文本中提取 JSON 对象
        if result is None:
            import re
            try:
                match = re.search(r'\{[\s\S]*\}', raw_response)
                if match:
                    result = json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return result

    @staticmethod
    def _validate_corners(pts: np.ndarray) -> bool:
        """验证角点坐标的有效性."""
        if pts.shape != (4, 2):
            return False

        # 检查坐标范围
        if not np.all((pts >= 0) & (pts <= 1)):
            return False

        # 检查四边形面积是否合理（至少占图片的 10%）
        area = cv2.contourArea(pts.reshape(4, 1, 2))
        if area < 0.1:
            return False

        return True

    @staticmethod
    def _order_points(pts: np.ndarray) -> np.ndarray:
        """按顺序排列四个点（左上、右上、右下、左下）."""
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]   # 左上
        rect[2] = pts[np.argmax(s)]   # 右下
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]  # 右上
        rect[3] = pts[np.argmax(diff)]  # 左下
        return rect
