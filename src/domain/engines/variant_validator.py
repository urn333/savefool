"""变形题验证器.

验证变形题的质量和正确性。
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.domain.models.variant import VariantProblem
from src.domain.models.diagnosis import Problem


@dataclass
class ValidationResult:
    """验证结果.
    
    Attributes:
        is_valid: 是否通过验证
        errors: 错误信息列表
        warnings: 警告信息列表
        metadata: 验证元数据
    """
    
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


class VariantValidator:
    """变形题验证器.
    
    验证变形题的多个维度：
    - 答案正确性
    - 等价性检查
    - 难度评估
    - 学生水平匹配
    """
    
    def __init__(self, min_content_length: int = 5, max_content_length: int = 1000):
        """初始化验证器.
        
        Args:
            min_content_length: 最小内容长度
            max_content_length: 最大内容长度
        """
        self.min_content_length = min_content_length
        self.max_content_length = max_content_length
    
    async def validate(
        self,
        variant: VariantProblem,
        original: Problem,
        student_level: float,
    ) -> ValidationResult:
        """验证变形题.
        
        Args:
            variant: 变形题
            original: 原题
            student_level: 学生水平
            
        Returns:
            验证结果
        """
        errors = []
        warnings = []
        metadata = {}
        
        # 1. 基本内容验证
        content_valid, content_errors = self._validate_content(variant)
        errors.extend(content_errors)
        
        # 2. 答案验证
        answer_valid, answer_errors = self._validate_answer(variant)
        errors.extend(answer_errors)
        
        # 3. 等价性检查
        equivalent, equiv_warnings = self._check_equivalence(variant, original)
        warnings.extend(equiv_warnings)
        metadata["equivalent"] = equivalent
        
        # 4. 难度检查
        difficulty_ok, difficulty_warnings = self._check_difficulty(variant, student_level)
        warnings.extend(difficulty_warnings)
        metadata["difficulty_ok"] = difficulty_ok
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            metadata=metadata,
        )
    
    def quick_validate(self, variant: VariantProblem) -> bool:
        """快速验证.
        
        仅做基本检查，用于快速筛选。
        
        Args:
            variant: 变形题
            
        Returns:
            是否通过快速验证
        """
        # 检查内容
        if not variant.content or len(variant.content) < self.min_content_length:
            return False
        
        # 检查答案
        if not variant.answer:
            return False
        
        return True
    
    def _validate_content(self, variant: VariantProblem) -> tuple[bool, List[str]]:
        """验证内容."""
        errors = []
        
        if not variant.content:
            errors.append("内容为空")
        elif len(variant.content) < self.min_content_length:
            errors.append(f"内容过短（少于{self.min_content_length}字符）")
        elif len(variant.content) > self.max_content_length:
            errors.append(f"内容过长（超过{self.max_content_length}字符）")
        
        return len(errors) == 0, errors
    
    def _validate_answer(self, variant: VariantProblem) -> tuple[bool, List[str]]:
        """验证答案."""
        errors = []
        
        if not variant.answer:
            errors.append("答案为空")
        elif len(str(variant.answer)) > 500:
            errors.append("答案过长")
        
        return len(errors) == 0, errors
    
    def _check_equivalence(
        self, variant: VariantProblem, original: Problem
    ) -> tuple[bool, List[str]]:
        """检查等价性."""
        warnings = []
        
        # 提取数值
        variant_nums = re.findall(r'\d+', variant.content)
        original_nums = re.findall(r'\d+', original.content)
        
        # 数值数量应该相近
        if abs(len(variant_nums) - len(original_nums)) > 1:
            warnings.append("数值数量变化较大")
        
        # 运算符应该相同
        variant_ops = set(c for c in variant.content if c in '+-×÷*/=')
        original_ops = set(c for c in original.content if c in '+-×÷*/=')
        
        if variant_ops != original_ops:
            warnings.append("运算符发生变化")
        
        is_equivalent = len(warnings) <= 1
        return is_equivalent, warnings
    
    def _check_difficulty(
        self, variant: VariantProblem, student_level: float
    ) -> tuple[bool, List[str]]:
        """检查难度."""
        warnings = []
        
        # 难度范围检查
        if not 1 <= variant.difficulty <= 10:
            warnings.append(f"难度超出范围(1-10): {variant.difficulty}")
        
        # 与学生水平匹配检查
        expected_difficulty = int(student_level * 10)
        diff = abs(variant.difficulty - expected_difficulty)
        
        if diff > 3:
            warnings.append(f"难度与学生水平差异较大")
        
        return len(warnings) == 0, warnings
