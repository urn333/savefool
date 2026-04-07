"""启发式讲解生成引擎测试."""

import pytest
from unittest.mock import MagicMock

from src.domain.engines.explanation_generator import (
    ExplanationGenerator,
    ExplanationResult,
    ExplanationContent,
)
from src.domain.engines.error_attribution import ErrorAttributionResult, AttributionFactor
from src.domain.models.diagnosis import ErrorType


@pytest.fixture
def generator():
    """创建讲解生成器."""
    return ExplanationGenerator()


@pytest.fixture
def sample_attribution_result():
    """创建示例归因结果."""
    return ErrorAttributionResult(
        problem_id="prob_123",
        student_id="stu_456",
        primary_cause="计算错误",
        secondary_causes=["方法不熟练"],
        error_type=ErrorType.CALCULATION_ERROR,
        confidence=0.85,
        knowledge_gaps=["分数加法", "通分"],
        is_careless_pattern=False,
        historical_similarity=0.3,
        factors=[
            AttributionFactor(
                factor_type="knowledge_gap",
                description="知识缺口",
                weight=0.5,
            ),
        ],
        recommendations=["多做练习"],
    )


class TestExplanationGenerator:
    """讲解生成引擎测试类."""
    
    @pytest.mark.asyncio
    async def test_generate_basic(self, generator, sample_attribution_result):
        """测试基础讲解生成."""
        result = await generator.generate(
            attribution_result=sample_attribution_result,
            problem_content="计算：1/2 + 1/3 = ?",
        )
        
        assert isinstance(result, ExplanationResult)
        assert result.problem_id == "prob_123"
        assert result.student_id == "stu_456"
        assert result.content is not None
        assert result.safety_score > 0
        assert result.estimated_reading_time > 0
    
    @pytest.mark.asyncio
    async def test_generate_main_explanation(self, generator, sample_attribution_result):
        """测试主要讲解生成."""
        main = generator._generate_main_explanation(
            sample_attribution_result,
            "计算：1/2 + 1/3 = ?",
            None,
        )
        
        # 检查主要讲解包含关键信息
        assert "计算" in main  # 计算错误类型应该被提及
        assert "计算错误" in main  # 主要原因应该被包含
        assert "分数加法" in main or "知识" in main or "知识点" in main
    
    @pytest.mark.asyncio
    async def test_generate_analogy(self, generator):
        """测试类比生成."""
        attribution = MagicMock()
        attribution.error_type = ErrorType.CALCULATION_ERROR
        
        analogy = generator._generate_analogy(attribution)
        
        assert "💡" in analogy
        assert "比如" in analogy or "就像" in analogy or "打个比方" in analogy
    
    @pytest.mark.asyncio
    async def test_generate_step_hints(self, generator):
        """测试分步提示生成."""
        attribution = MagicMock()
        attribution.error_type = ErrorType.CALCULATION_ERROR
        
        hints = generator._generate_step_hints(attribution, None)
        
        assert len(hints) > 0
        assert all("✓" in h for h in hints)
    
    @pytest.mark.asyncio
    async def test_generate_step_hints_careless(self, generator):
        """测试粗心情况的分步提示."""
        attribution = MagicMock()
        attribution.error_type = ErrorType.CARELESS_MISTAKE
        
        hints = generator._generate_step_hints(attribution, None)
        
        assert len(hints) > 0
        assert any("验算" in h or "检查" in h for h in hints)
    
    @pytest.mark.asyncio
    async def test_generate_key_points(self, generator):
        """测试关键点生成."""
        attribution = MagicMock()
        attribution.is_careless_pattern = False
        attribution.historical_similarity = 0.2
        attribution.knowledge_gaps = ["分数运算"]
        attribution.error_type = ErrorType.CALCULATION_ERROR
        
        points = generator._generate_key_points(attribution)
        
        assert len(points) > 0
    
    @pytest.mark.asyncio
    async def test_generate_visual_description(self, generator):
        """测试可视化描述生成."""
        desc = generator._generate_visual_description(
            "解方程 2x + 5 = 15",
            ErrorType.CALCULATION_ERROR,
        )
        
        assert "🎯" in desc
        assert len(desc) > 0
    
    @pytest.mark.asyncio
    async def test_generate_practice_suggestion(self, generator):
        """测试练习建议生成."""
        attribution = MagicMock()
        attribution.is_careless_pattern = False
        attribution.knowledge_gaps = ["分数加法"]
        attribution.historical_similarity = 0.2
        
        suggestion = generator._generate_practice_suggestion(attribution)
        
        assert "建议" in suggestion
        assert len(suggestion) > 0
    
    def test_check_safety_safe(self, generator):
        """测试安全内容检查."""
        content = ExplanationContent(
            main_explanation="这是一段安全的讲解内容",
            analogy="就像做数学题一样",
            step_hints=["认真读题", "仔细计算"],
            key_points=["注意符号"],
        )
        
        score = generator._check_safety(content)
        
        assert score == 1.0
    
    def test_check_age_appropriateness(self, generator):
        """测试年龄适配检查."""
        content = ExplanationContent(
            main_explanation="这道题需要仔细思考。",
            analogy="就像玩游戏升级一样",
            step_hints=["第一步：读题"],
        )
        
        is_appropriate = generator._check_age_appropriateness(content)
        
        assert is_appropriate is True
    
    def test_estimate_difficulty(self, generator):
        """测试难度估计."""
        easy_content = ExplanationContent(
            main_explanation="简单",
            analogy="比如",
            step_hints=["一步"],
        )
        
        easy_difficulty = generator._estimate_difficulty(easy_content)
        assert easy_difficulty == "easy"
        
        hard_content = ExplanationContent(
            main_explanation="这是一段很长的讲解内容" * 20,
            analogy="比如",
            step_hints=["一", "二", "三", "四"],
        )
        
        hard_difficulty = generator._estimate_difficulty(hard_content)
        assert hard_difficulty == "hard"
    
    def test_estimate_reading_time(self, generator):
        """测试阅读时间估计."""
        content = ExplanationContent(
            main_explanation="这是一段讲解内容" * 50,
            analogy="比如这个",
            step_hints=["第一步", "第二步", "第三步"],
            key_points=["关键点一", "关键点二"],
        )
        
        time = generator._estimate_reading_time(content)
        
        assert 10 <= time <= 120  # 在合理范围内
    
    def test_regenerate_with_adjustment_simplify(self, generator, sample_attribution_result):
        """测试简化调整."""
        original = ExplanationResult(
            problem_id="p1",
            student_id="s1",
            content=ExplanationContent(
                main_explanation="这是一段很长的讲解" * 20,
                analogy="比如",
                step_hints=["一", "二", "三", "四", "五"],
            ),
        )
        
        adjusted = generator.regenerate_with_adjustment(original, "simplify")
        
        assert len(adjusted.content.step_hints) <= 2
        assert adjusted.estimated_reading_time <= generator._estimate_reading_time(original.content)
