"""
数据库枚举类型测试

测试src.infrastructure.db.enums模块
"""

import pytest
from src.infrastructure.db.enums import (
    ErrorType,
    VariantType,
    GapStatus,
    ValidationStatus,
    HomeworkStatus,
    EvidenceType,
    SourceType,
)


class TestErrorTypeEnum:
    """测试错因类型枚举"""
    
    def test_error_type_values(self):
        """
        测试所有错因类型值
        
        Given: ErrorType枚举定义
        When: 访问各枚举值
        Then: 值应与设计文档一致
        """
        assert ErrorType.CARELESS == "careless"
        assert ErrorType.METHOD_ERROR == "method_error"
        assert ErrorType.CONCEPT_GAP == "concept_gap"
        assert ErrorType.CALCULATION_ERROR == "calculation_error"
        assert ErrorType.READING_ERROR == "reading_error"
        assert ErrorType.UNKNOWN == "unknown"
    
    def test_error_type_is_str_enum(self):
        """
        测试ErrorType是字符串枚举
        
        Given: ErrorType枚举
        When: 检查类型
        Then: 应是str的子类
        """
        assert isinstance(ErrorType.CARELESS, str)
        assert ErrorType.CARELESS.value == "careless"


class TestVariantTypeEnum:
    """测试变形类型枚举"""
    
    def test_variant_type_values(self):
        """
        测试所有变形类型值
        
        Given: VariantType枚举定义
        When: 访问各枚举值
        Then: 值应与设计文档一致
        """
        assert VariantType.NUMERIC_CHANGE == "numeric_change"
        assert VariantType.INVERSE_OPERATION == "inverse_operation"
        assert VariantType.CONTEXT_TRANSFER == "context_transfer"
        assert VariantType.DIFFICULTY_ADJUST == "difficulty_adjust"
        assert VariantType.FORMAT_CHANGE == "format_change"


class TestGapStatusEnum:
    """测试认知缺口状态枚举"""
    
    def test_gap_status_values(self):
        """
        测试所有缺口状态值
        
        Given: GapStatus枚举定义
        When: 访问各枚举值
        Then: 值应与设计文档一致
        """
        assert GapStatus.PENDING == "pending"
        assert GapStatus.CRYSTALLIZED == "crystallized"
        assert GapStatus.DISMISSED == "dismissed"


class TestValidationStatusEnum:
    """测试验证状态枚举"""
    
    def test_validation_status_values(self):
        """
        测试所有验证状态值
        
        Given: ValidationStatus枚举定义
        When: 访问各枚举值
        Then: 值应与设计文档一致
        """
        assert ValidationStatus.PENDING == "pending"
        assert ValidationStatus.VALIDATED == "validated"
        assert ValidationStatus.FAILED == "failed"
        assert ValidationStatus.EXPIRED == "expired"


class TestHomeworkStatusEnum:
    """测试作业状态枚举"""
    
    def test_homework_status_values(self):
        """
        测试所有作业状态值
        
        Given: HomeworkStatus枚举定义
        When: 访问各枚举值
        Then: 值应与设计文档一致
        """
        assert HomeworkStatus.ACTIVE == "active"
        assert HomeworkStatus.ARCHIVED == "archived"
        assert HomeworkStatus.DELETED == "deleted"


class TestEvidenceTypeEnum:
    """测试证据类型枚举"""
    
    def test_evidence_type_values(self):
        """
        测试所有证据类型值
        
        Given: EvidenceType枚举定义
        When: 访问各枚举值
        Then: 值应与设计文档一致
        """
        assert EvidenceType.INITIAL_DIAGNOSIS == "initial_diagnosis"
        assert EvidenceType.REPEAT_ERROR == "repeat_error"
        assert EvidenceType.VARIANT_FAILED == "variant_failed"
        assert EvidenceType.CROSS_HOMEWORK == "cross_homework"


class TestSourceTypeEnum:
    """测试来源类型枚举"""
    
    def test_source_type_values(self):
        """
        测试所有来源类型值
        
        Given: SourceType枚举定义
        When: 访问各枚举值
        Then: 值应与设计文档一致
        """
        assert SourceType.TEXT == "text"
        assert SourceType.VOICE == "voice"
        assert SourceType.VIDEO == "video"


class TestEnumUsages:
    """测试枚举使用场景"""
    
    def test_enum_in_dict(self):
        """
        测试枚举可用作字典值
        
        Given: ErrorType枚举值
        When: 用作字典值
        Then: 应正确存储和比较
        """
        data = {"error_type": ErrorType.CARELESS}
        assert data["error_type"] == "careless"
        assert data["error_type"] == ErrorType.CARELESS
    
    def test_enum_comparison(self):
        """
        测试枚举比较
        
        Given: 枚举值
        When: 与字符串比较
        Then: 应正确比较
        """
        assert ErrorType.CARELESS == "careless"
        assert ErrorType.CARELESS != "method_error"
        assert GapStatus.PENDING == "pending"
        assert GapStatus.CRYSTALLIZED != "pending"
    
    def test_enum_list_membership(self):
        """
        测试枚举列表成员检查
        
        Given: 枚举值列表
        When: 检查成员
        Then: 应正确识别
        """
        valid_error_types = [ErrorType.CARELESS, ErrorType.METHOD_ERROR, ErrorType.CONCEPT_GAP]
        assert ErrorType.CARELESS in valid_error_types
        assert ErrorType.UNKNOWN not in valid_error_types[:2]
