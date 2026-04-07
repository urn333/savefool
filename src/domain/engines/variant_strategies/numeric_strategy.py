"""数值变形策略.

通过替换题目中的数字来生成变形题，保持解题逻辑不变。
支持整数、分数、小数之间的转换。
"""

import random
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from src.domain.engines.variant_strategies.base import (
    StrategyContext,
    StrategyResult,
    VariantStrategy,
)
from src.domain.models.diagnosis import ErrorType, Problem
from src.domain.models.variant import VariantProblem


class NumericVariationStrategy(VariantStrategy):
    """数值变形策略.
    
    功能特点：
    - 识别题目中的数字
    - 根据难度生成新数字
    - 支持整数↔分数↔小数转换
    - 保持解题逻辑不变
    - 确保答案可计算
    
    适用场景：
    - 计算错误(ErrorType.CALCULATION_ERROR)
    - 粗心错误(ErrorType.CARELESS_MISTAKE)
    - 需要强化计算的练习
    """
    
    strategy_name = "数值变形"
    strategy_type = "numeric"
    difficulty_adjustment = 0.0
    
    # 数字类型权重(根据难度)
    TYPE_WEIGHTS = {
        1: {"int": 0.9, "float": 0.1, "fraction": 0.0},
        2: {"int": 0.8, "float": 0.2, "fraction": 0.0},
        3: {"int": 0.7, "float": 0.25, "fraction": 0.05},
        4: {"int": 0.6, "float": 0.3, "fraction": 0.1},
        5: {"int": 0.5, "float": 0.35, "fraction": 0.15},
        6: {"int": 0.4, "float": 0.4, "fraction": 0.2},
        7: {"int": 0.3, "float": 0.45, "fraction": 0.25},
        8: {"int": 0.2, "float": 0.5, "fraction": 0.3},
        9: {"int": 0.15, "float": 0.5, "fraction": 0.35},
        10: {"int": 0.1, "float": 0.5, "fraction": 0.4},
    }
    
    def can_apply(
        self,
        problem: Problem,
        error_type: ErrorType,
    ) -> bool:
        """判断策略是否适用.
        
        适用条件：
        - 题目中包含数字
        - 错误类型为计算错误或粗心错误
        
        Args:
            problem: 原题
            error_type: 错误类型
            
        Returns:
            是否适用
        """
        # 检查是否有数字
        numbers = self._extract_numbers(problem.content)
        if not numbers:
            return False
        
        # 检查错误类型
        applicable_errors = {
            ErrorType.CALCULATION_ERROR,
            ErrorType.CARELESS_MISTAKE,
            ErrorType.CONCEPT_MISUNDERSTANDING,
            ErrorType.KNOWLEDGE_GAP,
        }
        
        return error_type in applicable_errors
    
    async def generate(
        self,
        context: StrategyContext,
    ) -> StrategyResult:
        """生成数值变形题.
        
        Args:
            context: 策略执行上下文
            
        Returns:
            生成结果
        """
        try:
            original = context.original_problem
            
            # 1. 提取原题中的数字
            numbers = self._extract_numbers(original.content)
            if not numbers:
                return StrategyResult(
                    success=False,
                    error_message="题目中没有找到可替换的数字",
                )
            
            # 2. 计算目标难度
            target_difficulty = self._calculate_target_difficulty(
                original.difficulty,
                context.student_level,
                context.error_type,
            )
            
            # 3. 生成新数字
            new_content, num_mapping = self._replace_numbers(
                original.content,
                numbers,
                target_difficulty,
            )
            
            # 4. 计算新答案(如果有原答案)
            new_answer = None
            new_solution = None
            if original.answer:
                new_answer = self._recalculate_answer(
                    original.answer,
                    num_mapping,
                )
            if original.solution_steps:
                new_solution = self._update_solution_steps(
                    original.solution_steps,
                    num_mapping,
                )
            
            # 5. 验证结果
            validation_errors = self._validate_result(
                new_content, new_answer, original
            )
            if validation_errors:
                return StrategyResult(
                    success=False,
                    error_message=f"验证失败: {'; '.join(validation_errors)}",
                )
            
            # 6. 创建变形题对象
            variant = self._create_variant_problem(
                original=original,
                content=new_content,
                answer=new_answer,
                solution=new_solution,
                difficulty=target_difficulty,
                context=context,
            )
            
            # 记录元数据
            self._generation_metadata = {
                "original_numbers": [n[0] for n in numbers],
                "number_mapping": {str(k): str(v) for k, v in num_mapping.items()},
                "target_difficulty": target_difficulty,
            }
            
            return StrategyResult(
                success=True,
                variant=variant,
                metadata=self._generation_metadata,
            )
            
        except Exception as e:
            return StrategyResult(
                success=False,
                error_message=f"生成失败: {str(e)}",
            )
    
    def _replace_numbers(
        self,
        content: str,
        numbers: List[tuple],
        difficulty: int,
    ) -> Tuple[str, Dict[Union[int, float], Union[int, float, str]]]:
        """替换题目中的数字.
        
        Args:
            content: 原题内容
            numbers: 提取的数字列表
            difficulty: 目标难度
            
        Returns:
            (新内容, 数字映射关系)
        """
        new_content = content
        mapping: Dict[Union[int, float], Union[int, float, str]] = {}
        
        # 从后往前替换，避免位置变化影响
        for num_str, original_value, num_type, start, end in reversed(numbers):
            new_value = self._generate_number(
                original_value,
                num_type,
                difficulty,
            )
            mapping[original_value] = new_value
            
            # 替换
            new_content = new_content[:start] + str(new_value) + new_content[end:]
        
        return new_content, mapping
    
    def _generate_number(
        self,
        original_value: Union[int, float],
        original_type: str,
        difficulty: int,
    ) -> Union[int, float, str]:
        """生成新数字.
        
        Args:
            original_value: 原数值
            original_type: 原数字类型
            difficulty: 目标难度
            
        Returns:
            新数字
        """
        # 根据难度选择新类型
        weights = self.TYPE_WEIGHTS.get(difficulty, self.TYPE_WEIGHTS[5])
        new_type = random.choices(
            list(weights.keys()),
            weights=list(weights.values()),
        )[0]
        
        # 根据原数值范围生成新数值
        if isinstance(original_value, (int, float)) and original_value != 0:
            magnitude = abs(original_value)
            sign = 1 if original_value > 0 else -1
        else:
            magnitude = 10
            sign = 1
        
        if new_type == "int":
            # 生成整数
            if magnitude <= 10:
                new_val = random.randint(1, 10)
            elif magnitude <= 100:
                new_val = random.randint(1, 100)
            else:
                new_val = random.randint(1, 1000)
            return sign * new_val
        
        elif new_type == "float":
            # 生成小数
            if difficulty <= 5:
                new_val = round(random.uniform(0.1, magnitude * 1.5), 1)
            else:
                new_val = round(random.uniform(0.01, magnitude * 2), 2)
            return sign * new_val
        
        elif new_type == "fraction":
            # 生成分数
            denom = random.randint(2, 10 if difficulty <= 7 else 20)
            numer = random.randint(1, int(magnitude) if magnitude > 1 else denom - 1)
            if sign < 0:
                return f"-{numer}/{denom}"
            return f"{numer}/{denom}"
        
        return original_value
    
    def _recalculate_answer(
        self,
        original_answer: str,
        num_mapping: Dict[Union[int, float], Union[int, float, str]],
    ) -> Optional[str]:
        """重新计算答案.
        
        简单替换数字，复杂表达式需要模型辅助。
        
        Args:
            original_answer: 原答案
            num_mapping: 数字映射
            
        Returns:
            新答案
        """
        new_answer = original_answer
        
        # 尝试替换答案中的数字
        for old_val, new_val in num_mapping.items():
            old_str = str(old_val)
            if old_str in new_answer:
                new_answer = new_answer.replace(old_str, str(new_val))
        
        return new_answer
    
    def _update_solution_steps(
        self,
        solution_steps: List[str],
        num_mapping: Dict[Union[int, float], Union[int, float, str]],
    ) -> str:
        """更新解题步骤.
        
        Args:
            solution_steps: 原解题步骤
            num_mapping: 数字映射
            
        Returns:
            新解题过程
        """
        updated_steps = []
        
        for step in solution_steps:
            new_step = step
            for old_val, new_val in num_mapping.items():
                old_str = str(old_val)
                if old_str in new_step:
                    new_step = new_step.replace(old_str, str(new_val))
            updated_steps.append(new_step)
        
        return "\n".join(updated_steps)
    
    def _validate_result(
        self,
        content: str,
        answer: Optional[str],
        original: Problem,
    ) -> List[str]:
        """验证生成结果.
        
        Args:
            content: 新题目内容
            answer: 新答案
            original: 原题
            
        Returns:
            验证错误列表
        """
        errors = []
        
        # 1. 检查内容非空
        if not content or len(content.strip()) < 5:
            errors.append("题目内容过短")
        
        # 2. 检查是否有数字
        new_numbers = self._extract_numbers(content)
        if not new_numbers:
            errors.append("变形后题目没有数字")
        
        # 3. 检查内容变化
        if content == original.content:
            errors.append("题目内容未发生变化")
        
        # 4. 检查答案合理性(简单检查)
        if answer:
            # 检查答案中是否有数字
            answer_numbers = self._extract_numbers(answer)
            if not answer_numbers and any(c.isdigit() for c in original.answer or ""):
                errors.append("答案中缺少数字")
        
        return errors
    
    def get_confidence_score(
        self,
        context: StrategyContext,
    ) -> float:
        """获取策略适用置信度.
        
        数值变形策略对计算错误的置信度较高。
        
        Args:
            context: 策略执行上下文
            
        Returns:
            置信度分数
        """
        if not self.can_apply(context.original_problem, context.error_type):
            return 0.0
        
        # 基础置信度
        base_confidence = 0.8
        
        # 错误类型加成
        if context.error_type == ErrorType.CALCULATION_ERROR:
            base_confidence = 0.95
        elif context.error_type == ErrorType.CARELESS_MISTAKE:
            base_confidence = 0.9
        
        # 数字数量加成(数字越多越适合数值变形)
        numbers = self._extract_numbers(context.original_problem.content)
        if len(numbers) >= 3:
            base_confidence += 0.05
        
        return min(1.0, base_confidence)
