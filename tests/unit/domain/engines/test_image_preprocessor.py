"""图像预处理引擎测试."""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch

from src.domain.engines.image_preprocessor import (
    ImagePreprocessor,
    ImagePreprocessorPipeline,
    PreprocessOptions,
    PreprocessResult,
)


class TestPreprocessOptions:
    """预处理选项测试."""
    
    def test_default_options(self):
        """测试默认选项."""
        opts = PreprocessOptions()
        assert opts.correct_perspective is True
        assert opts.correct_rotation is True
        assert opts.remove_background is False  # 默认关闭
        assert opts.enhance_contrast is True
        assert opts.jpeg_quality == 90
        assert opts.perspective_margin == 0.02
    
    def test_custom_options(self):
        """测试自定义选项."""
        opts = PreprocessOptions(
            correct_perspective=False,
            remove_background=True,
            jpeg_quality=95,
        )
        assert opts.correct_perspective is False
        assert opts.remove_background is True
        assert opts.jpeg_quality == 95


class TestImagePreprocessor:
    """图像预处理器测试."""
    
    @pytest.fixture
    def preprocessor(self):
        """创建预处理器实例."""
        return ImagePreprocessor()
    
    @pytest.fixture
    def sample_image(self):
        """创建测试图像（模拟作业纸张）."""
        cv2 = pytest.importorskip("cv2")
        
        # 创建白色背景的模拟纸张
        image = np.ones((800, 600, 3), dtype=np.uint8) * 255
        
        # 添加深色边框模拟纸张边缘
        cv2.rectangle(image, (50, 50), (550, 750), (0, 0, 0), 3)
        
        # 添加模拟文字行
        cv2.rectangle(image, (100, 150), (500, 200), (60, 60, 60), -1)
        cv2.rectangle(image, (100, 300), (500, 350), (60, 60, 60), -1)
        cv2.rectangle(image, (100, 450), (500, 500), (60, 60, 60), -1)
        
        return image
    
    def test_initialization(self, preprocessor):
        """测试初始化."""
        assert preprocessor.options is not None
        assert preprocessor.options.correct_perspective is True
        # 默认关闭背景去除，避免误删文字
        assert preprocessor.options.remove_background is False
    
    def test_process_with_numpy_array(self, preprocessor, sample_image):
        """测试直接处理numpy数组."""
        result = preprocessor.process(sample_image)
        
        assert isinstance(result, PreprocessResult)
        assert result.success is True
        assert result.original_size == (600, 800)
        assert result.image is not None
    
    def test_order_points(self, preprocessor):
        """测试点排序功能."""
        # 创建四个无序的点
        pts = np.array([
            [400, 400],  # 右下
            [100, 100],  # 左上
            [400, 100],  # 右上
            [100, 400],  # 左下
        ], dtype=np.float32)
        
        ordered = preprocessor._order_points(pts)
        
        # 验证顺序：左上、右上、右下、左下
        assert np.allclose(ordered[0], [100, 100])
        assert np.allclose(ordered[1], [400, 100])
        assert np.allclose(ordered[2], [400, 400])
        assert np.allclose(ordered[3], [100, 400])
    
    def test_enhance_contrast_safe(self, preprocessor, sample_image):
        """测试安全的对比度增强."""
        opts = PreprocessOptions()
        
        result = preprocessor._enhance_contrast_safe(sample_image, opts)
        
        assert result is not None
        assert result.shape == sample_image.shape
        assert result.dtype == sample_image.dtype
        # 确保没有溢出
        assert np.all(result >= 0) and np.all(result <= 255)
    
    def test_remove_border_only(self, preprocessor, sample_image):
        """测试仅去除边框."""
        opts = PreprocessOptions()
        
        result = preprocessor._remove_border_only(sample_image, opts)
        
        # 尺寸应该几乎不变（只裁剪了1%边缘）
        assert abs(result.shape[0] - sample_image.shape[0]) < 20
        assert abs(result.shape[1] - sample_image.shape[1]) < 20
    
    def test_to_base64(self, preprocessor, sample_image):
        """测试base64编码."""
        import base64
        
        b64_string = preprocessor.to_base64(sample_image)
        
        assert isinstance(b64_string, str)
        # 验证是有效的base64
        decoded = base64.b64decode(b64_string)
        assert len(decoded) > 0
    
    def test_save_and_load(self, preprocessor, sample_image, tmp_path):
        """测试保存和加载."""
        cv2 = pytest.importorskip("cv2")
        
        output_path = tmp_path / "test_output.jpg"
        
        # 保存
        saved_path = preprocessor.save(sample_image, output_path)
        assert Path(saved_path).exists()
        
        # 加载验证
        loaded = cv2.imread(str(output_path))
        assert loaded is not None
        assert loaded.shape == sample_image.shape
    
    def test_text_preserved_after_processing(self, preprocessor):
        """测试处理后文字区域保留."""
        cv2 = pytest.importorskip("cv2")
        
        # 创建带有明确文字区域的图像
        image = np.ones((600, 400, 3), dtype=np.uint8) * 255
        
        # 绘制一个矩形模拟纸张
        cv2.rectangle(image, (50, 50), (350, 550), (240, 240, 240), -1)
        cv2.rectangle(image, (50, 50), (350, 550), (0, 0, 0), 2)
        
        # 添加文字区域
        cv2.rectangle(image, (80, 150), (320, 180), (50, 50, 50), -1)
        cv2.rectangle(image, (80, 250), (320, 280), (50, 50, 50), -1)
        
        # 处理
        result = preprocessor.process(image)
        
        assert result.success
        # 文字区域应该仍然存在（不为白色）
        processed = result.image
        
        # 检查文字区域是否还有深色像素
        text_region_1 = processed[150:180, 80:320]
        assert np.mean(text_region_1) < 250  # 不是全白


class TestImagePreprocessorPipeline:
    """图像预处理管道测试."""
    
    @pytest.fixture
    def pipeline(self):
        """创建管道实例."""
        return ImagePreprocessorPipeline()
    
    @pytest.mark.asyncio
    async def test_process_upload(self, pipeline, tmp_path):
        """测试上传处理流程."""
        cv2 = pytest.importorskip("cv2")
        
        # 创建测试图像
        test_image = np.ones((800, 600, 3), dtype=np.uint8) * 255
        cv2.rectangle(test_image, (50, 50), (550, 750), (0, 0, 0), 2)
        
        input_path = tmp_path / "test_input.jpg"
        cv2.imwrite(str(input_path), test_image)
        
        output_dir = tmp_path / "output"
        
        # 处理上传
        result = await pipeline.process_upload(input_path, output_dir)
        
        assert isinstance(result, PreprocessResult)
        # 不应该抛出异常


class TestPreprocessResult:
    """预处理结果测试."""
    
    def test_default_result(self):
        """测试默认结果."""
        result = PreprocessResult()
        
        assert result.success is False
        assert result.image is None
        assert result.applied_corrections == []
        assert result.confidence == 0.0
    
    def test_successful_result(self):
        """测试成功结果."""
        result = PreprocessResult(
            success=True,
            image=np.ones((100, 100, 3), dtype=np.uint8),
            original_size=(200, 200),
            processed_size=(100, 100),
            applied_corrections=["perspective(0.95)", "contrast"],
            confidence=0.95,
        )
        
        assert result.success is True
        assert len(result.applied_corrections) == 2
        assert result.confidence == 0.95


class TestPreprocessIntegration:
    """集成测试（需要实际图像文件）."""
    
    @pytest.fixture
    def sample_image_path(self, tmp_path):
        """创建测试图像文件."""
        cv2 = pytest.importorskip("cv2")
        
        # 创建一张模拟作业图像
        image = np.ones((1200, 900, 3), dtype=np.uint8) * 255
        
        # 绘制纸张矩形（轻微倾斜）
        angle = 3
        center = (450, 600)
        pts = np.array([
            [100, 100],
            [800, 120],
            [820, 1100],
            [80, 1080],
        ], np.int32)
        
        cv2.fillPoly(image, [pts], (250, 250, 250))
        cv2.polylines(image, [pts], True, (200, 200, 200), 2)
        
        # 添加文字行
        cv2.rectangle(image, (200, 300), (700, 350), (60, 60, 60), -1)
        cv2.rectangle(image, (200, 450), (700, 500), (60, 60, 60), -1)
        cv2.rectangle(image, (200, 600), (700, 650), (60, 60, 60), -1)
        
        # 保存
        image_path = tmp_path / "homework_sample.jpg"
        cv2.imwrite(str(image_path), image)
        
        return image_path
    
    def test_full_preprocess_pipeline(self, sample_image_path, tmp_path):
        """测试完整预处理流程."""
        cv2 = pytest.importorskip("cv2")
        
        preprocessor = ImagePreprocessor(PreprocessOptions(
            correct_perspective=True,
            correct_rotation=True,
            remove_background=False,  # 关闭，保护文字
            enhance_contrast=True,
        ))
        
        # 处理图像
        result = preprocessor.process(sample_image_path)
        
        # 验证结果结构
        assert isinstance(result, PreprocessResult)
        
        if result.success:
            # 验证处理效果
            assert result.image is not None
            # 验证文字区域没有被删除
            processed = result.image
            # 检查中间区域是否还有深色内容
            center_region = processed[
                processed.shape[0]//3:2*processed.shape[0]//3,
                processed.shape[1]//4:3*processed.shape[1]//4
            ]
            # 应该包含深色像素（文字）
            assert np.any(center_region < 200)
