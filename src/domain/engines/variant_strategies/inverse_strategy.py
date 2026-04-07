"""逆运算变形策略.

将题目从正向求解变为逆向验证。
"""

import re
from typing import Optional

from .base import StrategyContext, StrategyResult, VariantStrategy
from src.domain.models.diagnosis import ErrorType, Problem


class InverseOperationStrategy(VariantStrategy):
    """逆运算变形策略.
    
    将题目从"已知条件求结果"变为"已知结果求条件"。
    """
    
    strategy_name = "逆运算变形"
    strategy_type = "inverse"
    difficulty_adjustment = 1.0
    
    def can_apply(self, problem: Problem, error_type: ErrorType) -> bool:
        """判断是否适用.
        
        需要是方程或可逆的题目。
        """
        content = problem.content.lower()
        
        # 检查是否包含方程关键词
        equation_keywords = [
            '方程', 'equation', 'x', 'y', '求解', '解',
            '求', 'find', 'solve'
        ]
        
        has_variable = any(v in content for v in ['x', 'y', 'z'])
        has_equation_marker = '=' in content
        has_keyword = any(kw in content for kw in equation_keywords)
        
        return has_variable or (has_equation_marker and has_keyword)
    
    async def generate(self, context: StrategyContext) -> StrategyResult:
        """生成逆运算变形题."""
        try:
            original = context.original_problem
            
            # 构建逆运算题目
            new_content = self._build_inverse_problem(
                original.content, original.answer
            )
            
            if not new_content:
                return StrategyResult(
                    success=False,
                    error_message="无法构建逆运算题目"
                )
            
            # 逆运算的答案通常是原题的条件
            new_answer = self._extract_condition(original.content)
            
            # 创建变形题
            variant = self._create_variant_problem(
                original=original,
                content=new_content,
                answer=new_answer,
                solution=None,
                difficulty=min(10, context.target_difficulty + 1),
                context=context,
            )
            
            return StrategyResult(
                success=True,
                variant=variant,
                metadata={
                    "transform_type": "inverse_operation",
                    "original_answer_used": True,
                }
            )
            
        except Exception as e:
            return StrategyResult(
                success=False,
                error_message=f"逆运算变形失败: {str(e)}"
            )
    
    def _build_inverse_problem(
        self, original_content: str, answer: Optional[str]
    ) -> Optional[str]:
        """构建逆运算题目."""
        if not answer:
            return None
        
        # 提取数值
        numbers = re.findall(r'\d+', original_content)
        
        # 构造逆运算题目
        inverse_content = f"验证: 当 {'x' if 'x' in original_content else '解'} = {answer} 时，{original_content} 是否成立？"
        
        return inverse_content
    
    def _extract_condition(self, content: str) -> Optional[str]:
        """提取原题条件作为答案."""
        # 简化处理：返回第一个数值
        numbers = re.findall(r'\d+', content)
        if numbers:
            return numbers[0]
        return None
