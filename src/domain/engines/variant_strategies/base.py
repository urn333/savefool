"""变形题生成策略基类.

定义策略模式接口，所有具体策略需继承此基类。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.domain.models.diagnosis import ErrorType, Problem
from src.domain.models.variant import VariantProblem


@dataclass
class StrategyContext:
    """策略执行上下文.
    
    包含生成变形题所需的所有上下文信息。
    
    Attributes:
        original_problem: 原题
        error_type: 错误类型
        student_level: 学生能力水平(0-1)
        target_difficulty: 目标难度(1-10)
        student_id: 学生ID
        history_context: 历史答题上下文
    """
    
    original_problem: Problem
    error_type: ErrorType
    student_level: float
    target_difficulty: int
    student_id: Optional[str] = None
    history_context: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """验证参数."""
        if not 0 <= self.student_level <= 1:
            raise ValueError(f"student_level must be in [0, 1], got {self.student_level}")
        if not 1 <= self.target_difficulty <= 10:
            raise ValueError(f"target_difficulty must be in [1, 10], got {self.target_difficulty}")


@dataclass
class StrategyResult:
    """策略执行结果.
    
    Attributes:
        success: 是否成功
        variant: 生成的变形题(成功时)
        error_message: 错误信息(失败时)
        metadata: 生成元数据
    """
    
    success: bool
    variant: Optional[VariantProblem] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class VariantStrategy(ABC):
    """变形题生成策略基类.
    
    所有具体策略必须继承此类并实现generate方法。
    
    Attributes:
        strategy_name: 策略名称
        strategy_type: 策略类型标识
        difficulty_adjustment: 难度调整系数
    """
    
    strategy_name: str = "base"
    strategy_type: str = "base"
    difficulty_adjustment: float = 0.0
    
    def __init__(self, model_client: Optional[Any] = None):
        """初始化策略.
        
        Args:
            model_client: 可选的模型客户端，用于AI辅助生成
        """
        self.model_client = model_client
        self._generation_metadata: Dict[str, Any] = {}
    
    @abstractmethod
    async def generate(
        self,
        context: StrategyContext,
    ) -> StrategyResult:
        """生成变形题.
        
        Args:
            context: 策略执行上下文
            
        Returns:
            策略执行结果
        """
        pass
    
    @abstractmethod
    def can_apply(
        self,
        problem: Problem,
        error_type: ErrorType,
    ) -> bool:
        """判断策略是否适用于给定题目.
        
        Args:
            problem: 原题
            error_type: 错误类型
            
        Returns:
            是否适用
        """
        pass
    
    def get_confidence_score(
        self,
        context: StrategyContext,
    ) -> float:
        """获取策略适用置信度(0-1).
        
        Args:
            context: 策略执行上下文
            
        Returns:
            置信度分数
        """
        if not self.can_apply(context.original_problem, context.error_type):
            return 0.0
        return 0.8  # 默认置信度
    
    def _calculate_target_difficulty(
        self,
        original_difficulty: int,
        student_level: float,
        error_type: ErrorType,
    ) -> int:
        """计算目标难度.
        
        基于原题难度、学生水平和错误类型计算合适的目标难度。
        
        Args:
            original_difficulty: 原题难度(1-10)
            student_level: 学生水平(0-1)
            error_type: 错误类型
            
        Returns:
            目标难度(1-10)
        """
        # 基础调整：根据学生水平
        level_adjustment = (0.5 - student_level) * 4  # -2 到 +2
        
        # 错误类型调整
        error_adjustment = self._get_error_type_adjustment(error_type)
        
        # 策略特定调整
        strategy_adjustment = self.difficulty_adjustment
        
        # 计算目标难度
        target = original_difficulty + level_adjustment + error_adjustment + strategy_adjustment
        
        # 确保在有效范围内
        return max(1, min(10, int(round(target))))
    
    def _get_error_type_adjustment(self, error_type: ErrorType) -> float:
        """根据错误类型获取难度调整.
        
        Args:
            error_type: 错误类型
            
        Returns:
            难度调整值
        """
        adjustments = {
            ErrorType.CONCEPT_MISUNDERSTANDING: -1,
            ErrorType.CALCULATION_ERROR: 0,
            ErrorType.LOGICAL_FLAW: 1,
            ErrorType.CARELESS_MISTAKE: 0,
            ErrorType.KNOWLEDGE_GAP: -2,
        }
        return adjustments.get(error_type, 0)
    
    def _create_variant_problem(
        self,
        original: Problem,
        content: str,
        answer: Optional[str],
        solution: Optional[str],
        difficulty: int,
        context: StrategyContext,
    ) -> VariantProblem:
        """创建变形题对象.
        
        Args:
            original: 原题
            content: 变形后题目内容
            answer: 变形题答案
            solution: 变形题解题过程
            difficulty: 难度
            context: 执行上下文
            
        Returns:
            变形题对象
        """
        from src.domain.models.variant import GenerationStrategy
        
        # 映射策略类型到GenerationStrategy
        strategy_mapping = {
            "numeric": GenerationStrategy.VALUE_SUBSTITUTION,
            "inverse": GenerationStrategy.REVERSE_CONSTRUCT,
            "context": GenerationStrategy.CONTEXT_CHANGE,
        }
        
        strategy = strategy_mapping.get(
            self.strategy_type,
            GenerationStrategy.VALUE_SUBSTITUTION
        )
        
        return VariantProblem(
            original_problem_id=original.id,
            content=content,
            difficulty=difficulty,
            target_concept=context.original_problem.knowledge_points[0] if context.original_problem.knowledge_points else "general",
            error_type=context.error_type,
            strategy=strategy,
            answer=answer,
            solution=solution,
            metadata={
                "strategy_name": self.strategy_name,
                "strategy_type": self.strategy_type,
                "original_difficulty": original.difficulty,
                "student_level": context.student_level,
                "generation_context": self._generation_metadata,
            },
        )
    
    def _extract_numbers(self, text: str) -> List[tuple]:
        """提取文本中的数字.
        
        Args:
            text: 输入文本
            
        Returns:
            数字列表，每个元素为(原始字符串, 数值, 类型, 开始位置, 结束位置)
        """
        import re
        
        numbers = []
        
        # 提取整数和小数 - 使用更宽松的模式
        # 匹配小数
        float_pattern = r'\d+\.\d+'
        # 匹配整数 - 匹配单独的数字序列
        int_pattern = r'\d+'
        # 匹配分数
        fraction_pattern = r'\d+/\d+'
        
        # 查找小数
        for match in re.finditer(float_pattern, text):
            num_str = match.group()
            numbers.append((num_str, float(num_str), "float", match.start(), match.end()))
        
        # 查找整数(排除已匹配的小数部分)
        for match in re.finditer(int_pattern, text):
            num_str = match.group()
            start, end = match.start(), match.end()
            # 检查是否已被小数匹配
            if not any(start >= n[3] and end <= n[4] for n in numbers):
                numbers.append((num_str, int(num_str), "int", start, end))
        
        # 查找分数
        for match in re.finditer(fraction_pattern, text):
            num_str = match.group()
            parts = num_str.split('/')
            value = int(parts[0]) / int(parts[1])
            numbers.append((num_str, value, "fraction", match.start(), match.end()))
        
        return sorted(numbers, key=lambda x: x[3])
    
    def _generate_numbers_at_difficulty(
        self,
        count: int,
        difficulty: int,
        num_type: str = "auto",
    ) -> List[Any]:
        """生成指定难度的数字.
        
        Args:
            count: 生成数量
            difficulty: 难度(1-10)
            num_type: 数字类型(int/float/fraction/auto)
            
        Returns:
            数字列表
        """
        import random
        
        results = []
        for _ in range(count):
            if num_type == "auto":
                # 根据难度自动选择类型
                if difficulty <= 3:
                    num_type_selected = "int"
                elif difficulty <= 6:
                    num_type_selected = random.choice(["int", "float"])
                else:
                    num_type_selected = random.choice(["int", "float", "fraction"])
            else:
                num_type_selected = num_type
            
            if num_type_selected == "int":
                # 整数：难度越高范围越大
                if difficulty <= 3:
                    num = random.randint(1, 10)
                elif difficulty <= 6:
                    num = random.randint(1, 100)
                else:
                    num = random.randint(1, 1000)
            elif num_type_selected == "float":
                # 小数
                if difficulty <= 5:
                    num = round(random.uniform(0.1, 10.0), 1)
                else:
                    num = round(random.uniform(0.01, 100.0), 2)
            elif num_type_selected == "fraction":
                # 分数
                denom = random.randint(2, 10 if difficulty <= 7 else 20)
                numer = random.randint(1, denom - 1)
                num = f"{numer}/{denom}"
            else:
                num = random.randint(1, 10)
            
            results.append(num)
        
        return results
