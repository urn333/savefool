"""数值变形策略.

通过改变题目中的数值生成变形题。
"""

import random
import re
from typing import List, Optional, Tuple

from .base import StrategyContext, StrategyResult, VariantStrategy
from src.domain.models.diagnosis import ErrorType, Problem


class NumericVariationStrategy(VariantStrategy):
    """数值变形策略.
    
    通过改变题目中的数值生成变形题，保持题目结构不变。
    """
    
    strategy_name = "数值变形"
    strategy_type = "numeric"
    difficulty_adjustment = 0.0
    
    def can_apply(self, problem: Problem, error_type: ErrorType) -> bool:
        """判断是否适用.
        
        题目中需要包含数值。
        """
        numbers = self._extract_numbers(problem.content)
        return len(numbers) > 0
    
    async def generate(self, context: StrategyContext) -> StrategyResult:
        """生成数值变形题."""
        try:
            original = context.original_problem
            content = original.content
            
            # 提取所有数值
            numbers = self._extract_numbers(content)
            if not numbers:
                return StrategyResult(
                    success=False,
                    error_message="题目中没有可替换的数值"
                )
            
            # 选择要替换的数值
            target = self._select_number_to_replace(numbers, original.answer)
            if not target:
                return StrategyResult(
                    success=False,
                    error_message="无法选择合适的数值进行替换"
                )
            
            # 生成新数值
            new_value = self._generate_new_number(
                target, context.target_difficulty
            )
            
            # 替换内容
            new_content = self._replace_number(content, target, new_value)
            
            # 计算新答案（简化处理）
            new_answer = self._calculate_answer(original.answer, target, new_value)
            
            # 创建变形题
            solution_text = "\n".join(original.solution_steps) if original.solution_steps else None
            variant = self._create_variant_problem(
                original=original,
                content=new_content,
                answer=new_answer,
                solution=solution_text,
                difficulty=context.target_difficulty,
                context=context,
            )
            
            return StrategyResult(
                success=True,
                variant=variant,
                metadata={
                    "original_value": target,
                    "new_value": new_value,
                    "replacement_count": 1,
                }
            )
            
        except Exception as e:
            return StrategyResult(
                success=False,
                error_message=f"数值变形失败: {str(e)}"
            )
    
    def _extract_numbers(self, text: str) -> List[str]:
        """提取文本中的数值."""
        # 匹配整数和小数
        pattern = r'\d+\.?\d*'
        matches = re.findall(pattern, text)
        return [m for m in matches if m]
    
    def _select_number_to_replace(
        self, numbers: List[str], answer: Optional[str]
    ) -> Optional[str]:
        """选择要替换的数值."""
        if not numbers:
            return None
        
        # 优先选择不等于答案的数值
        for num in numbers:
            if num != answer:
                return num
        
        # 如果没有，返回第一个
        return numbers[0]
    
    def _generate_new_number(self, original: str, difficulty: int) -> str:
        """生成新数值."""
        try:
            if '.' in original:
                # 小数
                orig_val = float(original)
                # 根据难度调整
                factor = 1 + (difficulty - 5) * 0.1
                new_val = round(orig_val * factor, 1)
                return str(new_val)
            else:
                # 整数
                orig_val = int(original)
                # 根据难度调整范围
                if difficulty <= 3:
                    new_val = random.randint(1, 20)
                elif difficulty <= 7:
                    new_val = random.randint(10, 100)
                else:
                    new_val = random.randint(50, 500)
                return str(new_val)
        except ValueError:
            return original
    
    def _replace_number(self, content: str, old: str, new: str) -> str:
        """替换内容中的数值."""
        # 只替换第一次出现
        return content.replace(old, new, 1)
    
    def _calculate_answer(
        self, original_answer: Optional[str], old_value: str, new_value: str
    ) -> Optional[str]:
        """计算新答案."""
        # 简化处理：返回原答案
        # 实际应该根据具体题目重新计算
        return original_answer
