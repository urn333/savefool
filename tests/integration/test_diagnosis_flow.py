"""诊断流程集成测试."""
import pytest
import pytest_asyncio
from src.domain.engines.diagnosis_engine import DiagnosisEngine, DiagnosisConfig
from src.domain.engines.arbitration_engine import ArbitrationEngine, ArbitrationConfig
from src.domain.models.diagnosis import Problem, DiagnosisStatus, ErrorType
from src.domain.models.arbitration import ModelResult, ArbitrationResult


class TestEndToEndDiagnosisFlow:
    """端到端诊断流程测试."""
    
    @pytest.fixture
    def diagnosis_engine(self):
        return DiagnosisEngine(DiagnosisConfig())
    
    @pytest.fixture
    def arbitration_engine(self):
        return ArbitrationEngine(ArbitrationConfig())
    
    @pytest.fixture
    def sample_problem(self):
        return Problem(
            id="prob_001",
            content="解方程: 3x + 7 = 22",
            subject="math",
            difficulty=3,
            answer="5",
        )
    
    @pytest.fixture
    def model_results_consensus(self):
        return [
            ModelResult(model_id="model_a", is_correct=False,
                       error_type=ErrorType.CALCULATION_ERROR, confidence=0.88),
            ModelResult(model_id="model_b", is_correct=False,
                       error_type=ErrorType.CALCULATION_ERROR, confidence=0.92),
            ModelResult(model_id="model_c", is_correct=False,
                       error_type=ErrorType.CALCULATION_ERROR, confidence=0.85),
        ]
    
    @pytest.mark.asyncio
    async def test_full_diagnosis_pipeline(self, diagnosis_engine, arbitration_engine,
                                            sample_problem, model_results_consensus):
        """测试完整诊断流程."""
        arbitration_result = arbitration_engine.arbitrate(
            problem_id=sample_problem.id,
            model_results=model_results_consensus,
        )
        assert arbitration_result.is_consensus is True
        
        diagnosis_result = await diagnosis_engine.diagnose(
            task_id="e2e_task_001",
            problems=[sample_problem],
            student_answers={sample_problem.id: "3"},
            arbitration_result=arbitration_result,
        )
        assert diagnosis_result.status == DiagnosisStatus.COMPLETED


class TestArbitrationToDiagnosisFlow:
    """仲裁到诊断流程测试."""
    
    @pytest.fixture
    def arbitration_engine(self):
        return ArbitrationEngine(ArbitrationConfig())
    
    def test_consensus_scenario(self, arbitration_engine):
        """测试共识场景."""
        model_results = [
            ModelResult(model_id="m1", is_correct=False,
                       error_type=ErrorType.CONCEPT_MISUNDERSTANDING, confidence=0.9),
            ModelResult(model_id="m2", is_correct=False,
                       error_type=ErrorType.CONCEPT_MISUNDERSTANDING, confidence=0.88),
            ModelResult(model_id="m3", is_correct=False,
                       error_type=ErrorType.CONCEPT_MISUNDERSTANDING, confidence=0.85),
        ]
        result = arbitration_engine.arbitrate(problem_id="p1", model_results=model_results)
        assert result.is_consensus is True
    
    def test_divergence_scenario(self, arbitration_engine):
        """测试分歧场景."""
        model_results = [
            ModelResult(model_id="m1", is_correct=False,
                       error_type=ErrorType.CALCULATION_ERROR, confidence=0.8),
            ModelResult(model_id="m2", is_correct=True, confidence=0.75),
            ModelResult(model_id="m3", is_correct=False,
                       error_type=ErrorType.CONCEPT_MISUNDERSTANDING, confidence=0.7),
        ]
        result = arbitration_engine.arbitrate(problem_id="p1", model_results=model_results)
        assert result.is_consensus is False
        assert arbitration_engine.should_trigger_variant(result) is True


class TestMultiProblemDiagnosis:
    """多题诊断流程测试."""
    
    @pytest.fixture
    def diagnosis_engine(self):
        return DiagnosisEngine(DiagnosisConfig())
    
    @pytest.mark.asyncio
    async def test_multi_problem_diagnosis(self, diagnosis_engine):
        """测试多题诊断."""
        problems = [
            Problem(id=f"p{i}", content=f"题{i}", subject="math", difficulty=3, answer=str(i*10))
            for i in range(1, 4)
        ]
        arbitration = ArbitrationResult(
            problem_id="multi", is_correct=False,
            error_type=ErrorType.CALCULATION_ERROR, confidence=0.8
        )
        result = await diagnosis_engine.diagnose(
            task_id="multi_task",
            problems=problems,
            student_answers={"p1": "10", "p2": "25", "p3": "35"},  # p2,p3错误
            arbitration_result=arbitration,
        )
        assert result.total_count == 3
        assert result.wrong_count == 2
