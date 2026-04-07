"""结果融合算法单元测试."""

import pytest

from src.domain.engines.result_fusion import (
    ResultFusion,
    FusionConfig,
    FieldSource,
    FusedDiagnosis,
    FusionResult,
)
from src.domain.models.arbitration import ArbitrationResult, ModelResult
from src.domain.models.diagnosis import ErrorType, DiagnosisResult


@pytest.fixture
def fusion():
    """创建融合器."""
    return ResultFusion(FusionConfig())


@pytest.fixture
def arbitration_result():
    """创建仲裁结果."""
    return ArbitrationResult(
        problem_id="prob_001",
        is_correct=False,
        error_type=ErrorType.CALCULATION_ERROR,
        confidence=0.85,
        is_consensus=True,
        used_models=["model_a", "model_b", "model_c"],
    )


@pytest.fixture
def model_results():
    """创建模型结果列表."""
    return [
        ModelResult(
            model_id="model_a",
            is_correct=False,
            error_type=ErrorType.CALCULATION_ERROR,
            confidence=0.9,
            diagnosis={
                "analysis": "计算步骤有误",
                "knowledge_points": ["分数加法", "通分"],
            },
        ),
        ModelResult(
            model_id="model_b",
            is_correct=False,
            error_type=ErrorType.CALCULATION_ERROR,
            confidence=0.85,
            diagnosis={
                "error_analysis": "计算错误",
                "steps": [{"step": 1, "is_correct": False}],
                "knowledge_points": ["分数运算"],
            },
        ),
        ModelResult(
            model_id="model_c",
            is_correct=False,
            error_type=ErrorType.CONCEPT_MISUNDERSTANDING,
            confidence=0.8,
            diagnosis={
                "root_cause": "概念理解不清",
                "concept_gaps": ["分数比较"],
                "knowledge_points": ["分数概念"],
            },
        ),
    ]


class TestResultFusion:
    """ResultFusion测试."""
    
    def test_fuse_results_success(self, fusion, arbitration_result, model_results):
        """测试成功融合."""
        result = fusion.fuse_results(arbitration_result, model_results, "prob_001")
        
        assert isinstance(result, FusedDiagnosis)
        assert result.is_wrong == True
        assert result.error_type == ErrorType.CALCULATION_ERROR
        assert result.confidence == 0.85
        assert len(result.root_cause) > 0
        assert len(result.concept_gaps) > 0
    
    def test_fuse_results_empty(self, fusion, arbitration_result):
        """测试空结果融合."""
        result = fusion.fuse_results(arbitration_result, [], "prob_001")
        
        assert result.is_wrong == True
        assert result.confidence == 0.85
        assert len(result.concept_gaps) == 0
    
    def test_fuse_results_correct_answer(self, fusion):
        """测试正确答案融合."""
        arbitration_result = ArbitrationResult(
            problem_id="prob_002",
            is_correct=True,
            confidence=0.95,
            is_consensus=True,
            used_models=["model_a", "model_b", "model_c"],
        )
        model_results = [
            ModelResult(model_id="m1", is_correct=True, confidence=0.95),
            ModelResult(model_id="m2", is_correct=True, confidence=0.9),
        ]
        
        result = fusion.fuse_results(arbitration_result, model_results, "prob_002")
        
        assert result.is_wrong == False
        assert result.error_type is None
    
    def test_fuse_root_cause_priority(self, fusion):
        """测试根本原因优先级."""
        model_results = [
            ModelResult(
                model_id="model_c",  # 高优先级
                is_correct=False,
                confidence=0.6,  # 但置信度较低
                diagnosis={"root_cause": "概念原因"},
            ),
            ModelResult(
                model_id="model_a",  # 中优先级
                is_correct=False,
                confidence=0.9,  # 高置信度
                diagnosis={"analysis": "分析原因"},
            ),
        ]
        
        result = fusion.fuse_results(
            ArbitrationResult(problem_id="test", is_correct=False, confidence=0.8),
            model_results,
        )
        
        # 应该在满足置信度阈值的前提下优先选择高优先级模型
        assert len(result.root_cause) > 0
    
    def test_fuse_concept_gaps_deduplication(self, fusion):
        """测试概念缺口去重."""
        model_results = [
            ModelResult(
                model_id="m1",
                is_correct=False,
                confidence=0.9,
                diagnosis={"concept_gaps": ["分数加法", "通分"]},
            ),
            ModelResult(
                model_id="m2",
                is_correct=False,
                confidence=0.85,
                diagnosis={"concept_gaps": ["分数加法", "分数运算"]},  # 有重复
            ),
        ]
        
        result = fusion.fuse_results(
            ArbitrationResult(problem_id="test", is_correct=False, confidence=0.8),
            model_results,
        )
        
        # 去重后应该少于4个
        assert len(result.concept_gaps) <= 3
    
    def test_field_source_tracking(self, fusion, arbitration_result, model_results):
        """测试字段来源追踪."""
        fusion.config.enable_source_tracking = True
        
        result = fusion.fuse_results(arbitration_result, model_results, "prob_001")
        
        assert len(result.field_sources) > 0
        assert "root_cause" in result.field_sources or "error_type" in result.field_sources
    
    def test_fuse_method_returns_fusion_result(self, fusion, arbitration_result, model_results):
        """测试fuse方法返回FusionResult(向后兼容)."""
        result = fusion.fuse(arbitration_result, model_results, "prob_001")
        
        assert isinstance(result, FusionResult)
        assert result.problem_id == "prob_001"
        assert "is_wrong" in result.fused_fields
        assert "error_type" in result.fused_fields


class TestFieldCandidates:
    """字段候选值测试."""
    
    def test_extract_field_candidates(self, fusion):
        """测试字段候选提取."""
        model_results = [
            ModelResult(
                model_id="m1",
                is_correct=False,
                confidence=0.9,
                diagnosis={
                    "root_cause": "原因1",
                    "concept_gaps": ["缺口1"],
                    "steps": [1, 2, 3],
                    "knowledge_points": ["知识点1"],
                },
            ),
            ModelResult(
                model_id="m2",
                is_correct=False,
                confidence=0.85,
                diagnosis={
                    "analysis": "分析",  # 作为root_cause备选
                    "knowledge_points": ["知识点2"],
                },
            ),
        ]
        
        candidates = fusion._extract_field_candidates(model_results)
        
        assert len(candidates["root_cause"]) >= 2
        assert len(candidates["concept_gaps"]) >= 1
        assert len(candidates["knowledge_points"]) >= 2
    
    def test_extract_empty_diagnosis(self, fusion):
        """测试空诊断提取."""
        model_results = [
            ModelResult(model_id="m1", is_correct=True, confidence=0.9),
        ]
        
        candidates = fusion._extract_field_candidates(model_results)
        
        assert len(candidates["root_cause"]) == 0
        assert len(candidates["concept_gaps"]) == 0


class TestConflictDetection:
    """冲突检测测试."""
    
    def test_detect_root_cause_conflict(self, fusion):
        """测试根本原因冲突."""
        candidates = {
            "root_cause": [
                ("原因A", "m1", 0.9),
                ("原因B完全不同", "m2", 0.85),
            ],
        }
        model_results = [
            ModelResult(model_id="m1", is_correct=False, confidence=0.9),
            ModelResult(model_id="m2", is_correct=False, confidence=0.85),
        ]
        
        conflicts = fusion._detect_field_conflicts(candidates, model_results)
        
        assert "root_cause_divergence" in conflicts
    
    def test_detect_error_type_conflict(self, fusion):
        """测试错误类型冲突."""
        candidates = {}
        model_results = [
            ModelResult(model_id="m1", is_correct=False, error_type=ErrorType.CALCULATION_ERROR, confidence=0.9),
            ModelResult(model_id="m2", is_correct=False, error_type=ErrorType.LOGICAL_FLAW, confidence=0.85),
        ]
        
        conflicts = fusion._detect_field_conflicts(candidates, model_results)
        
        assert "error_type_conflict" in conflicts
    
    def test_detect_confidence_variance(self, fusion):
        """测试置信度差异."""
        candidates = {}
        model_results = [
            ModelResult(model_id="m1", is_correct=False, confidence=0.95),
            ModelResult(model_id="m2", is_correct=False, confidence=0.5),  # 差异 0.45 > 0.4
        ]
        
        conflicts = fusion._detect_field_conflicts(candidates, model_results)
        
        assert "high_confidence_variance" in conflicts
    
    def test_no_conflict(self, fusion):
        """测试无冲突."""
        candidates = {
            "root_cause": [("原因", "m1", 0.9)],
        }
        model_results = [
            ModelResult(model_id="m1", is_correct=False, error_type=ErrorType.CALCULATION_ERROR, confidence=0.9),
            ModelResult(model_id="m2", is_correct=False, error_type=ErrorType.CALCULATION_ERROR, confidence=0.85),
        ]
        
        conflicts = fusion._detect_field_conflicts(candidates, model_results)
        
        assert len(conflicts) == 0


class TestCreateDiagnosisResult:
    """创建诊断结果测试."""
    
    def test_create_diagnosis_result_wrong(self, fusion):
        """测试创建错题诊断结果."""
        arbitration_result = ArbitrationResult(
            problem_id="prob_001",
            is_correct=False,
            error_type=ErrorType.CALCULATION_ERROR,
            confidence=0.85,
        )
        fused = FusedDiagnosis(
            is_wrong=True,
            error_type=ErrorType.CALCULATION_ERROR,
            root_cause="计算错误",
            concept_gaps=["分数加法"],
            confidence=0.85,
        )
        
        result = fusion.create_diagnosis_result(
            task_id="task_001",
            arbitration_result=arbitration_result,
            fused_diagnosis=fused,
            problem_id="prob_001",
        )
        
        assert isinstance(result, DiagnosisResult)
        assert result.task_id == "task_001"
        assert result.has_wrong_problems == True
        assert result.wrong_count == 1
        assert len(result.knowledge_update["concept_gaps"]) == 1
    
    def test_create_diagnosis_result_correct(self, fusion):
        """测试创建正确诊断结果."""
        arbitration_result = ArbitrationResult(
            problem_id="prob_002",
            is_correct=True,
            confidence=0.95,
        )
        fused = FusedDiagnosis(
            is_wrong=False,
            confidence=0.95,
        )
        
        result = fusion.create_diagnosis_result(
            task_id="task_002",
            arbitration_result=arbitration_result,
            fused_diagnosis=fused,
        )
        
        assert result.has_wrong_problems == False
        assert result.wrong_count == 0


class TestFusionConfig:
    """融合配置测试."""
    
    def test_default_config(self):
        """测试默认配置."""
        config = FusionConfig()
        
        assert config.field_confidence_threshold == 0.6
        assert config.enable_source_tracking == True
        assert config.conflict_resolution_strategy == "weighted_vote"
        assert config.field_merge_strategy == "union"
        assert config.conflict_resolution == "majority"
        assert config.include_sources == True
        assert config.min_field_agreement == 0.5
    
    def test_custom_config(self):
        """测试自定义配置."""
        config = FusionConfig(
            field_confidence_threshold=0.7,
            enable_source_tracking=False,
            conflict_resolution_strategy="priority",
            field_merge_strategy="intersection",
            conflict_resolution="confidence",
            include_sources=False,
            min_field_agreement=0.7,
        )
        
        assert config.field_confidence_threshold == 0.7
        assert config.enable_source_tracking == False
        assert config.conflict_resolution_strategy == "priority"
        assert config.field_merge_strategy == "intersection"
        assert config.conflict_resolution == "confidence"
        assert config.include_sources == False
        assert config.min_field_agreement == 0.7


class TestFieldSource:
    """字段来源测试."""
    
    def test_field_source_creation(self):
        """测试创建字段来源."""
        source = FieldSource(
            field_name="root_cause",
            model_id="model_a",
            confidence=0.9,
            value="计算错误",
        )
        
        assert source.field_name == "root_cause"
        assert source.model_id == "model_a"
        assert source.confidence == 0.9
        assert source.value == "计算错误"


class TestFusedDiagnosis:
    """融合诊断测试."""
    
    def test_default_values(self):
        """测试默认值."""
        diagnosis = FusedDiagnosis()
        
        assert diagnosis.is_wrong == False
        assert diagnosis.error_type is None
        assert diagnosis.root_cause == ""
        assert diagnosis.concept_gaps == []
        assert diagnosis.confidence == 0.0
        assert diagnosis.field_sources == {}
        assert diagnosis.conflict_flags == []
    
    def test_custom_values(self):
        """测试自定义值."""
        diagnosis = FusedDiagnosis(
            is_wrong=True,
            error_type=ErrorType.CALCULATION_ERROR,
            root_cause="计算错误",
            concept_gaps=["分数加法"],
            confidence=0.85,
            conflict_flags=["high_confidence_variance"],
        )
        
        assert diagnosis.is_wrong == True
        assert diagnosis.error_type == ErrorType.CALCULATION_ERROR
        assert diagnosis.confidence == 0.85
        assert len(diagnosis.conflict_flags) == 1


class TestFusionResult:
    """FusionResult测试."""
    
    def test_default_values(self):
        """测试默认值."""
        result = FusionResult()
        
        assert result.problem_id == ""
        assert result.fused_fields == {}
        assert result.field_sources == {}
        assert result.conflicts == []
        assert result.fusion_confidence == 0.0
    
    def test_custom_values(self):
        """测试自定义值."""
        result = FusionResult(
            problem_id="prob_001",
            fused_fields={"is_wrong": True},
            fusion_confidence=0.9,
        )
        
        assert result.problem_id == "prob_001"
        assert result.fused_fields["is_wrong"] == True
        assert result.fusion_confidence == 0.9


class TestAdditionalMethods:
    """额外方法测试."""
    
    def test_fuse_concept_scores(self, fusion):
        """测试融合概念分数."""
        model_results = [
            ModelResult(
                model_id="m1",
                is_correct=False,
                confidence=0.9,
                concept_scores={"arithmetic": 0.8, "logic": 0.7},
            ),
            ModelResult(
                model_id="m2",
                is_correct=False,
                confidence=0.85,
                concept_scores={"arithmetic": 0.9, "logic": 0.6},
            ),
        ]
        
        scores = fusion.fuse_concept_scores(model_results)
        
        assert "arithmetic" in scores
        assert "logic" in scores
        # 平均值
        assert scores["arithmetic"] == pytest.approx(0.85, 0.01)
        assert scores["logic"] == pytest.approx(0.65, 0.01)
    
    def test_fuse_knowledge_points(self, fusion):
        """测试融合知识点."""
        model_results = [
            ModelResult(
                model_id="m1",
                is_correct=False,
                confidence=0.9,
                diagnosis={"knowledge_points": ["加法", "减法"]},
            ),
            ModelResult(
                model_id="m2",
                is_correct=False,
                confidence=0.85,
                diagnosis={"knowledge_points": ["加法", "乘法"]},
            ),
        ]
        
        points = fusion.fuse_knowledge_points(model_results)
        
        assert len(points) > 0
        # 加法被两个模型提到，频率应该是2
        addition = next((p for p in points if p["name"] == "加法"), None)
        if addition:
            assert addition["frequency"] == 2
