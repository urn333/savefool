"""情境迁移变形策略.

将题目从一个情境迁移到另一个情境，保持数学结构不变。
"""

import random
import re
from typing import Dict, List

from .base import StrategyContext, StrategyResult, VariantStrategy
from src.domain.models.diagnosis import ErrorType, Problem


class ContextTransferStrategy(VariantStrategy):
    """情境迁移变形策略.
    
    将题目的实际背景进行迁移，保持核心数学关系不变。
    """
    
    strategy_name = "情境迁移"
    strategy_type = "context"
    difficulty_adjustment = 0.0
    
    # 情境映射表
    CONTEXT_MAPPINGS: Dict[str, List[str]] = {
        "苹果": ["橘子", "香蕉", "书本", "铅笔", "糖果"],
        "小明": ["小华", "小李", "小张", "小王"],
        "小红": ["小芳", "小丽", "小美", "小军"],
        "买": ["卖", "生产", "运输", "借阅"],
        "元": ["角", "分", "美元", "欧元"],
        "米": ["千米", "厘米", "毫米"],
        "分钟": ["小时", "秒"],
    }
    
    def can_apply(self, problem: Problem, error_type: ErrorType) -> bool:
        """判断是否适用.
        
        需要是应用题，包含可替换的情境元素。
        """
        content = problem.content
        
        # 检查是否有可替换的情境元素
        for keyword in self.CONTEXT_MAPPINGS.keys():
            if keyword in content:
                return True
        
        # 检查是否包含人名
        name_pattern = r'小[明华红芳丽军]+'
        if re.search(name_pattern, content):
            return True
        
        return False
    
    async def generate(self, context: StrategyContext) -> StrategyResult:
        """生成情境迁移变形题."""
        try:
            original = context.original_problem
            content = original.content
            
            # 执行情境替换
            new_content, replacements = self._apply_context_transfer(content)
            
            if not replacements:
                return StrategyResult(
                    success=False,
                    error_message="没有可替换的情境元素"
                )
            
            # 验证数学结构保持
            if not self._verify_structure_preservation(content, new_content):
                return StrategyResult(
                    success=False,
                    error_message="数学结构未保持"
                )
            
            # 创建变形题
            variant = self._create_variant_problem(
                original=original,
                content=new_content,
                answer=original.answer,
                solution=original.solution_steps,
                difficulty=context.target_difficulty,
                context=context,
            )
            
            return StrategyResult(
                success=True,
                variant=variant,
                metadata={
                    "replacements": replacements,
                    "structure_preserved": True,
                }
            )
            
        except Exception as e:
            return StrategyResult(
                success=False,
                error_message=f"情境迁移失败: {str(e)}"
            )
    
    def _apply_context_transfer(self, content: str) -> tuple:
        """应用情境替换."""
        new_content = content
        replacements = []
        
        for keyword, alternatives in self.CONTEXT_MAPPINGS.items():
            if keyword in new_content:
                # 随机选择替换词
                replacement = random.choice(alternatives)
                new_content = new_content.replace(keyword, replacement, 1)
                replacements.append({
                    "from": keyword,
                    "to": replacement
                })
        
        return new_content, replacements
    
    def _verify_structure_preservation(
        self, original: str, transformed: str
    ) -> bool:
        """验证数学结构保持."""
        # 提取数值
        orig_numbers = re.findall(r'\d+', original)
        trans_numbers = re.findall(r'\d+', transformed)
        
        # 数值应该相同
        return orig_numbers == trans_numbers
