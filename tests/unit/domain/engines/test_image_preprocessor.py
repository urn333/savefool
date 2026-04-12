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
        assert opts.remove_background is True
        assert opts.enhance_contrast is True
        assert opts.target_dpi == 150
        assert opts.jpeg_quality == 85
    
    def test_custom_options(self):
        """测试自定义选项."""
        opts = PreprocessOptions(
            correct_perspective=False,
            enhance_contrast=False,
            jpeg_quality=90,
        )
        assert opts.correct_perspective is False
        assert opts.correct_rotation is True
        assert opts.enhance_contrast is False
        assert opts.jpeg_quality == 90


class TestImagePreprocessor:
    """图像预处理器测试."""
    
    @pytest.fixture
    def preprocessor(self):
        """创建预处理器实例."""
        return ImagePreprocessor()
    
    @pytest.fixture
    def sample_image(self):
        """创建测试图像."""
        # 创建一个模拟的作业纸张图像（白色背景，黑色边框）
        image = np.ones((800, 600, 3), dtype=np.uint8) * 255
        # 添加黑色边框模拟纸张
        cv2 = pytest.importorskip("cv2")
        cv2.rectangle(image, (50, 50), (550, 750), (0, 0, 0), 3)
        # 添加一些文字区域
        cv2.rectangle(image, (100, 100), (500, 200), (0, 0, 0), -1)
        return image
    
    def test_initialization(self, preprocessor):
        """测试初始化."""
        assert preprocessor.options is not None
        assert preprocessor.options.correct_perspective is True
    
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
    
    def test_enhance_contrast(self, preprocessor, sample_image):
        """测试对比度增强."""
        opts = PreprocessOptions()
        
        result = preprocessor._enhance_contrast(sample_image, opts)
        
        assert result is not None
        assert result.shape == sample_image.shape
        assert result.dtype == sample_image.dtype
    
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
        input_path = tmp_path / "test_input.jpg"
        cv2.imwrite(str(input_path), test_image)
        
        output_dir = tmp_path / "output"
        
        # 处理上传
        result = await pipeline.process_upload(input_path, output_dir)
        
        assert isinstance(result, PreprocessResult)
        # 注意：实际处理可能失败（取决于图像内容）
        # 但不应该抛出异常


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
            applied_corrections=["perspective", "contrast_enhancement"],
            confidence=0.85,
        )
        
        assert result.success is True
        assert len(result.applied_corrections) == 2
        assert result.confidence == 0.85


class TestPreprocessIntegration:
    """集成测试（需要实际图像文件）."""
    
    @pytest.fixture
    def sample_image_path(self, tmp_path):
        """创建测试图像文件."""
        cv2 = pytest.importorskip("cv2")
        
        # 创建一张带有透视变形的模拟作业图像
        image = np.ones((1200, 900, 3), dtype=np.uint8) * 255
        
        # 绘制一个倾斜的四边形模拟纸张
        pts = np.array([
            [100, 150],   # 左上（偏移）
            [800, 100],   # 右上（偏移）
            [850, 1100],  # 右下（偏移）
            [150, 1050],  # 左下（偏移）
        ], np.int32)
        
        # 填充白色，边框黑色
        cv2.fillPoly(image, [pts], (255, 255, 255))
        cv2.polylines(image, [pts], True, (0, 0, 0), 3)
        
        # 添加一些"文字"区域
        cv2.rectangle(image, (200, 300), (700, 400), (50, 50, 50), -1)
        cv2.rectangle(image, (200, 500), (700, 600), (50, 50, 50), -1)
        
        # 保存
        image_path = tmp_path / "homework_sample.jpg"
        cv2.imwrite(str(image_path), image)
        
        return image_path
    
    def test_full_preprocess_pipeline(self, sample_image_path, tmp_path):
        """测试完整预处理流程."""
        cv2 = pytest.importorskip("cv2")
        
        preprocessor = ImagePreprocessor()
        
        # 处理图像
        result = preprocessor.process(sample_image_path)
        
        # 验证结果结构
        assert isinstance(result, PreprocessResult)
        
        if result.success:
            # 验证处理效果
            assert result.image is not None
            assert len(result.applied_corrections) > 0
            
            # 保存结果
            output_path = tmp_path / "processed.jpg"
            preprocessor.save(result.image, output_path)
            
            # 验证输出文件
            assert output_path.exists()
            saved_image = cv2.imread(str(output_path))
            assert saved_image is not None
