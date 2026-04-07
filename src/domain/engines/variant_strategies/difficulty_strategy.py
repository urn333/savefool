"""难度调整变形策略.

通过增减条件、改变复杂度来调整题目难度。
"""

import re
from typing import List, Optional, Tuple

from .base import TransformationContext, TransformResult, TransformStatus, TransformationStrategy
from src.domain.models.variant import GenerationStrategy


class DifficultyAdjustmentStrategy(TransformationStrategy):
    """难度调整变形策略.
    
    通过以下方式调整难度：
    - 增加/减少已知条件
    - 增加中间步骤
    - 改变数值复杂度
    - 添加/移除提示
    
    Example:
        >>> strategy = DifficultyAdjustmentStrategy(difficulty_delta=-1)
        >>> # 降低难度
    """
    
    def __init__(self, difficulty_delta: int = 0):
        """初始化难度调整策略.
        
        Args:
            difficulty_delta: 难度调整值（负数降低，正数增加）
        """
        super().__init__(GenerationStrategy.CONDITION_MODIFY)
        self.difficulty_delta = difficulty_delta
    
    def can_handle(self, context: TransformationContext) -> bool:
        """判断是否能处理.
        
        所有题目都可以调整难度。
        
        Args:
            context: 变形上下文
            
        Returns:
            是否能处理
        """
        return True
    
    def transform(self, context: TransformationContext) -> TransformResult:
        """执行难度调整.
        
        Args:
            context: 变形上下文
            
        Returns:
            变形结果
        """
        try:
            problem = context.original_problem
            answer = context.original_answer
            current_difficulty = context.original_difficulty
            
            # 计算目标难度
            target_difficulty = max(1, min(10, current_difficulty + self.difficulty_delta))
            
            if self.difficulty_delta < 0:
                # 降低难度
                new_problem, new_answer, adjustments = self._decrease_difficulty(
                    problem, answer, current_difficulty, target_difficulty
                )
            elif self.difficulty_delta > 0:
                # 增加难度
                new_problem, new_answer, adjustments = self._increase_difficulty(
                    problem, answer, current_difficulty, target_difficulty
                )
            else:
                # 不调整
                return TransformResult(
                    success=False,
                    status=TransformStatus.FAILED,
                    error_message="No difficulty adjustment needed",
                )
            
            # 创建变形题
            variant = self._create_variant(
                context=context,
                content=new_problem,
                answer=new_answer,
                difficulty=target_difficulty,
                hint=self._generate_hint(adjustments),
            )
            
            return TransformResult(
                success=True,
                variant=variant,
                status=TransformStatus.SUCCESS,
                metadata={
                    "transform_type": "difficulty_adjustment",
                    "original_difficulty": current_difficulty,
                    "target_difficulty": target_difficulty,
                    "adjustments": adjustments,
                },
            )
            
        except Exception as e:
            return TransformResult(
                success=False,
                status=TransformStatus.FAILED,
                error_message=str(e),
            )
    
    def _decrease_difficulty(
        self,
        problem: str,
        answer: str,
        current: int,
        target: int,
    ) -> Tuple[str, str, List[str]]:
        """降低难度.
        
        Args:
            problem: 原题
            answer: 原答案
            current: 当前难度
            target: 目标难度
            
        Returns:
            (新题目, 新答案, 调整项列表)
        """
        adjustments = []
        new_problem = problem
        new_answer = answer
        
        # 1. 简化数值
        numbers = self._extract_numbers(problem)
        if len(numbers) > 0:
            # 尝试将大数变小
            new_problem = self._simplify_numbers(new_problem)
            adjustments.append("simplified_numbers")
        
        # 2. 添加提示
        if "提示" not in new_problem:
            new_problem = "【提示：分步计算】" + new_problem
            adjustments.append("added_hint")
        
        # 3. 减少步骤（通过简化表述）
        if len(problem) > 50:
            new_problem = self._simplify_problem(new_problem)
            adjustments.append("simplified_problem")
        
        return new_problem, new_answer, adjustments
    
    def _increase_difficulty(
        self,
        problem: str,
        answer: str,
        current: int,
        target: int,
    ) -> Tuple[str, str, List[str]]:
        """增加难度.
        
        Args:
            problem: 原题
            answer: 原答案
            current: 当前难度
            target: 目标难度
            
        Returns:
            (新题目, 新答案, 调整项列表)
        """
        adjustments = []
        new_problem = problem
        new_answer = answer
        
        # 1. 增加复杂度（合并题目）
        if current < 5:
            new_problem = self._add_complexity(new_problem)
            adjustments.append("added_complexity")
        
        # 2. 隐藏条件
        if "已知" in new_problem:
            new_problem = new_problem.replace("已知", "隐含条件：")
            adjustments.append("hidden_condition")
        
        # 3. 要求逆运算
        if "求" in new_problem:
            new_problem = new_problem.replace("求", "反推")
            adjustments.append("reverse_operation")
        
        return new_problem, new_answer, adjustments
    
    def _extract_numbers(self, text: str) -> List[str]:
        """提取文本中的数字.
        
        Args:
            text: 输入文本
            
        Returns:
            数字列表
        """
        pattern = re.compile(r'-?\d+')
        return pattern.findall(text)
    
    def _simplify_numbers(self, problem: str) -> str:
        """简化数值.
        
        将较大的数值变小。
        
        Args:
            problem: 原题
            
        Returns:
            简化后的题目
        """
        # 简单的数值映射
        replacements = {
            "100": "20",
            "50": "10",
            "25": "5",
            "12": "6",
        }
        
        result = problem
        for old, new in replacements.items():
            result = result.replace(old, new)
        
        return result
    
    def _simplify_problem(self, problem: str) -> str:
        """简化题目表述.
        
        Args:
            problem: 原题
            
        Returns:
            简化后的题目
        """
        # 移除复杂的修饰词
        simplified = problem
        complex_words = ["复杂的", "困难的", "抽象的"]
        for word in complex_words:
            simplified = simplified.replace(word, "")
        
        return simplified
    
    def _add_complexity(self, problem: str) -> str:
        """增加复杂度.
        
        Args:
            problem: 原题
            
        Returns:
            增加复杂度后的题目
        """
        # 添加额外条件
        return problem + "（同时考虑边界条件）"
    
    def _generate_hint(self, adjustments: List[str]) -> Optional[str]:
        """生成提示信息.
        
        Args:
            adjustments: 调整项列表
            
        Returns:
            提示信息
        """
        if not adjustments:
            return None
        
        hints = {
            "simplified_numbers": "数值已简化",
            "added_hint": "请关注提示信息",
            "simplified_problem": "题目已简化",
            "added_complexity": "题目复杂度增加",
            "hidden_condition": "注意隐含条件",
            "reverse_operation": "需要逆运算",
        }
        
        hint_parts = [hints.get(a, a) for a in adjustments]
        return "；".join(hint_parts)
