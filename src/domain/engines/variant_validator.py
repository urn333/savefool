"""变形题验证器.

验证生成的变形题的正确性、等价性、难度等。
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.domain.models.diagnosis import Problem
from src.domain.models.variant import VariantProblem


@dataclass
class ValidationResult:
    """验证结果.
    
    Attributes:
        is_valid: 是否通过验证
        errors: 错误信息列表
        warnings: 警告信息列表
        difficulty_delta: 难度变化
        equivalence_score: 等价性分数
        recommendation: 使用建议
    """
    
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    difficulty_delta: float = 0.0
    equivalence_score: float = 0.0
    recommendation: str = ""
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "difficulty_delta": self.difficulty_delta,
            "equivalence_score": self.equivalence_score,
            "recommendation": self.recommendation,
        }


class VariantValidator:
    """变形题验证器.
    
    提供全面的变形题验证功能：
    - 答案正确性验证
    - 等价性检查
    - 难度评估
    - 学生水平匹配检查
    """
    
    def __init__(self):
        """初始化验证器."""
        self._validation_rules = self._init_validation_rules()
    
    def _init_validation_rules(self) -> Dict[str, Any]:
        """初始化验证规则."""
        return {
            "min_content_length": 10,
            "max_content_length": 1000,
            "min_answer_length": 1,
            "max_difficulty_delta": 3.0,
            "min_equivalence_score": 0.5,
        }
    
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
        
        # 1. 基础内容验证
        content_errors = self._validate_content(variant)
        errors.extend(content_errors)
        
        # 2. 答案验证
        answer_result = self._validate_answer(variant, original)
        errors.extend(answer_result[0])
        warnings.extend(answer_result[1])
        
        # 3. 等价性检查
        equivalence_score = self._check_equivalence(variant, original)
        if equivalence_score < self._validation_rules["min_equivalence_score"]:
            warnings.append(f"与原题等价性较低({equivalence_score:.2f})")
        
        # 4. 难度评估
        difficulty_delta = variant.difficulty - original.difficulty
        if abs(difficulty_delta) > self._validation_rules["max_difficulty_delta"]:
            warnings.append(f"难度变化过大({difficulty_delta:+.1f})")
        
        # 5. 学生水平匹配
        level_errors = self._validate_student_level_match(
            variant, student_level
        )
        warnings.extend(level_errors)
        
        # 6. 生成推荐
        recommendation = self._generate_recommendation(
            errors, warnings, equivalence_score, difficulty_delta
        )
        
        # 判断是否有效
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            difficulty_delta=difficulty_delta,
            equivalence_score=equivalence_score,
            recommendation=recommendation,
        )
    
    def _validate_content(self, variant: VariantProblem) -> List[str]:
        """验证题目内容.
        
        Args:
            variant: 变形题
            
        Returns:
            错误列表
        """
        errors = []
        content = variant.content
        
        # 1. 长度检查
        if not content:
            errors.append("题目内容为空")
        elif len(content) < self._validation_rules["min_content_length"]:
            errors.append(f"题目内容过短({len(content)}字符)")
        elif len(content) > self._validation_rules["max_content_length"]:
            errors.append(f"题目内容过长({len(content)}字符)")
        
        # 2. 必要元素检查
        if content:
            # 检查是否有数字
            if not re.search(r'\d', content):
                errors.append("题目中缺少数字")
            
            # 检查问题标记
            if '?' not in content and '？' not in content:
                if not any(word in content for word in ["多少", "几", "求", "计算"]):
                    errors.append("题目缺少问题标记")
        
        return errors
    
    def _validate_answer(
        self,
        variant: VariantProblem,
        original: Problem,
    ) -> Tuple[List[str], List[str]]:
        """验证答案.
        
        Args:
            variant: 变形题
            original: 原题
            
        Returns:
            (错误列表, 警告列表)
        """
        errors = []
        warnings = []
        
        # 1. 检查答案存在性
        if not variant.answer:
            warnings.append("变形题缺少答案")
            return errors, warnings
        
        answer = str(variant.answer).strip()
        
        # 2. 检查答案格式
        if len(answer) < self._validation_rules["min_answer_length"]:
            errors.append("答案过短")
        
        # 3. 检查答案合理性
        # 提取题目中的数字
        content_nums = re.findall(r'\d+\.?\d*', variant.content)
        
        if content_nums:
            try:
                nums = [float(n) for n in content_nums]
                max_num = max(nums)
                min_num = min(nums)
                
                # 尝试解析答案
                try:
                    ans_val = float(answer)
                    
                    # 检查答案范围合理性
                    if ans_val < 0 and min_num >= 0:
                        # 原题数字都是正数，答案为负数需警告
                        warnings.append("答案为负数，但题目中数字均为正数")
                    
                    if ans_val > max_num * 100:
                        warnings.append(f"答案({ans_val})远大于题目中最大数字({max_num})")
                    
                except ValueError:
                    # 非数字答案，检查是否是分数或表达式
                    if '/' in answer or '+' in answer or '-' in answer:
                        pass  # 可能是分数或表达式
                    else:
                        warnings.append("答案格式不常见")
                        
            except (ValueError, TypeError):
                pass
        
        return errors, warnings
    
    def _check_equivalence(
        self,
        variant: VariantProblem,
        original: Problem,
    ) -> float:
        """检查与原题的等价性.
        
        Args:
            variant: 变形题
            original: 原题
            
        Returns:
            等价性分数(0-1)
        """
        score = 1.0
        
        # 1. 运算符一致性
        variant_ops = set(c for c in variant.content if c in "+-×÷*/")
        original_ops = set(c for c in original.content if c in "+-×÷*/")
        
        if variant_ops != original_ops:
            # 运算符不同，可能是逆运算
            score -= 0.2
        
        # 2. 数字数量一致性
        variant_nums = len(re.findall(r'\d+\.?\d*', variant.content))
        original_nums = len(re.findall(r'\d+\.?\d*', original.content))
        
        num_diff = abs(variant_nums - original_nums)
        if num_diff > 1:
            score -= 0.1 * num_diff
        
        # 3. 知识点一致性
        if variant.target_concept in original.knowledge_points:
            score += 0.1
        else:
            score -= 0.1
        
        # 4. 策略相关评分
        # 数值变形保持等价性较好
        if variant.strategy.value == "value_substitution":
            score += 0.1
        # 逆运算变形等价性略低
        elif variant.strategy.value == "reverse_construct":
            score -= 0.1
        
        return min(1.0, max(0.0, score))
    
    def _validate_student_level_match(
        self,
        variant: VariantProblem,
        student_level: float,
    ) -> List[str]:
        """验证与学生水平的匹配度.
        
        Args:
            variant: 变形题
            student_level: 学生水平
            
        Returns:
            警告列表
        """
        warnings = []
        
        # 将难度(1-10)映射到学生水平(0-1)
        difficulty_level = variant.difficulty / 10.0
        gap = abs(difficulty_level - student_level)
        
        if gap > 0.4:
            if difficulty_level > student_level:
                warnings.append(f"题目难度({variant.difficulty})明显高于学生水平")
            else:
                warnings.append(f"题目难度({variant.difficulty})明显低于学生水平")
        elif gap > 0.2:
            if difficulty_level > student_level:
                warnings.append(f"题目难度({variant.difficulty})略高于学生水平")
        
        return warnings
    
    def _generate_recommendation(
        self,
        errors: List[str],
        warnings: List[str],
        equivalence_score: float,
        difficulty_delta: float,
    ) -> str:
        """生成使用建议.
        
        Args:
            errors: 错误列表
            warnings: 警告列表
            equivalence_score: 等价性分数
            difficulty_delta: 难度变化
            
        Returns:
            建议文本
        """
        if errors:
            return "建议：验证未通过，需要修正错误后使用"
        
        if equivalence_score >= 0.9 and not warnings:
            return "建议：优秀变形，可直接使用"
        
        if equivalence_score >= 0.75:
            if difficulty_delta > 0:
                return "建议：良好变形，难度有所提升，适合挑战"
            else:
                return "建议：良好变形，可直接使用"
        
        if equivalence_score >= 0.6:
            return "建议：基本可用，建议检查后再使用"
        
        if warnings:
            return "建议：存在一些问题，建议谨慎使用"
        
        return "建议：可以试用"
    
    def quick_validate(self, variant: VariantProblem) -> bool:
        """快速验证.
        
        用于生成过程中的快速检查。
        
        Args:
            variant: 变形题
            
        Returns:
            是否通过快速验证
        """
        # 1. 内容非空
        if not variant.content or len(variant.content) < 10:
            return False
        
        # 2. 有数字
        if not re.search(r'\d', variant.content):
            return False
        
        # 3. 难度在合理范围
        if not 1 <= variant.difficulty <= 10:
            return False
        
        # 4. 有答案或解题过程
        if not variant.answer and not variant.solution:
            return False
        
        return True
    
    def validate_batch(
        self,
        variants: List[VariantProblem],
        original: Problem,
        student_level: float,
    ) -> List[ValidationResult]:
        """批量验证.
        
        Args:
            variants: 变形题列表
            original: 原题
            student_level: 学生水平
            
        Returns:
            验证结果列表
        """
        import asyncio
        
        async def validate_all():
            tasks = [
                self.validate(v, original, student_level)
                for v in variants
            ]
            return await asyncio.gather(*tasks)
        
        return asyncio.run(validate_all())
