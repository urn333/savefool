"""图像预处理引擎.

提供作业照片预处理功能：
- 透视校正：自动检测纸张边缘并矫正
- 旋转校正：检测文本方向并旋转
- 去噪/背景去除：消除手指、阴影等干扰
- 对比度增强：自适应直方图均衡化
"""

import logging
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)


class CorrectionMode(Enum):
    """校正模式."""
    NONE = auto()       # 不校正
    AUTO = auto()       # 自动检测并校正
    FORCE_PORTRAIT = auto()  # 强制竖版
    FORCE_LANDSCAPE = auto()  # 强制横版


@dataclass
class PreprocessOptions:
    """预处理选项.
    
    Attributes:
        correct_perspective: 是否进行透视校正
        correct_rotation: 是否进行旋转校正
        remove_background: 是否去除背景/无关内容
        enhance_contrast: 是否增强对比度
        target_dpi: 目标DPI（用于标准化输出）
        output_format: 输出格式（PNG/JPEG）
        jpeg_quality: JPEG质量（1-100）
    """
    correct_perspective: bool = True
    correct_rotation: bool = True
    remove_background: bool = True
    enhance_contrast: bool = True
    target_dpi: int = 150
    output_format: str = "jpeg"
    jpeg_quality: int = 85
    
    # 透视校正参数
    min_contour_area_ratio: float = 0.1  # 最小轮廓面积比例
    approx_accuracy: float = 0.02  # 多边形近似精度
    
    # 对比度增强参数
    clahe_clip_limit: float = 2.0
    clahe_grid_size: int = 8
    
    # 去噪参数
    denoise_strength: int = 10


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
    applied_corrections: list = None
    confidence: float = 0.0
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.applied_corrections is None:
            self.applied_corrections = []


class ImagePreprocessor:
    """图像预处理引擎.
    
    专门处理作业照片的预处理，包括透视校正、旋转校正、
    背景去除和对比度增强。
    
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
            result.image = image.copy()
            
            self.logger.info(
                "preprocess_start",
                original_size=result.original_size,
            )
            
            # 1. 透视校正
            if opts.correct_perspective:
                image, confidence = self._correct_perspective(image, opts)
                if confidence > 0.5:
                    result.applied_corrections.append("perspective")
                    result.confidence = max(result.confidence, confidence)
                    self.logger.debug("perspective_corrected", confidence=confidence)
            
            # 2. 旋转校正
            if opts.correct_rotation:
                image, angle = self._correct_rotation(image, opts)
                if angle != 0:
                    result.applied_corrections.append(f"rotation({angle:.1f}°)")
                    self.logger.debug("rotation_corrected", angle=angle)
            
            # 3. 去除背景/无关内容
            if opts.remove_background:
                image = self._remove_background(image, opts)
                result.applied_corrections.append("background_removal")
                self.logger.debug("background_removed")
            
            # 4. 对比度增强
            if opts.enhance_contrast:
                image = self._enhance_contrast(image, opts)
                result.applied_corrections.append("contrast_enhancement")
                self.logger.debug("contrast_enhanced")
            
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
    
    def _correct_perspective(
        self,
        image: np.ndarray,
        opts: PreprocessOptions,
    ) -> Tuple[np.ndarray, float]:
        """透视校正.
        
        检测纸张边缘并进行透视变换，将倾斜的纸张矫正为正面视角。
        
        Args:
            image: 输入图像
            opts: 预处理选项
            
        Returns:
            (校正后的图像, 置信度)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 边缘检测
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        
        # 膨胀连接边缘
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        edges = cv2.dilate(edges, kernel, iterations=2)
        edges = cv2.erode(edges, kernel, iterations=1)
        
        # 查找轮廓
        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        if not contours:
            return image, 0.0
        
        # 找到最大的轮廓
        max_contour = max(contours, key=cv2.contourArea)
        area_ratio = cv2.contourArea(max_contour) / (image.shape[0] * image.shape[1])
        
        # 轮廓面积太小，可能是干扰
        if area_ratio < opts.min_contour_area_ratio:
            return image, 0.0
        
        # 近似多边形
        epsilon = opts.approx_accuracy * cv2.arcLength(max_contour, True)
        approx = cv2.approxPolyDP(max_contour, epsilon, True)
        
        # 如果不是四边形，尝试使用最小外接矩形
        if len(approx) != 4:
            rect = cv2.minAreaRect(max_contour)
            box = cv2.boxPoints(rect)
            approx = box.reshape(4, 1, 2)
        
        # 确保点是顺时针顺序
        pts = approx.reshape(4, 2).astype(np.float32)
        pts = self._order_points(pts)
        
        # 计算目标尺寸
        width_a = np.linalg.norm(pts[2] - pts[3])
        width_b = np.linalg.norm(pts[1] - pts[0])
        max_width = int(max(width_a, width_b))
        
        height_a = np.linalg.norm(pts[1] - pts[2])
        height_b = np.linalg.norm(pts[0] - pts[3])
        max_height = int(max(height_a, height_b))
        
        # 透视变换
        dst = np.array([
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1]
        ], dtype=np.float32)
        
        matrix = cv2.getPerspectiveTransform(pts, dst)
        warped = cv2.warpPerspective(image, matrix, (max_width, max_height))
        
        # 置信度基于轮廓面积比例
        confidence = min(area_ratio * 2, 1.0)
        
        return warped, confidence
    
    def _order_points(self, pts: np.ndarray) -> np.ndarray:
        """按顺序排列四个点（左上、右上、右下、左下）.
        
        Args:
            pts: 四个点的数组
            
        Returns:
            排序后的点
        """
        rect = np.zeros((4, 2), dtype=np.float32)
        
        # 按坐标和排序
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]  # 左上
        rect[2] = pts[np.argmax(s)]  # 右下
        
        # 按坐标差排序
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
        
        # 使用霍夫变换检测直线
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, 100, minLineLength=100, maxLineGap=10
        )
        
        if lines is None or len(lines) < 5:
            return image, 0.0
        
        # 计算主要角度
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if x2 - x1 != 0:
                angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                # 归一化到 -45 到 45 度
                while angle < -45:
                    angle += 90
                while angle > 45:
                    angle -= 90
                angles.append(angle)
        
        if not angles:
            return image, 0.0
        
        # 使用中位数角度（更鲁棒）
        median_angle = np.median(angles)
        
        # 如果角度很小，不需要旋转
        if abs(median_angle) < 1.0:
            return image, 0.0
        
        # 旋转图像
        center = (image.shape[1] // 2, image.shape[0] // 2)
        matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        
        # 计算新边界
        cos = np.abs(matrix[0, 0])
        sin = np.abs(matrix[0, 1])
        new_w = int(image.shape[0] * sin + image.shape[1] * cos)
        new_h = int(image.shape[0] * cos + image.shape[1] * sin)
        
        # 调整旋转矩阵中心
        matrix[0, 2] += (new_w - image.shape[1]) / 2
        matrix[1, 2] += (new_h - image.shape[0]) / 2
        
        rotated = cv2.warpAffine(
            image, matrix, (new_w, new_h), borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255)
        )
        
        return rotated, median_angle
    
    def _remove_background(
        self,
        image: np.ndarray,
        opts: PreprocessOptions,
    ) -> np.ndarray:
        """去除背景/无关内容.
        
        使用GrabCut算法分离前景（作业）和背景。
        
        Args:
            image: 输入图像
            opts: 预处理选项
            
        Returns:
            去噪后的图像
        """
        # 创建掩码
        mask = np.zeros(image.shape[:2], np.uint8)
        
        # 背景和前景模型
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)
        
        # 初始矩形（假设作业在中心）
        height, width = image.shape[:2]
        margin_x = int(width * 0.05)
        margin_y = int(height * 0.05)
        rect = (margin_x, margin_y, width - 2 * margin_x, height - 2 * margin_y)
        
        # GrabCut
        cv2.grabCut(
            image, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT
        )
        
        # 创建掩码：0和2为背景，1和3为前景
        mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
        
        # 应用掩码
        result = image * mask2[:, :, np.newaxis]
        
        # 背景设为白色
        white_bg = np.ones_like(image) * 255
        white_bg = white_bg * (1 - mask2[:, :, np.newaxis])
        result = result + white_bg
        
        return result
    
    def _enhance_contrast(
        self,
        image: np.ndarray,
        opts: PreprocessOptions,
    ) -> np.ndarray:
        """增强对比度.
        
        使用CLAHE（对比度受限的自适应直方图均衡化）增强文字对比度。
        
        Args:
            image: 输入图像
            opts: 预处理选项
            
        Returns:
            对比度增强后的图像
        """
        # 转换到LAB颜色空间
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # 应用CLAHE到L通道
        clahe = cv2.createCLAHE(
            clipLimit=opts.clahe_clip_limit,
            tileGridSize=(opts.clahe_grid_size, opts.clahe_grid_size)
        )
        l = clahe.apply(l)
        
        # 合并通道
        enhanced = cv2.merge([l, a, b])
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
        
        # 额外的锐化
        kernel = np.array([[-1, -1, -1],
                          [-1,  9, -1],
                          [-1, -1, -1]])
        sharpened = cv2.filter2D(enhanced, -1, kernel)
        
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
            # JPEG 压缩
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, opts.jpeg_quality]
            cv2.imwrite(str(output_path), image, encode_params)
        else:
            # PNG 无损
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
            None,  # 使用默认执行器
            self.preprocessor.process,
            image_path,
            None,  # 使用默认选项
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
