"""图像预处理引擎.

提供作业照片预处理功能，采用保守策略确保文字不丢失：
- 透视校正：自动检测纸张边缘并矫正，保留边距
- 旋转校正：检测文本方向并旋转
- 背景去除：仅去除边缘，不影响内容区域
- 对比度增强：轻度CLAHE，避免过度处理
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PreprocessOptions:
    """预处理选项.
    
    Attributes:
        correct_perspective: 是否进行透视校正
        correct_rotation: 是否进行旋转校正
        remove_background: 是否去除背景/无关内容（默认关闭，容易误删文字）
        enhance_contrast: 是否增强对比度
        target_dpi: 目标DPI（用于标准化输出）
        output_format: 输出格式（PNG/JPEG）
        jpeg_quality: JPEG质量（1-100）
        perspective_margin: 透视校正后保留的边距比例
    """
    correct_perspective: bool = True
    correct_rotation: bool = True
    remove_background: bool = False  # 默认关闭，避免误删文字
    enhance_contrast: bool = True
    target_dpi: int = 150
    output_format: str = "jpeg"
    jpeg_quality: int = 90
    
    # 透视校正参数
    perspective_margin: float = 0.02  # 保留2%边距
    min_paper_area_ratio: float = 0.15  # 最小纸张面积比例
    max_paper_area_ratio: float = 0.95  # 最大纸张面积比例
    
    # 对比度增强参数（保守）
    clahe_clip_limit: float = 1.5
    clahe_grid_size: int = 8
    
    # 去噪参数
    denoise_strength: int = 10
    
    # 智能裁剪参数
    auto_crop: bool = True  # 自动裁剪空白边缘
    content_margin: int = 20  # 内容边距（像素）
    white_threshold: int = 240  # 白色阈值（高于此值视为背景）
    min_content_size: int = 100  # 最小内容区域尺寸


@dataclass
class PreprocessResult:
    """预处理结果.
    
    Attributes:
        success: 是否成功
        image: 处理后的图像（OpenCV格式）
        original_size: 原始尺寸
        processed_size: 处理后尺寸
        applied_corrections: 应用的校正列表
        confidence: 校正置信度（0-1）
        error: 错误信息
    """
    success: bool = False
    image: Optional[np.ndarray] = None
    original_size: Optional[Tuple[int, int]] = None
    processed_size: Optional[Tuple[int, int]] = None
    applied_corrections: List[str] = field(default_factory=list)
    confidence: float = 0.0
    error: Optional[str] = None


class ImagePreprocessor:
    """图像预处理引擎.
    
    专门处理作业照片的预处理，采用保守策略确保文字内容不丢失。
    
    Example:
        >>> preprocessor = ImagePreprocessor()
        >>> result = preprocessor.process("/path/to/homework.jpg")
        >>> if result.success:
        ...     preprocessor.save(result.image, "/path/to/output.jpg")
    """
    
    def __init__(self, options: Optional[PreprocessOptions] = None):
        """初始化预处理器.
        
        Args:
            options: 预处理选项
        """
        self.options = options or PreprocessOptions()
        self.logger = logger
    
    def process(
        self,
        image_path: Union[str, Path, np.ndarray],
        options: Optional[PreprocessOptions] = None,
    ) -> PreprocessResult:
        """处理图像.
        
        Args:
            image_path: 图像路径或OpenCV图像数组
            options: 可选的预处理选项（覆盖默认选项）
            
        Returns:
            预处理结果
        """
        opts = options or self.options
        result = PreprocessResult()
        
        try:
            # 加载图像
            if isinstance(image_path, np.ndarray):
                image = image_path.copy()
            else:
                image = self._load_image(str(image_path))
            
            result.original_size = (image.shape[1], image.shape[0])
            
            self.logger.info(
                "preprocess_start",
                original_size=result.original_size,
            )
            
            # 1. 透视校正（保守策略）
            if opts.correct_perspective:
                image, confidence = self._correct_perspective_safe(image, opts)
                if confidence > 0.5:
                    result.applied_corrections.append(f"perspective({confidence:.2f})")
                    result.confidence = max(result.confidence, confidence)
                    self.logger.debug("perspective_corrected", confidence=confidence)
            
            # 2. 旋转校正
            if opts.correct_rotation:
                image, angle = self._correct_rotation(image, opts)
                if abs(angle) > 0.5:
                    result.applied_corrections.append(f"rotation({angle:.1f}°)")
                    self.logger.debug("rotation_corrected", angle=angle)
            
            # 3. 去除背景/无关内容（默认关闭）
            if opts.remove_background:
                image = self._remove_border_only(image, opts)
                result.applied_corrections.append("border")
                self.logger.debug("border_removed")
            
            # 4. 对比度增强（轻度）
            if opts.enhance_contrast:
                image = self._enhance_contrast_safe(image, opts)
                result.applied_corrections.append("contrast")
                self.logger.debug("contrast_enhanced")
            
            # 5. 智能裁剪（去除空白背景）
            if opts.auto_crop:
                image, crop_info = self._auto_crop_content(image, opts)
                if crop_info:
                    result.applied_corrections.append(f"crop({crop_info})")
                    self.logger.debug("auto_cropped", info=crop_info)
            
            result.image = image
            result.processed_size = (image.shape[1], image.shape[0])
            result.success = True
            
            self.logger.info(
                "preprocess_complete",
                processed_size=result.processed_size,
                corrections=result.applied_corrections,
                confidence=result.confidence,
            )
            
        except Exception as e:
            result.error = str(e)
            self.logger.error("preprocess_failed", error=str(e))
        
        return result
    
    def _load_image(self, image_path: str) -> np.ndarray:
        """加载图像.
        
        Args:
            image_path: 图像路径
            
        Returns:
            OpenCV格式的图像（BGR）
        """
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"无法加载图像: {image_path}")
        return image
    
    def _correct_perspective_safe(
        self,
        image: np.ndarray,
        opts: PreprocessOptions,
    ) -> Tuple[np.ndarray, float]:
        """安全的透视校正 - 保留更多内容.
        
        使用自适应阈值检测纸张边缘，保留边距以避免裁剪文字。
        
        Args:
            image: 输入图像
            opts: 预处理选项
            
        Returns:
            (校正后的图像, 置信度)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # 使用自适应阈值而不是Canny，对文字更友好
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )
        
        # 查找轮廓
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        if not contours:
            return image, 0.0
        
        # 找到最大的轮廓（应该是纸张）
        max_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(max_contour)
        total_area = image.shape[0] * image.shape[1]
        area_ratio = area / total_area
        
        # 如果轮廓太小或太大，可能是误检测
        if area_ratio < opts.min_paper_area_ratio or area_ratio > opts.max_paper_area_ratio:
            return image, 0.0
        
        # 近似四边形
        epsilon = 0.02 * cv2.arcLength(max_contour, True)
        approx = cv2.approxPolyDP(max_contour, epsilon, True)
        
        # 如果不是四边形，使用最小外接矩形
        if len(approx) != 4:
            rect = cv2.minAreaRect(max_contour)
            box = cv2.boxPoints(rect)
            approx = box.reshape(4, 1, 2)
        
        pts = approx.reshape(4, 2).astype(np.float32)
        pts = self._order_points(pts)
        
        # 计算目标尺寸（加上边距）
        margin = opts.perspective_margin
        width_a = np.linalg.norm(pts[2] - pts[3])
        width_b = np.linalg.norm(pts[1] - pts[0])
        max_width = int(max(width_a, width_b) * (1 + margin * 2))
        
        height_a = np.linalg.norm(pts[1] - pts[2])
        height_b = np.linalg.norm(pts[0] - pts[3])
        max_height = int(max(height_a, height_b) * (1 + margin * 2))
        
        # 目标点（加上边距偏移）
        margin_w = int(max_width * margin / (1 + margin * 2))
        margin_h = int(max_height * margin / (1 + margin * 2))
        
        dst = np.array([
            [margin_w, margin_h],
            [max_width - margin_w - 1, margin_h],
            [max_width - margin_w - 1, max_height - margin_h - 1],
            [margin_w, max_height - margin_h - 1]
        ], dtype=np.float32)
        
        matrix = cv2.getPerspectiveTransform(pts, dst)
        warped = cv2.warpPerspective(
            image, matrix, (max_width, max_height),
            borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255)
        )
        
        confidence = min(area_ratio * 1.5, 1.0)
        return warped, confidence
    
    def _order_points(self, pts: np.ndarray) -> np.ndarray:
        """按顺序排列四个点（左上、右上、右下、左下）.
        
        Args:
            pts: 四个点的数组
            
        Returns:
            排序后的点
        """
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]  # 左上
        rect[2] = pts[np.argmax(s)]  # 右下
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]  # 右上
        rect[3] = pts[np.argmax(diff)]  # 左下
        return rect
    
    def _correct_rotation(
        self,
        image: np.ndarray,
        opts: PreprocessOptions,
    ) -> Tuple[np.ndarray, float]:
        """旋转校正.
        
        检测文本方向并旋转图像。
        
        Args:
            image: 输入图像
            opts: 预处理选项
            
        Returns:
            (旋转后的图像, 旋转角度)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, 100, minLineLength=100, maxLineGap=10
        )
        
        if lines is None or len(lines) < 5:
            return image, 0.0
        
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if abs(x2 - x1) > 10:  # 避免垂直线
                angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                # 归一化到 -45 到 45 度
                while angle < -45:
                    angle += 90
                while angle > 45:
                    angle -= 90
                if abs(angle) < 30:  # 排除极端角度
                    angles.append(angle)
        
        if not angles:
            return image, 0.0
        
        median_angle = np.median(angles)
        if abs(median_angle) < 0.5:
            return image, 0.0
        
        # 旋转
        center = (image.shape[1] // 2, image.shape[0] // 2)
        matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        
        cos = np.abs(matrix[0, 0])
        sin = np.abs(matrix[0, 1])
        new_w = int(image.shape[0] * sin + image.shape[1] * cos)
        new_h = int(image.shape[0] * cos + image.shape[1] * sin)
        
        matrix[0, 2] += (new_w - image.shape[1]) / 2
        matrix[1, 2] += (new_h - image.shape[0]) / 2
        
        rotated = cv2.warpAffine(
            image, matrix, (new_w, new_h),
            borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255)
        )
        
        return rotated, median_angle
    
    def _remove_border_only(
        self,
        image: np.ndarray,
        opts: PreprocessOptions,
    ) -> np.ndarray:
        """仅去除边缘干扰，不处理内容区域.
        
        Args:
            image: 输入图像
            opts: 预处理选项
            
        Returns:
            去除边缘后的图像
        """
        h, w = image.shape[:2]
        
        # 创建一个略微缩小的ROI，裁剪边缘
        border = int(min(h, w) * 0.01)  # 1%边距
        
        # 复制图像并裁剪边缘
        result = image[border:h-border, border:w-border].copy()
        
        # 添加白色边框回来
        result = cv2.copyMakeBorder(
            result, border, border, border, border,
            cv2.BORDER_CONSTANT, value=(255, 255, 255)
        )
        
        return result
    
    def _auto_crop_content(
        self,
        image: np.ndarray,
        opts: PreprocessOptions,
    ) -> Tuple[np.ndarray, Optional[str]]:
        """智能裁剪 - 检测纸张边缘并裁剪.
        
        针对作业照片优化：
        1. 先去除纯白色边框（旋转填充区域）
        2. 检测纸张（浅色）与背景（桌面/深色）的边界
        
        Args:
            image: 输入图像
            opts: 预处理选项
            
        Returns:
            (裁剪后的图像, 裁剪信息字符串)
        """
        # 转换为灰度图
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # 步骤1: 先去除纯白色边框（旋转填充区域）
        # 找到非白色区域（实际内容）
        _, non_white = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
        
        # 找到非白色区域的边界
        coords = cv2.findNonZero(non_white)
        if coords is not None:
            x, y, w, h = cv2.boundingRect(coords)
            # 检查是否有效裁剪（至少保留50%区域）
            if w > image.shape[1] * 0.5 and h > image.shape[0] * 0.5:
                margin = opts.content_margin
                min_x = max(0, x - margin)
                min_y = max(0, y - margin)
                max_x = min(image.shape[1], x + w + margin)
                max_y = min(image.shape[0], y + h + margin)
                image = image[min_y:max_y, min_x:max_x]
                gray = gray[min_y:max_y, min_x:max_x]
        
        # 步骤2: 在新的图像上检测纸张边缘
        # 使用自适应阈值检测纸张区域
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # 检测纸张（亮色区域）vs 背景（深色）
        _, paper_mask = cv2.threshold(blurred, opts.white_threshold, 255, cv2.THRESH_BINARY)
        
        # 形态学操作清理噪声
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
        paper_mask = cv2.morphologyEx(paper_mask, cv2.MORPH_CLOSE, kernel)
        paper_mask = cv2.morphologyEx(paper_mask, cv2.MORPH_OPEN, kernel)
        
        # 查找纸张轮廓
        contours, _ = cv2.findContours(paper_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return image, None
        
        # 找到最大的轮廓（应该是纸张）
        max_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(max_contour)
        total_area = image.shape[0] * image.shape[1]
        area_ratio = area / total_area
        
        # 检查是否合理（10% - 95%）
        if area_ratio < 0.1 or area_ratio > 0.95:
            return image, None
        
        # 获取纸张的边界框
        x, y, w, h = cv2.boundingRect(max_contour)
        
        # 添加边距
        margin = opts.content_margin
        min_x = max(0, x - margin)
        min_y = max(0, y - margin)
        max_x = min(image.shape[1], x + w + margin)
        max_y = min(image.shape[0], y + h + margin)
        
        # 裁剪
        cropped = image[min_y:max_y, min_x:max_x]
        
        crop_info = f"{image.shape[1]}x{image.shape[0]}->{cropped.shape[1]}x{cropped.shape[0]}"
        
        return cropped, crop_info
    
    def _enhance_contrast_safe(
        self,
        image: np.ndarray,
        opts: PreprocessOptions,
    ) -> np.ndarray:
        """安全的对比度增强 - 不过度处理.
        
        使用轻度CLAHE和锐化，避免文字失真。
        
        Args:
            image: 输入图像
            opts: 预处理选项
            
        Returns:
            对比度增强后的图像
        """
        # 转换到LAB颜色空间
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # 使用保守的参数
        clahe = cv2.createCLAHE(
            clipLimit=opts.clahe_clip_limit,
            tileGridSize=(opts.clahe_grid_size, opts.clahe_grid_size)
        )
        l = clahe.apply(l)
        
        # 合并通道
        enhanced = cv2.merge([l, a, b])
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
        
        # 轻度锐化
        kernel = np.array([[-0.5, -0.5, -0.5],
                          [-0.5,  5,   -0.5],
                          [-0.5, -0.5, -0.5]])
        sharpened = cv2.filter2D(enhanced, -1, kernel)
        
        # 限制范围
        sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)
        
        return sharpened
    
    def save(
        self,
        image: np.ndarray,
        output_path: Union[str, Path],
        options: Optional[PreprocessOptions] = None,
    ) -> str:
        """保存处理后的图像.
        
        Args:
            image: OpenCV格式的图像
            output_path: 输出路径
            options: 保存选项
            
        Returns:
            保存的文件路径
        """
        opts = options or self.options
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if opts.output_format.lower() == "jpeg" or output_path.suffix.lower() in [".jpg", ".jpeg"]:
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, opts.jpeg_quality]
            cv2.imwrite(str(output_path), image, encode_params)
        else:
            cv2.imwrite(str(output_path), image)
        
        self.logger.info("image_saved", path=str(output_path))
        return str(output_path)
    
    def to_base64(
        self,
        image: np.ndarray,
        options: Optional[PreprocessOptions] = None,
    ) -> str:
        """转换为base64编码.
        
        Args:
            image: OpenCV格式的图像
            options: 编码选项
            
        Returns:
            base64编码的图像数据
        """
        import base64
        
        opts = options or self.options
        
        if opts.output_format.lower() == "jpeg":
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, opts.jpeg_quality]
            _, buffer = cv2.imencode(".jpg", image, encode_params)
        else:
            _, buffer = cv2.imencode(".png", image)
        
        return base64.b64encode(buffer).decode("utf-8")


class ImagePreprocessorPipeline:
    """图像预处理管道.
    
    用于批量处理图像，集成到上传流程中。
    """
    
    def __init__(self, options: Optional[PreprocessOptions] = None):
        """初始化管道.
        
        Args:
            options: 预处理选项
        """
        self.preprocessor = ImagePreprocessor(options)
        self.logger = logger
    
    async def process_upload(
        self,
        image_path: Union[str, Path],
        output_dir: Union[str, Path],
    ) -> PreprocessResult:
        """处理上传的图像.
        
        Args:
            image_path: 上传的图像路径
            output_dir: 输出目录
            
        Returns:
            预处理结果
        """
        import asyncio
        
        # 在后台线程中执行图像处理
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self.preprocessor.process,
            image_path,
        )
        
        if result.success:
            # 生成输出路径
            input_path = Path(image_path)
            output_path = Path(output_dir) / f"{input_path.stem}_processed.jpg"
            
            # 保存结果
            await loop.run_in_executor(
                None,
                self.preprocessor.save,
                result.image,
                output_path,
            )
            
            self.logger.info(
                "upload_processed",
                input=str(image_path),
                output=str(output_path),
                corrections=result.applied_corrections,
            )
        
        return result
