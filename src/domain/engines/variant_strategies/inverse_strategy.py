"""逆运算变形策略.

将原题改为已知结果求输入的逆运算题目。
保持数学等价性，难度提升20-50%。
"""

import re
from typing import Any, Dict, List, Optional, Tuple, Union

from src.domain.engines.variant_strategies.base import (
    StrategyContext,
    StrategyResult,
    VariantStrategy,
)
from src.domain.models.diagnosis import ErrorType, Problem
from src.domain.models.variant import VariantProblem


class InverseOperationStrategy(VariantStrategy):
    """逆运算变形策略.
    
    功能特点：
    - 原题: 3+5=? → 变形: 8-5=?
    - 保持数学等价性
    - 难度提升20-50%
    - 适用于逻辑错误和概念理解
    
    适用场景：
    - 逻辑缺陷(ErrorType.LOGICAL_FLAW)
    - 概念误解(ErrorType.CONCEPT_MISUNDERSTANDING)
    - 需要理解逆运算的练习
    """
    
    strategy_name = "逆运算变形"
    strategy_type = "inverse"
    difficulty_adjustment = 1.5  # 难度提升1.5级
    
    # 运算符映射(正向->逆向)
    OPERATOR_INVERSE = {
        "+": "-",
        "-": "+",
        "×": "÷",
        "*": "÷",
        "÷": "×",
        "/": "×",
    }
    
    # 运算词汇映射
    OPERATION_WORDS = {
        "加": "减",
        "减": "加",
        "乘": "除",
        "除": "乘",
        "加上": "减去",
        "减去": "加上",
        "乘以": "除以",
        "除以": "乘以",
        "增加": "减少",
        "减少": "增加",
        "一共": "还剩",
        "还剩": "一共",
        "总共": "剩余",
        "剩余": "总共",
    }
    
    # 关键词模式
    PATTERNS = {
        "addition": [
            r"(.+?)\s*([+＋]\s*|加上|增加|多了)\s*(.+?)\s*[，,。]?\s*(?:等于|是|为|=)\s*\?",
            r"(.+?)\s*和\s*(.+?)\s*(?:相加|加在一起|一共是多少|总和是)",
        ],
        "subtraction": [
            r"(.+?)\s*([-－]\s*|减去|减少|少了|拿走|用去)\s*(.+?)\s*[，,。]?\s*(?:等于|是|为|=|还剩|剩余|还有)\s*\?",
            r"(?:从|用)\s*(.+?)\s*(?:中?去掉|减去|用去)\s*(.+?)\s*[，,。]?\s*(?:还剩|剩余|还有|等于)",
        ],
        "multiplication": [
            r"(.+?)\s*([×xX*＊]\s*|乘以|乘|倍)\s*(.+?)\s*[，,。]?\s*(?:等于|是|为|=)\s*\?",
            r"(.+?)\s*的\s*(\d+)\s*倍\s*(?:是|为|等于)\s*\?",
        ],
        "division": [
            r"(.+?)\s*([÷/]\s*|除以|除|平均|分成)\s*(.+?)\s*(?:份|个)?\s*[，,。]?\s*(?:等于|是|为|=|每份|每人|每个)",
            r"(?:把|将)\s*(.+?)\s*(?:平均|均等)?\s*(?:分成|分给|分给)\s*(.+?)\s*(?:份|人|个)",
        ],
    }
    
    def can_apply(
        self,
        problem: Problem,
        error_type: ErrorType,
    ) -> bool:
        """判断策略是否适用.
        
        适用条件：
        - 题目包含可逆运算
        - 有明确的运算关系
        - 错误类型为逻辑错误或概念错误
        
        Args:
            problem: 原题
            error_type: 错误类型
            
        Returns:
            是否适用
        """
        content = problem.content
        
        # 检查是否有运算符
        has_operator = any(op in content for op in "+-×÷*/=＋－＊／")
        has_operation_words = any(word in content for word in self.OPERATION_WORDS.keys())
        
        if not (has_operator or has_operation_words):
            return False
        
        # 检查错误类型
        applicable_errors = {
            ErrorType.LOGICAL_FLAW,
            ErrorType.CONCEPT_MISUNDERSTANDING,
            ErrorType.KNOWLEDGE_GAP,
            ErrorType.CALCULATION_ERROR,
        }
        
        return error_type in applicable_errors
    
    async def generate(
        self,
        context: StrategyContext,
    ) -> StrategyResult:
        """生成逆运算变形题.
        
        Args:
            context: 策略执行上下文
            
        Returns:
            生成结果
        """
        try:
            original = context.original_problem
            content = original.content
            
            # 1. 识别运算类型
            op_type, op_info = self._identify_operation(content)
            if not op_type:
                return StrategyResult(
                    success=False,
                    error_message="无法识别题目中的运算类型",
                )
            
            # 2. 提取数字和结构
            numbers = self._extract_numbers(content)
            if len(numbers) < 2:
                return StrategyResult(
                    success=False,
                    error_message="题目中数字不足，无法进行逆运算变形",
                )
            
            # 3. 构建逆运算题目
            new_content, new_answer = self._construct_inverse_problem(
                content,
                op_type,
                op_info,
                numbers,
            )
            
            if not new_content:
                return StrategyResult(
                    success=False,
                    error_message="无法构建逆运算题目",
                )
            
            # 4. 计算目标难度
            target_difficulty = self._calculate_target_difficulty(
                original.difficulty,
                context.student_level,
                context.error_type,
            )
            
            # 5. 更新解题过程
            new_solution = None
            if original.solution_steps:
                new_solution = self._generate_inverse_solution(
                    original.solution_steps,
                    op_type,
                )
            
            # 6. 验证结果
            validation_errors = self._validate_inverse_result(
                new_content, new_answer, original
            )
            if validation_errors:
                return StrategyResult(
                    success=False,
                    error_message=f"验证失败: {'; '.join(validation_errors)}",
                )
            
            # 7. 创建变形题对象
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
                "original_operation": op_type,
                "inverse_operation": self._get_inverse_operation(op_type),
                "target_difficulty": target_difficulty,
                "difficulty_increase": self.difficulty_adjustment,
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
    
    def _identify_operation(
        self,
        content: str,
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """识别题目中的运算类型.
        
        Args:
            content: 题目内容
            
        Returns:
            (运算类型, 运算信息)
        """
        content_lower = content.lower()
        
        # 检查加法
        for pattern in self.PATTERNS["addition"]:
            match = re.search(pattern, content)
            if match:
                return "addition", {"match": match, "pattern": pattern}
        
        # 检查减法
        for pattern in self.PATTERNS["subtraction"]:
            match = re.search(pattern, content)
            if match:
                return "subtraction", {"match": match, "pattern": pattern}
        
        # 检查乘法
        for pattern in self.PATTERNS["multiplication"]:
            match = re.search(pattern, content)
            if match:
                return "multiplication", {"match": match, "pattern": pattern}
        
        # 检查除法
        for pattern in self.PATTERNS["division"]:
            match = re.search(pattern, content)
            if match:
                return "division", {"match": match, "pattern": pattern}
        
        # 简化检测：检查运算符
        if any(op in content for op in ["+", "＋", "加上", "加", "add"]):
            return "addition", {"detected_by": "operator"}
        elif any(op in content for op in ["-", "－", "减去", "减", "subtract"]):
            return "subtraction", {"detected_by": "operator"}
        elif any(op in content for op in ["×", "*", "＊", "乘以", "乘", "multiply", "倍"]):
            return "multiplication", {"detected_by": "operator"}
        elif any(op in content for op in ["÷", "/", "／", "除以", "除", "divide", "平均"]):
            return "division", {"detected_by": "operator"}
        
        return None, {}
    
    def _get_inverse_operation(self, op_type: str) -> str:
        """获取逆运算类型.
        
        Args:
            op_type: 原运算类型
            
        Returns:
            逆运算类型
        """
        inverse_map = {
            "addition": "subtraction",
            "subtraction": "addition",
            "multiplication": "division",
            "division": "multiplication",
        }
        return inverse_map.get(op_type, op_type)
    
    def _construct_inverse_problem(
        self,
        content: str,
        op_type: str,
        op_info: Dict[str, Any],
        numbers: List[tuple],
    ) -> Tuple[Optional[str], Optional[str]]:
        """构建逆运算题目.
        
        Args:
            content: 原题内容
            op_type: 运算类型
            op_info: 运算信息
            numbers: 数字列表
            
        Returns:
            (新题目, 新答案)
        """
        # 提取前两个数字(通常是运算数)
        if len(numbers) < 2:
            return None, None
        
        num1_val = numbers[0][1]  # 第一个数字的值
        num2_val = numbers[1][1]  # 第二个数字的值
        
        # 尝试从原答案提取结果
        # 这里简化处理，实际应该解析原答案
        if op_type == "addition":
            # 加法逆运算: a + b = c -> c - b = a 或 c - a = b
            result = num1_val + num2_val
            new_content = self._build_inverse_content(
                content, op_type, result, num2_val, num1_val
            )
            new_answer = str(num1_val)
            
        elif op_type == "subtraction":
            # 减法逆运算: a - b = c -> c + b = a 或 a - c = b
            result = num1_val - num2_val
            new_content = self._build_inverse_content(
                content, op_type, result, num2_val, num1_val
            )
            new_answer = str(num1_val)
            
        elif op_type == "multiplication":
            # 乘法逆运算: a × b = c -> c ÷ b = a 或 c ÷ a = b
            result = num1_val * num2_val
            new_content = self._build_inverse_content(
                content, op_type, result, num2_val, num1_val
            )
            new_answer = str(num1_val)
            
        elif op_type == "division":
            # 除法逆运算: a ÷ b = c -> c × b = a 或 a ÷ c = b
            if num2_val != 0:
                result = num1_val / num2_val
                new_content = self._build_inverse_content(
                    content, op_type, result, num2_val, num1_val
                )
                new_answer = str(num1_val)
            else:
                return None, None
        else:
            return None, None
        
        return new_content, new_answer
    
    def _build_inverse_content(
        self,
        original_content: str,
        op_type: str,
        result: Union[int, float],
        known_operand: Union[int, float],
        unknown_operand: Union[int, float],
    ) -> str:
        """构建逆运算题目内容.
        
        Args:
            original_content: 原题内容
            op_type: 运算类型
            result: 运算结果
            known_operand: 已知操作数
            unknown_operand: 未知操作数(答案)
            
        Returns:
            新题目内容
        """
        # 简化处理：直接构建新问题
        inverse_op = self._get_inverse_operation(op_type)
        
        op_symbols = {
            "addition": "+",
            "subtraction": "-",
            "multiplication": "×",
            "division": "÷",
        }
        
        inverse_symbol = op_symbols.get(inverse_op, "?")
        
        # 构建新问题文本
        # 原: a + b = ?
        # 新: result - b = ? (求a) 或 result - a = ? (求b)
        new_content = f"如果结果是{result}，已知一个数是{known_operand}，另一个数是多少？"
        
        # 尝试保留原题的上下文描述
        # 提取原题中的情境词
        context_words = []
        for word in ["小明", "小红", "妈妈", "爸爸", "老师", "同学", "学校", "家里", "商店", "超市"]:
            if word in original_content:
                context_words.append(word)
        
        if context_words:
            # 构建带情境的问题
            if "一共" in original_content or "总共" in original_content:
                new_content = f"{context_words[0]}一共有{result}个，如果其中一部分是{known_operand}个，另一部分是多少个？"
            elif "平均" in original_content or "每" in original_content:
                new_content = f"如果每个{context_words[0]}分到{known_operand}个，总共需要{result}个，那么分给多少个{context_words[0]}？"
            elif "倍" in original_content:
                new_content = f"一个数是{known_operand}，另一个数是它的多少倍才能得到{result}？"
            else:
                new_content = f"在计算中，结果是{result}，已知一个加数是{known_operand}，另一个加数是多少？"
        
        return new_content
    
    def _generate_inverse_solution(
        self,
        original_steps: List[str],
        op_type: str,
    ) -> str:
        """生成逆运算的解题过程.
        
        Args:
            original_steps: 原解题步骤
            op_type: 运算类型
            
        Returns:
            新的解题过程
        """
        inverse_op = self._get_inverse_operation(op_type)
        
        op_names = {
            "addition": ("加", "和"),
            "subtraction": ("减", "差"),
            "multiplication": ("乘", "积"),
            "division": ("除", "商"),
        }
        
        original_name, original_result = op_names.get(op_type, ("运算", "结果"))
        inverse_name, _ = op_names.get(inverse_op, ("逆运算", "结果"))
        
        steps = [
            f"这是一个{original_name}法问题，需要用到{inverse_name}法来求解。",
            f"已知{original_result}和一个加数，求另一个加数，用{inverse_name}法。",
            f"列式：{original_result} - 已知加数 = 未知加数",
            f"计算得出答案。",
        ]
        
        return "\n".join(steps)
    
    def _validate_inverse_result(
        self,
        content: str,
        answer: Optional[str],
        original: Problem,
    ) -> List[str]:
        """验证逆运算结果.
        
        Args:
            content: 新题目内容
            answer: 新答案
            original: 原题
            
        Returns:
            验证错误列表
        """
        errors = []
        
        # 1. 检查内容非空
        if not content or len(content.strip()) < 10:
            errors.append("题目内容过短")
        
        # 2. 检查内容变化
        if content == original.content:
            errors.append("题目内容未发生变化")
        
        # 3. 检查逆运算特征词
        inverse_keywords = ["如果", "已知", "求", "多少", "另一个"]
        if not any(kw in content for kw in inverse_keywords):
            errors.append("题目缺少逆运算特征")
        
        # 4. 检查答案
        if answer:
            try:
                float(answer)
            except (ValueError, TypeError):
                errors.append("答案不是有效数字")
        
        return errors
    
    def get_confidence_score(
        self,
        context: StrategyContext,
    ) -> float:
        """获取策略适用置信度.
        
        逆运算策略对逻辑错误的置信度较高。
        
        Args:
            context: 策略执行上下文
            
        Returns:
            置信度分数
        """
        if not self.can_apply(context.original_problem, context.error_type):
            return 0.0
        
        # 基础置信度
        base_confidence = 0.75
        
        # 错误类型加成
        if context.error_type == ErrorType.LOGICAL_FLAW:
            base_confidence = 0.92
        elif context.error_type == ErrorType.CONCEPT_MISUNDERSTANDING:
            base_confidence = 0.88
        
        # 运算符数量加成
        content = context.original_problem.content
        op_count = sum(content.count(op) for op in "+-×÷*/")
        if op_count == 1:  # 单一运算更适合逆运算
            base_confidence += 0.08
        
        return min(1.0, base_confidence)
