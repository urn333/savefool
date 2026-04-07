"""分层诊断测试."""
import pytest
import pytest_asyncio
from src.domain.engines.layered_diagnosis import (
    LayeredDiagnosisEngine, LayerOption, LayerOptionType, DiagnosisPath
)
from src.domain.models.diagnosis import ErrorType


class TestLayerOption:
    """分层选项测试."""
    
    def test_option_creation(self):
        """测试选项创建."""
        option = LayerOption(
            option_id="opt_1",
            title="选项文本",
            type=LayerOptionType.CONCEPT,
            description="描述",
            icon="icon",
            confidence=0.8,
        )
        assert option.option_id == "opt_1"


class TestDiagnosisPath:
    """诊断路径测试."""
    
    def test_path_creation(self):
        """测试路径创建."""
        path = DiagnosisPath(
            path_id="path_1",
            student_id="stu_1",
            problem_id="p1",
        )
        assert path.student_id == "stu_1"


class TestLayeredDiagnosisEngine:
    """分层诊断引擎测试."""
    
    @pytest.fixture
    def engine(self):
        return LayeredDiagnosisEngine(None)
    
    def test_engine_creation(self, engine):
        """测试引擎创建."""
        assert engine is not None
