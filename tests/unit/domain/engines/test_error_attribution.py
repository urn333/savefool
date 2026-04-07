"""错误归因分析引擎测试."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from src.domain.engines.error_attribution import (
    ErrorAttributionEngine,
    ErrorAttributionResult,
    AttributionFactor,
)
from src.domain.models.diagnosis import ErrorType
from src.domain.memory.memory_manager import MemoryManager


@pytest.fixture
def mock_memory_manager():
    """创建模拟记忆管理器."""
    mm = MagicMock(spec=MemoryManager)
    
    # 模拟记忆快照
    snapshot = MagicMock()
    snapshot.recent_episodes = []
    snapshot.knowledge_graph = None
    snapshot.pending_gaps = []
    snapshot.profile = None
    
    mm.get_snapshot = AsyncMock(return_value=snapshot)
    
    return mm


@pytest.fixture
def attribution_engine(mock_memory_manager):
    """创建归因分析引擎."""
    return ErrorAttributionEngine(mock_memory_manager)


class TestErrorAttributionEngine:
    """错误归因分析引擎测试类."""
    
    @pytest.mark.asyncio
    async def test_analyze_basic(self, attribution_engine, mock_memory_manager):
        """测试基础归因分析."""
        result = await attribution_engine.analyze(
            student_id="stu_123",
            problem_id="prob_456",
            error_type=ErrorType.CALCULATION_ERROR,
            concept_ids=["addition", "subtraction"],
        )
        
        assert isinstance(result, ErrorAttributionResult)
        assert result.student_id == "stu_123"
        assert result.problem_id == "prob_456"
        assert result.error_type == ErrorType.CALCULATION_ERROR
        assert result.primary_cause is not None
        assert 0 <= result.confidence <= 1
    
    @pytest.mark.asyncio
    async def test_analyze_with_historical_pattern(
        self,
        attribution_engine,
        mock_memory_manager,
    ):
        """测试带有历史模式的归因."""
        # 创建模拟事件
        episode = MagicMock()
        episode.final_result = "incorrect"
        episode.error_type = ErrorType.CALCULATION_ERROR.value
        episode.concept_ids = ["addition"]
        episode.timestamp = datetime.now()
        
        snapshot = MagicMock()
        snapshot.recent_episodes = [episode, episode, episode]  # 3次相同错误
        snapshot.knowledge_graph = None
        snapshot.pending_gaps = []
        snapshot.profile = None
        
        mock_memory_manager.get_snapshot = AsyncMock(return_value=snapshot)
        
        result = await attribution_engine.analyze(
            student_id="stu_123",
            problem_id="prob_456",
            error_type=ErrorType.CALCULATION_ERROR,
            concept_ids=["addition"],
        )
        
        assert result.historical_similarity > 0
        
        # 检查是否有历史模式因子
        historical_factors = [f for f in result.factors if f.factor_type == "historical_pattern"]
        assert len(historical_factors) > 0
    
    @pytest.mark.asyncio
    async def test_analyze_with_knowledge_gaps(
        self,
        attribution_engine,
        mock_memory_manager,
    ):
        """测试带有知识缺口的归因."""
        # 创建模拟知识图谱
        concept = MagicMock()
        concept.id = "addition"
        concept.name = "加法运算"
        concept.mastery_level = 0.4  # 低掌握度
        
        kg = MagicMock()
        kg.concepts = [concept]
        kg.weak_points = []
        
        snapshot = MagicMock()
        snapshot.recent_episodes = []
        snapshot.knowledge_graph = kg
        snapshot.pending_gaps = []
        snapshot.profile = None
        
        mock_memory_manager.get_snapshot = AsyncMock(return_value=snapshot)
        
        result = await attribution_engine.analyze(
            student_id="stu_123",
            problem_id="prob_456",
            error_type=ErrorType.KNOWLEDGE_GAP,
            concept_ids=["addition"],
        )
        
        # 检查是否有知识缺口因子
        knowledge_factors = [f for f in result.factors if f.factor_type == "knowledge_gap"]
        assert len(knowledge_factors) > 0
        assert len(result.knowledge_gaps) > 0
    
    @pytest.mark.asyncio
    async def test_analyze_careless_pattern(
        self,
        attribution_engine,
        mock_memory_manager,
    ):
        """测试粗心模式分析."""
        result = await attribution_engine.analyze(
            student_id="stu_123",
            problem_id="prob_456",
            error_type=ErrorType.CARELESS_MISTAKE,
            concept_ids=["addition"],
            student_answer="12",
            correct_answer="13",
        )
        
        # 相似答案应该增加粗心可能性
        assert result.error_type == ErrorType.CARELESS_MISTAKE
    
    def test_determine_primary_cause(self, attribution_engine):
        """测试主要原因确定."""
        factors = [
            AttributionFactor(
                factor_type="knowledge_gap",
                description="知识缺口",
                weight=0.5,
            ),
            AttributionFactor(
                factor_type="careless",
                description="粗心",
                weight=0.3,
            ),
        ]
        
        primary, secondary = attribution_engine._determine_primary_cause(
            factors, ErrorType.CALCULATION_ERROR
        )
        
        assert primary == "知识缺口"
        assert "粗心" in secondary
    
    def test_calculate_attribution_confidence(self, attribution_engine):
        """测试归因置信度计算."""
        factors = [
            AttributionFactor(
                factor_type="knowledge_gap",
                description="知识缺口",
                weight=0.5,
            ),
            AttributionFactor(
                factor_type="careless",
                description="粗心",
                weight=0.3,
            ),
        ]
        
        snapshot = MagicMock()
        snapshot.recent_episodes = [MagicMock()] * 10  # 有历史数据
        
        confidence = attribution_engine._calculate_attribution_confidence(
            factors, ErrorType.CALCULATION_ERROR, snapshot
        )
        
        assert 0 <= confidence <= 1
        assert confidence >= 0.5  # 基础置信度
    
    def test_generate_recommendations(self, attribution_engine):
        """测试建议生成."""
        factors = [
            AttributionFactor(
                factor_type="knowledge_gap",
                description="知识缺口",
                weight=0.5,
                evidence=["分数运算掌握度低"],
            ),
        ]
        
        recommendations = attribution_engine._generate_recommendations(
            primary_cause="知识缺口",
            factors=factors,
            knowledge_gaps=["分数运算", "通分"],
            is_careless_pattern=False,
        )
        
        assert len(recommendations) > 0
        assert any("分数运算" in r for r in recommendations)
    
    def test_generate_recommendations_careless(self, attribution_engine):
        """测试粗心情况建议生成."""
        recommendations = attribution_engine._generate_recommendations(
            primary_cause="粗心导致的失误",
            factors=[],
            knowledge_gaps=[],
            is_careless_pattern=True,
        )
        
        assert len(recommendations) > 0
        assert any("粗心" in r or "仔细" in r for r in recommendations)
    
    def test_calculate_similarity(self, attribution_engine):
        """测试相似度计算."""
        similarity = attribution_engine._calculate_similarity("123", "124")
        assert 0 <= similarity <= 1
        assert similarity > 0  # 有共同字符
        
        similarity2 = attribution_engine._calculate_similarity("abc", "def")
        assert similarity2 == 0  # 无共同字符
    
    def test_check_careless_pattern(self, attribution_engine):
        """测试粗心模式检查."""
        factors = [
            AttributionFactor(
                factor_type="careless_habit",
                description="粗心习惯",
                weight=0.6,
            ),
        ]
        
        is_careless = attribution_engine._check_careless_pattern(factors)
        assert is_careless is True
        
        factors_low = [
            AttributionFactor(
                factor_type="careless_habit",
                description="粗心习惯",
                weight=0.3,
            ),
        ]
        
        is_careless_low = attribution_engine._check_careless_pattern(factors_low)
        assert is_careless_low is False
