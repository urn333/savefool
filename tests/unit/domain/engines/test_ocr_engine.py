"""OCR识别引擎单元测试."""

import base64
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

from src.domain.engines.ocr_engine import (
    OCREngine,
    OCROptions,
    OCRResult,
    SubjectType,
    ProblemType,
)
from src.infrastructure.models.base import ModelResponse, Usage


@pytest.fixture
def mock_client():
    """创建模拟模型客户端."""
    client = MagicMock()
    client.complete_with_vision = AsyncMock()
    return client


@pytest.fixture
def ocr_engine(mock_client):
    """创建OCR引擎."""
    return OCREngine(mock_client)


@pytest.fixture
def mock_image_path(tmp_path):
    """创建模拟图片文件."""
    image_path = tmp_path / "test_image.jpg"
    image_path.write_bytes(b"fake_image_data")
    return image_path


@pytest.fixture
def mock_ocr_response():
    """创建模拟OCR响应."""
    content = json.dumps({
        "content": "计算：2 + 2 = ?",
        "student_answer": "5",
        "subject": "math",
        "problem_type": "calculation",
        "knowledge_points": ["加法"],
        "confidence": 0.95,
    })
    return ModelResponse(
        content=content,
        model="gpt-4o",
        usage=Usage(prompt_tokens=100, completion_tokens=50),
    )


class TestOCREngine:
    """OCREngine测试."""
    
    @pytest.mark.asyncio
    async def test_recognize_success(self, ocr_engine, mock_image_path, mock_ocr_response):
        """测试正常识别."""
        ocr_engine.client.complete_with_vision.return_value = mock_ocr_response
        
        result = await ocr_engine.recognize(mock_image_path)
        
        assert result.success == True
        assert result.content == "计算：2 + 2 = ?"
        assert result.student_answer == "5"
        assert result.subject == "math"
        assert result.problem_type == "calculation"
        assert result.confidence == 0.95
        assert len(result.knowledge_points) == 1
    
    @pytest.mark.asyncio
    async def test_recognize_with_subject_hint(self, ocr_engine, mock_image_path, mock_ocr_response):
        """测试带学科提示的识别."""
        ocr_engine.client.complete_with_vision.return_value = mock_ocr_response
        
        result = await ocr_engine.recognize(mock_image_path, subject_hint="数学")
        
        assert result.success == True
        # 验证提示中包含了学科信息
        call_args = ocr_engine.client.complete_with_vision.call_args
        messages = call_args[1]["messages"]
        assert "数学" in messages[1].content
    
    @pytest.mark.asyncio
    async def test_recognize_file_not_found(self, ocr_engine):
        """测试文件不存在."""
        result = await ocr_engine.recognize("/nonexistent/path.jpg")
        
        assert result.success == False
        assert "not found" in result.error.lower() or "不存在" in result.error
    
    @pytest.mark.asyncio
    async def test_recognize_api_error(self, ocr_engine, mock_image_path):
        """测试API错误."""
        ocr_engine.client.complete_with_vision.side_effect = Exception("API Error")
        
        result = await ocr_engine.recognize(mock_image_path)
        
        assert result.success == False
        assert "API Error" in result.error
    
    @pytest.mark.asyncio
    async def test_recognize_batch(self, ocr_engine, tmp_path, mock_ocr_response):
        """测试批量识别."""
        ocr_engine.client.complete_with_vision.return_value = mock_ocr_response
        
        # 创建多个测试图片
        image_paths = []
        for i in range(3):
            path = tmp_path / f"test_{i}.jpg"
            path.write_bytes(b"fake_data")
            image_paths.append(path)
        
        results = await ocr_engine.recognize_batch(image_paths)
        
        assert len(results) == 3
        assert all(r.success for r in results)
    
    def test_read_image(self, ocr_engine, mock_image_path):
        """测试图片读取."""
        base64_data = ocr_engine._read_image(mock_image_path)
        
        assert isinstance(base64_data, str)
        # 验证是有效的base64
        decoded = base64.b64decode(base64_data)
        assert decoded == b"fake_image_data"
    
    def test_read_image_not_found(self, ocr_engine):
        """测试读取不存在的图片."""
        with pytest.raises(FileNotFoundError):
            ocr_engine._read_image("/nonexistent/path.jpg")
    
    def test_parse_response_json(self, ocr_engine):
        """测试JSON响应解析."""
        response = ModelResponse(
            content=json.dumps({
                "content": "题目内容",
                "student_answer": "答案",
                "subject": "math",
                "problem_type": "choice",
                "knowledge_points": ["知识点1", "知识点2"],
                "confidence": 0.9,
            }),
            model="gpt-4o",
        )
        
        result = ocr_engine._parse_response(response)
        
        assert result.success == True
        assert result.content == "题目内容"
        assert result.student_answer == "答案"
        assert result.subject == "math"
        assert result.problem_type == "choice"
        assert len(result.knowledge_points) == 2
    
    def test_parse_response_markdown(self, ocr_engine):
        """测试Markdown代码块解析."""
        response = ModelResponse(
            content='```json\n{"content": "题目", "subject": "math", "confidence": 0.8}\n```',
            model="gpt-4o",
        )
        
        result = ocr_engine._parse_response(response)
        
        assert result.success == True
        assert result.content == "题目"
        assert result.confidence == 0.8
    
    def test_parse_response_fallback(self, ocr_engine):
        """测试降级解析."""
        response = ModelResponse(
            content="这是非JSON格式的响应文本",
            model="gpt-4o",
        )
        
        result = ocr_engine._parse_response(response)
        
        assert result.success == True
        assert result.content == "这是非JSON格式的响应文本"
        assert result.subject == "unknown"
        assert result.confidence == 0.5
    
    def test_parse_response_invalid_subject(self, ocr_engine):
        """测试无效学科处理."""
        response = ModelResponse(
            content=json.dumps({
                "content": "题目",
                "subject": "invalid_subject",
                "problem_type": "invalid_type",
                "confidence": 0.8,
            }),
            model="gpt-4o",
        )
        
        result = ocr_engine._parse_response(response)
        
        assert result.subject == "unknown"
        assert result.problem_type == "unknown"
    
    def test_parse_response_string_knowledge_points(self, ocr_engine):
        """测试字符串形式的知识点."""
        response = ModelResponse(
            content=json.dumps({
                "content": "题目",
                "knowledge_points": "知识点1,知识点2,知识点3",
                "confidence": 0.8,
            }),
            model="gpt-4o",
        )
        
        result = ocr_engine._parse_response(response)
        
        assert len(result.knowledge_points) == 3
        assert "知识点1" in result.knowledge_points
    
    @pytest.mark.asyncio
    async def test_extract_text_only(self, ocr_engine, mock_image_path, mock_ocr_response):
        """测试仅提取文本."""
        ocr_engine.client.complete_with_vision.return_value = mock_ocr_response
        
        text = await ocr_engine.extract_text_only(mock_image_path)
        
        assert text == "计算：2 + 2 = ?"
    
    @pytest.mark.asyncio
    async def test_extract_text_only_failed(self, ocr_engine, mock_image_path):
        """测试提取文本失败."""
        ocr_engine.client.complete_with_vision.side_effect = Exception("Error")
        
        text = await ocr_engine.extract_text_only(mock_image_path)
        
        assert text == ""
    
    def test_estimate_confidence_high(self, ocr_engine):
        """测试高置信度评估."""
        result = OCRResult(success=True, confidence=0.85)
        
        level = ocr_engine.estimate_confidence(result)
        
        assert level == "high"
    
    def test_estimate_confidence_medium(self, ocr_engine):
        """测试中置信度评估."""
        result = OCRResult(success=True, confidence=0.7)
        
        level = ocr_engine.estimate_confidence(result)
        
        assert level == "medium"
    
    def test_estimate_confidence_low(self, ocr_engine):
        """测试低置信度评估."""
        result = OCRResult(success=True, confidence=0.5)
        
        level = ocr_engine.estimate_confidence(result)
        
        assert level == "low"


class TestOCRResult:
    """OCRResult测试."""
    
    def test_to_parsed_problem(self):
        """测试转换为ParsedProblem."""
        result = OCRResult(
            success=True,
            content="题目内容",
            student_answer="答案",
            subject="math",
            problem_type="calculation",
            knowledge_points=["加法"],
            confidence=0.9,
        )
        
        from src.domain.engines.model_schedulers import ParsedProblem
        parsed = result.to_parsed_problem()
        
        assert isinstance(parsed, ParsedProblem)
        assert parsed.content == "题目内容"
        assert parsed.student_answer == "答案"
        assert parsed.subject == "math"
        assert parsed.problem_type == "calculation"
        assert parsed.knowledge_points == ["加法"]
    
    def test_to_parsed_problem_unknown_subject(self):
        """测试未知学科转换."""
        result = OCRResult(
            success=True,
            content="题目",
            subject="unknown",
            problem_type="unknown",
        )
        
        parsed = result.to_parsed_problem()
        
        assert parsed.subject is None
        assert parsed.problem_type is None
    
    def test_default_values(self):
        """测试默认值."""
        result = OCRResult()
        
        assert result.success == False
        assert result.content == ""
        assert result.student_answer is None
        assert result.subject == "unknown"
        assert result.problem_type == "unknown"
        assert result.knowledge_points == []
        assert result.confidence == 0.0
        assert result.raw_response == ""
        assert result.error is None


class TestOCROptions:
    """OCROptions测试."""
    
    def test_default_values(self):
        """测试默认值."""
        options = OCROptions()
        
        assert options.detect_subject == True
        assert options.detect_problem_type == True
        assert options.extract_student_answer == True
        assert options.language_hint == "zh"
    
    def test_custom_values(self):
        """测试自定义值."""
        options = OCROptions(
            detect_subject=False,
            detect_problem_type=False,
            extract_student_answer=False,
            language_hint="en",
        )
        
        assert options.detect_subject == False
        assert options.detect_problem_type == False
        assert options.extract_student_answer == False
        assert options.language_hint == "en"


class TestSubjectType:
    """SubjectType测试."""
    
    def test_subject_values(self):
        """测试学科值."""
        assert SubjectType.MATH == "math"
        assert SubjectType.PHYSICS == "physics"
        assert SubjectType.CHEMISTRY == "chemistry"
        assert SubjectType.UNKNOWN == "unknown"


class TestProblemType:
    """ProblemType测试."""
    
    def test_problem_type_values(self):
        """测试题目类型值."""
        assert ProblemType.CHOICE == "choice"
        assert ProblemType.FILL_BLANK == "fill_blank"
        assert ProblemType.CALCULATION == "calculation"
        assert ProblemType.APPLICATION == "application"
        assert ProblemType.PROOF == "proof"
        assert ProblemType.UNKNOWN == "unknown"
