"""分层诊断引擎测试."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from src.domain.engines.layered_diagnosis import (
    LayeredDiagnosisEngine,
    LayerOption,
    LayerOptionType,
    DiagnosisPath,
)
from src.domain.engines.error_attribution import ErrorAttributionResult, AttributionFactor
from src.domain.models.diagnosis import ErrorType
from src.domain.memory.memory_manager import MemoryManager


@pytest.fixture
def mock_memory_manager():
    """创建模拟记忆管理器."""
    return MagicMock(spec=MemoryManager)


@pytest.fixture
def layered_engine(mock_memory_manager):
    """创建分层诊断引擎."""
    return LayeredDiagnosisEngine(mock_memory_manager)


@pytest.fixture
def sample_attribution_result():
    """创建示例归因结果."""
    return ErrorAttributionResult(
        problem_id="prob_123",
        student_id="stu_456",
        primary_cause="知识缺口",
        secondary_causes=["方法不熟练"],
        error_type=ErrorType.KNOWLEDGE_GAP,
        confidence=0.8,
        knowledge_gaps=["分数加法"],
        is_careless_pattern=False,
        historical_similarity=0.2,
        factors=[],
        recommendations=["多做练习"],
    )


class TestLayeredDiagnosisEngine:
    """分层诊断引擎测试类."""
    
    @pytest.mark.asyncio
    async def test_generate_first_layer(self, layered_engine, sample_attribution_result):
        """测试第一层选项生成."""
        options = await layered_engine.generate_first_layer(sample_attribution_result)
        
        assert len(options) == 3
        
        # 检查选项类型
        option_types = [opt.type for opt in options]
        assert LayerOptionType.KNOWLEDGE in option_types
        
        # 检查选项属性
        for opt in options:
            assert opt.option_id is not None
            assert opt.title is not None
            assert opt.description is not None
            assert opt.icon is not None
            assert 0 <= opt.confidence <= 1
    
    @pytest.mark.asyncio
    async def test_generate_first_layer_with_historical_pattern(
        self,
        layered_engine,
        sample_attribution_result,
    ):
        """测试带有历史模式的第一层选项."""
        # 设置高历史相似度
        sample_attribution_result.historical_similarity = 0.8
        
        options = await layered_engine.generate_first_layer(sample_attribution_result)
        
        # 历史模式选项应该有较高置信度
        historical_options = [opt for opt in options if opt.type == LayerOptionType.HISTORICAL]
        if historical_options:
            assert historical_options[0].confidence > 0.5
    
    @pytest.mark.asyncio
    async def test_generate_second_layer_historical(
        self,
        layered_engine,
        sample_attribution_result,
    ):
        """测试历史类型的第二层选项."""
        first_options = await layered_engine.generate_first_layer(sample_attribution_result)
        historical_option = [opt for opt in first_options if opt.type == LayerOptionType.HISTORICAL][0]
        
        second_options = await layered_engine.generate_second_layer(
            student_id="stu_456",
            problem_id="prob_123",
            first_selection=historical_option.option_id,
            attribution_result=sample_attribution_result,
            first_layer_options=first_options,
        )
        
        assert 2 <= len(second_options) <= 3
        
        for opt in second_options:
            assert opt.option_id is not None
            assert opt.title is not None
    
    @pytest.mark.asyncio
    async def test_generate_second_layer_knowledge(
        self,
        layered_engine,
        sample_attribution_result,
    ):
        """测试知识类型的第二层选项."""
        first_options = await layered_engine.generate_first_layer(sample_attribution_result)
        knowledge_option = [opt for opt in first_options if opt.type == LayerOptionType.KNOWLEDGE][0]
        
        second_options = await layered_engine.generate_second_layer(
            student_id="stu_456",
            problem_id="prob_123",
            first_selection=knowledge_option.option_id,
            attribution_result=sample_attribution_result,
            first_layer_options=first_options,
        )
        
        assert 2 <= len(second_options) <= 3
        
        # 检查是否包含概念或方法类型
        option_types = [opt.type for opt in second_options]
        assert LayerOptionType.CONCEPT in option_types or LayerOptionType.METHOD in option_types
    
    def test_start_diagnosis_path(self, layered_engine):
        """测试开始诊断路径."""
        path = layered_engine.start_diagnosis_path(
            student_id="stu_123",
            problem_id="prob_456",
        )
        
        assert isinstance(path, DiagnosisPath)
        assert path.student_id == "stu_123"
        assert path.problem_id == "prob_456"
        assert path.path_id is not None
        assert len(path.selections) == 0
    
    def test_record_first_selection(self, layered_engine):
        """测试记录第一层选择."""
        path = layered_engine.start_diagnosis_path("stu_123", "prob_456")
        
        updated_path = layered_engine.record_first_selection(
            path_id=path.path_id,
            option_id="opt_1",
            option_type="knowledge",
        )
        
        assert updated_path is not None
        assert len(updated_path.selections) == 1
        assert updated_path.selections[0]["layer"] == 1
        assert updated_path.selections[0]["option_type"] == "knowledge"
    
    def test_record_second_selection(self, layered_engine):
        """测试记录第二层选择."""
        path = layered_engine.start_diagnosis_path("stu_123", "prob_456")
        layered_engine.record_first_selection(path.path_id, "opt_1", "knowledge")
        
        updated_path = layered_engine.record_second_selection(
            path_id=path.path_id,
            option_id="opt_2",
            option_type="concept",
            final_diagnosis="概念理解有误",
        )
        
        assert updated_path is not None
        assert len(updated_path.selections) == 2
        assert updated_path.selections[1]["layer"] == 2
        assert updated_path.final_diagnosis == "概念理解有误"
        assert updated_path.end_time is not None
    
    @pytest.mark.asyncio
    async def test_finalize_diagnosis(self, layered_engine, sample_attribution_result):
        """测试完成诊断."""
        path = layered_engine.start_diagnosis_path("stu_123", "prob_456")
        layered_engine.record_first_selection(path.path_id, "opt_1", "knowledge")
        layered_engine.record_second_selection(
            path.path_id, "opt_2", "concept", "概念理解有误"
        )
        
        result = await layered_engine.finalize_diagnosis(
            path_id=path.path_id,
            attribution_result=sample_attribution_result,
        )
        
        assert result is not None
        assert "path" in result
        assert "final_diagnosis" in result
        assert path.path_id not in layered_engine._active_paths  # 已从活跃路径移除
    
    def test_get_option_recommendations_historical(self, layered_engine):
        """测试历史类型选项的建议."""
        recommendations = layered_engine.get_option_recommendations(
            LayerOptionType.HISTORICAL,
            ["分数运算"],
        )
        
        assert len(recommendations) > 0
        assert any("错题" in r for r in recommendations)
    
    def test_get_option_recommendations_knowledge(self, layered_engine):
        """测试知识类型选项的建议."""
        recommendations = layered_engine.get_option_recommendations(
            LayerOptionType.KNOWLEDGE,
            ["分数加法", "通分"],
        )
        
        assert len(recommendations) > 0
        assert any("复习" in r or "分数加法" in r for r in recommendations)
    
    def test_get_option_recommendations_careless(self, layered_engine):
        """测试粗心类型选项的建议."""
        recommendations = layered_engine.get_option_recommendations(
            LayerOptionType.CARELESS,
            [],
        )
        
        assert len(recommendations) > 0
        assert any("仔细" in r or "检查" in r or "专注" in r for r in recommendations)
    
    def test_build_final_diagnosis(self, layered_engine):
        """测试构建最终诊断."""
        path = DiagnosisPath(
            path_id="path_123",
            student_id="stu_456",
            problem_id="prob_789",
            selections=[
                {"layer": 1, "option_id": "opt_1", "option_type": "knowledge"},
                {"layer": 2, "option_id": "opt_2", "option_type": "concept"},
            ],
        )
        
        attribution = MagicMock()
        attribution.primary_cause = "知识缺口"
        
        diagnosis = layered_engine._build_final_diagnosis(path, attribution)
        
        assert "概念" in diagnosis
    
    def test_extract_confirmed_factors(self, layered_engine):
        """测试提取确认的因素."""
        path = DiagnosisPath(
            path_id="path_123",
            student_id="stu_456",
            problem_id="prob_789",
            selections=[
                {"layer": 1, "option_id": "opt_1", "option_type": "historical"},
                {"layer": 2, "option_id": "opt_2", "option_type": "careless"},
            ],
        )
        
        attribution = MagicMock()
        
        factors = layered_engine._extract_confirmed_factors(path, attribution)
        
        assert "historical" in factors
        assert "careless" in factors
