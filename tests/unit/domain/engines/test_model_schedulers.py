"""模型调度器单元测试."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.domain.engines.model_schedulers import (
    ModelAScheduler,
    ModelBScheduler,
    ModelCScheduler,
    ParsedProblem,
    SchedulerConfig,
)
from src.infrastructure.models.base import ModelResponse, Usage
from src.domain.models.diagnosis import ErrorType


@pytest.fixture
def mock_client():
    """创建模拟模型客户端."""
    client = MagicMock()
    client.complete = AsyncMock()
    client.complete_with_vision = AsyncMock()
    return client


@pytest.fixture
def scheduler_config():
    """创建调度器配置."""
    return SchedulerConfig(
        model_id="test_model",
        model_name="gpt-4",
        temperature=0.7,
        max_tokens=2048,
        timeout=10.0,
        weight=1.0,
    )


@pytest.fixture
def sample_problem():
    """创建示例题目."""
    return ParsedProblem(
        content="计算：2 + 2 = ?",
        student_answer="5",
        subject="math",
        problem_type="calculation",
        knowledge_points=["加法"],
    )


@pytest.fixture
def mock_response():
    """创建模拟响应."""
    return ModelResponse(
        content='{"is_correct": false, "error_type": "计算错误", "confidence": 0.9}',
        model="gpt-4",
        usage=Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
    )


class TestModelAScheduler:
    """ModelAScheduler测试."""
    
    @pytest.mark.asyncio
    async def test_schedule_success(self, mock_client, scheduler_config, sample_problem, mock_response):
        """测试正常调度."""
        mock_client.complete.return_value = mock_response
        
        scheduler = ModelAScheduler(mock_client, scheduler_config)
        result = await scheduler.schedule(sample_problem)
        
        assert result.model_id == "test_model"
        assert result.is_correct == False
        assert result.confidence == 0.9
        assert result.error_type == ErrorType.CALCULATION_ERROR
        assert result.latency_ms > 0
    
    @pytest.mark.asyncio
    async def test_schedule_with_images(self, mock_client, scheduler_config, sample_problem, mock_response):
        """测试带图片的调度."""
        mock_client.complete_with_vision.return_value = mock_response
        
        scheduler = ModelAScheduler(mock_client, scheduler_config)
        result = await scheduler.schedule(sample_problem, images=["base64_image"])
        
        assert result.model_id == "test_model"
        mock_client.complete_with_vision.assert_called_once()
    
    def test_build_prompt(self, mock_client, scheduler_config, sample_problem):
        """测试提示构建."""
        scheduler = ModelAScheduler(mock_client, scheduler_config)
        messages = scheduler.build_prompt(sample_problem)
        
        assert len(messages) == 2
        assert messages[0].role.value == "system"
        assert messages[1].role.value == "user"
        assert "2 + 2" in messages[1].content
    
    def test_parse_response_json(self, mock_client, scheduler_config):
        """测试JSON响应解析."""
        scheduler = ModelAScheduler(mock_client, scheduler_config)
        
        response = ModelResponse(
            content='{"is_correct": false, "error_type": "概念理解", "confidence": 0.85, "knowledge_points": ["分数"]}',
            model="gpt-4",
        )
        
        parsed = scheduler.parse_response(response)
        
        assert parsed["is_correct"] == False
        assert parsed["confidence"] == 0.85
        assert parsed["error_type"] == ErrorType.CONCEPT_MISUNDERSTANDING
    
    def test_parse_response_markdown(self, mock_client, scheduler_config):
        """测试Markdown代码块解析."""
        scheduler = ModelAScheduler(mock_client, scheduler_config)
        
        response = ModelResponse(
            content='```json\n{"is_correct": true, "confidence": 0.95}\n```',
            model="gpt-4",
        )
        
        parsed = scheduler.parse_response(response)
        
        assert parsed["is_correct"] == True
        assert parsed["confidence"] == 0.95
    
    def test_parse_response_fallback(self, mock_client, scheduler_config):
        """测试降级解析."""
        scheduler = ModelAScheduler(mock_client, scheduler_config)
        
        response = ModelResponse(
            content="这是一个非JSON格式的响应",
            model="gpt-4",
        )
        
        parsed = scheduler.parse_response(response)
        
        assert "analysis" in parsed["diagnosis"]
        assert parsed["confidence"] == 0.5
    
    def test_map_error_type(self, mock_client, scheduler_config):
        """测试错误类型映射."""
        scheduler = ModelAScheduler(mock_client, scheduler_config)
        
        assert scheduler._map_error_type("计算错误") == ErrorType.CALCULATION_ERROR
        assert scheduler._map_error_type("逻辑问题") == ErrorType.LOGICAL_FLAW
        assert scheduler._map_error_type("概念不清") == ErrorType.CONCEPT_MISUNDERSTANDING
        assert scheduler._map_error_type("粗心") == ErrorType.CARELESS_MISTAKE
        assert scheduler._map_error_type("知识空白") == ErrorType.KNOWLEDGE_GAP
        assert scheduler._map_error_type("未知错误") == ErrorType.KNOWLEDGE_GAP  # 默认


class TestModelBScheduler:
    """ModelBScheduler测试."""
    
    @pytest.mark.asyncio
    async def test_schedule_success(self, mock_client, scheduler_config, sample_problem):
        """测试正常调度."""
        response = ModelResponse(
            content='{"is_correct": false, "first_error_step": 2, "logic_score": 0.6, "confidence": 0.8}',
            model="deepseek-math",
        )
        mock_client.complete.return_value = response
        
        scheduler = ModelBScheduler(mock_client, scheduler_config)
        result = await scheduler.schedule(sample_problem)
        
        assert result.model_id == "test_model"
        assert result.is_correct == False
        assert result.error_type == ErrorType.LOGICAL_FLAW
    
    def test_parse_response_with_steps(self, mock_client, scheduler_config):
        """测试带步骤的响应解析."""
        scheduler = ModelBScheduler(mock_client, scheduler_config)
        
        response = ModelResponse(
            content='''{
                "steps": [
                    {"step": 1, "content": "步骤1", "is_correct": true},
                    {"step": 2, "content": "步骤2", "is_correct": false}
                ],
                "first_error_step": 2,
                "is_correct": false,
                "logic_score": 0.7,
                "confidence": 0.85,
                "error_analysis": "逻辑推理错误"
            }''',
            model="deepseek-math",
        )
        
        parsed = scheduler.parse_response(response)
        
        assert parsed["is_correct"] == False
        assert len(parsed["diagnosis"]["steps"]) == 2
        assert parsed["diagnosis"]["first_error_step"] == 2
        assert parsed["concept_scores"]["logic"] == 0.7
    
    def test_parse_response_calculation_error(self, mock_client, scheduler_config):
        """测试计算错误的响应解析."""
        scheduler = ModelBScheduler(mock_client, scheduler_config)
        
        response = ModelResponse(
            content='{"is_correct": false, "error_analysis": "计算步骤出错", "confidence": 0.9}',
            model="deepseek-math",
        )
        
        parsed = scheduler.parse_response(response)
        
        assert parsed["error_type"] == ErrorType.CALCULATION_ERROR


class TestModelCScheduler:
    """ModelCScheduler测试."""
    
    @pytest.mark.asyncio
    async def test_schedule_success(self, mock_client, scheduler_config, sample_problem):
        """测试正常调度."""
        response = ModelResponse(
            content='{"is_correct": false, "root_cause": "概念理解不清", "confidence": 0.8}',
            model="llama-3-70b",
        )
        mock_client.complete.return_value = response
        
        scheduler = ModelCScheduler(mock_client, scheduler_config)
        result = await scheduler.schedule(sample_problem)
        
        assert result.model_id == "test_model"
        assert result.is_correct == False
    
    def test_build_prompt_with_intermediate(self, mock_client, scheduler_config, sample_problem):
        """测试带中间结果的提示构建."""
        scheduler = ModelCScheduler(mock_client, scheduler_config)
        
        intermediate = [{"analysis": "初步分析"}, {"logic": "逻辑检查"}]
        messages = scheduler.build_prompt(sample_problem, intermediate_results=intermediate)
        
        assert len(messages) == 2
        assert "初步分析" in messages[1].content
        assert "逻辑检查" in messages[1].content
    
    def test_parse_response_concept_map(self, mock_client, scheduler_config):
        """测试概念映射解析."""
        scheduler = ModelCScheduler(mock_client, scheduler_config)
        
        response = ModelResponse(
            content='''{
                "concept_map": {"分数": ["分子", "分母"]},
                "root_cause": "分数概念不清",
                "attribution_valid": true,
                "concept_gaps": ["分数比较"],
                "is_correct": false,
                "confidence": 0.85,
                "cross_validation": "验证通过"
            }''',
            model="llama-3-70b",
        )
        
        parsed = scheduler.parse_response(response)
        
        assert parsed["is_correct"] == False
        assert "分数" in parsed["diagnosis"]["concept_map"]
        assert parsed["diagnosis"]["root_cause"] == "分数概念不清"
        assert len(parsed["concept_scores"]) == 1  # 1个概念缺口
    
    def test_error_type_mapping(self, mock_client, scheduler_config):
        """测试错误类型映射."""
        scheduler = ModelCScheduler(mock_client, scheduler_config)
        
        # 测试概念错误
        result1 = ModelResponse(
            content='{"is_correct": false, "root_cause": "概念理解不清"}',
            model="llama-3-70b",
        )
        parsed1 = scheduler.parse_response(result1)
        assert parsed1["error_type"] == ErrorType.CONCEPT_MISUNDERSTANDING
        
        # 测试知识缺口
        result2 = ModelResponse(
            content='{"is_correct": false, "root_cause": "知识点缺失"}',
            model="llama-3-70b",
        )
        parsed2 = scheduler.parse_response(result2)
        assert parsed2["error_type"] == ErrorType.KNOWLEDGE_GAP
        
        # 测试粗心
        result3 = ModelResponse(
            content='{"is_correct": false, "root_cause": "不够仔细"}',
            model="llama-3-70b",
        )
        parsed3 = scheduler.parse_response(result3)
        assert parsed3["error_type"] == ErrorType.CARELESS_MISTAKE


class TestParsedProblem:
    """ParsedProblem测试."""
    
    def test_creation(self):
        """测试创建."""
        problem = ParsedProblem(
            content="题目内容",
            student_answer="答案",
            subject="math",
        )
        
        assert problem.content == "题目内容"
        assert problem.student_answer == "答案"
        assert problem.subject == "math"
        assert problem.problem_type is None
        assert problem.knowledge_points == []
    
    def test_default_values(self):
        """测试默认值."""
        problem = ParsedProblem(content="仅内容")
        
        assert problem.student_answer is None
        assert problem.subject is None
        assert problem.problem_type is None
        assert problem.knowledge_points == []
