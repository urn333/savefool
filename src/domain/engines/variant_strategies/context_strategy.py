"""情境迁移变形策略.

将题目从一个生活情境迁移到另一个，保持数学结构不变。
适用于应用题的情境替换，如：苹果问题 → 橙子问题。
"""

import random
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from src.domain.engines.variant_strategies.base import (
    StrategyContext,
    StrategyResult,
    VariantStrategy,
)
from src.domain.models.diagnosis import ErrorType, Problem


class ContextTransferStrategy(VariantStrategy):
    """情境迁移变形策略.
    
    功能特点：
    - 识别题目中的情境元素(物品、人物、地点等)
    - 替换为同类别的其他元素
    - 保持数学结构不变
    - 情境自然度检查
    
    适用场景：
    - 审题错误(ErrorType.READING_ERROR)
    - 粗心错误(ErrorType.CARELESS_MISTAKE)
    - 概念误解(ErrorType.CONCEPT_MISUNDERSTANDING)
    - 需要泛化理解的练习
    """
    
    strategy_name = "情境迁移"
    strategy_type = "context"
    difficulty_adjustment = 0.0  # 保持难度不变
    
    # 情境替换词库
    CONTEXT_CATEGORIES = {
        "fruit": {
            "words": ["苹果", "橙子", "香蕉", "梨", "桃子", "草莓", "葡萄", "西瓜", "芒果", "樱桃"],
            "measure": ["个", "斤", "千克", "箱", "篮"],
        },
        "food": {
            "words": ["蛋糕", "面包", "饼干", "糖果", "巧克力", "冰淇淋", "包子", "饺子", "米饭", "面条"],
            "measure": ["个", "块", "片", "包", "盒", "碗", "盘"],
        },
        "animal": {
            "words": ["小猫", "小狗", "小鸟", "小兔", "小鸡", "小鸭", "小鱼", "小马", "小羊", "小牛"],
            "measure": ["只", "条", "匹", "头"],
        },
        "toy": {
            "words": ["积木", "汽车", "娃娃", "球", "拼图", "橡皮泥", "画板", "图书", "乐器", "机器人"],
            "measure": ["个", "套", "辆", "本", "盒"],
        },
        "school": {
            "words": ["铅笔", "橡皮", "尺子", "本子", "书包", "文具盒", "课本", "作业本", "彩笔", "胶水"],
            "measure": ["支", "块", "把", "本", "个", "盒"],
        },
        "person": {
            "words": ["小明", "小红", "小刚", "小丽", "小军", "小芳", "小华", "小敏", "小亮", "小静"],
            "measure": ["个", "名", "位"],
        },
        "family": {
            "words": ["妈妈", "爸爸", "爷爷", "奶奶", "哥哥", "姐姐", "弟弟", "妹妹", "叔叔", "阿姨"],
            "measure": ["个", "位"],
        },
        "place": {
            "words": ["学校", "家里", "商店", "超市", "公园", "图书馆", "电影院", "医院", "餐厅", "动物园"],
            "measure": ["个", "家", "所", "座"],
        },
        "vehicle": {
            "words": ["汽车", "自行车", "公交车", "火车", "飞机", "轮船", "摩托车", "卡车", "出租车", "地铁"],
            "measure": ["辆", "架", "艘", "列", "台"],
        },
        "money": {
            "words": ["元", "角", "分", "块钱", "元钱"],
            "measure": [],
        },
    }
    
    # 常见动词替换
    ACTION_WORDS = {
        "买": ["买", "卖", "送", "收到", "花了", "用了"],
        "有": ["有", "带着", "拿着", "装了"],
        "吃": ["吃", "喝", "分", "给"],
        "走": ["走", "跑", "飞", "开", "行驶"],
        "做": ["做", "完成", "制作", "准备"],
    }
    
    # 情境类型关键词
    CONTEXT_KEYWORDS = {
        "shopping": ["买", "卖", "钱", "价格", "元", "商店", "超市"],
        "distribution": ["分", "给", "每人", "平均", "分配"],
        "comparison": ["比", "多", "少", "更", "一样"],
        "total": ["一共", "总共", "合计", "总和"],
        "remaining": ["还剩", "剩下", "还有", "剩余"],
        "speed": ["速度", "时间", "路程", "每小时", "分钟"],
    }
    
    def can_apply(
        self,
        problem: Problem,
        error_type: ErrorType,
    ) -> bool:
        """判断策略是否适用.
        
        适用条件：
        - 题目包含可替换的情境元素
        - 是应用题类型
        
        Args:
            problem: 原题
            error_type: 错误类型
            
        Returns:
            是否适用
        """
        content = problem.content
        
        # 检查是否有可替换的情境词
        has_context_word = False
        for category in self.CONTEXT_CATEGORIES.values():
            for word in category["words"]:
                if word in content:
                    has_context_word = True
                    break
            if has_context_word:
                break
        
        if not has_context_word:
            # 检查是否有通用的人物名字
            if not re.search(r"[小|阿][\u4e00-\u9fa5]", content):
                return False
        
        # 几乎所有错误类型都适合情境迁移
        applicable_errors = {
            ErrorType.CARELESS_MISTAKE,
            ErrorType.CONCEPT_MISUNDERSTANDING,
            ErrorType.CALCULATION_ERROR,
            ErrorType.LOGICAL_FLAW,
            ErrorType.KNOWLEDGE_GAP,
        }
        
        return error_type in applicable_errors
    
    async def generate(
        self,
        context: StrategyContext,
    ) -> StrategyResult:
        """生成情境迁移变形题.
        
        Args:
            context: 策略执行上下文
            
        Returns:
            生成结果
        """
        try:
            original = context.original_problem
            content = original.content
            
            # 1. 识别题目中的情境元素
            detected_contexts = self._detect_context_elements(content)
            if not detected_contexts:
                return StrategyResult(
                    success=False,
                    error_message="题目中没有识别到可替换的情境元素",
                )
            
            # 2. 生成替换映射
            replacement_mapping = self._generate_replacements(
                detected_contexts,
                content,
            )
            
            if not replacement_mapping:
                return StrategyResult(
                    success=False,
                    error_message="无法生成有效的情境替换",
                )
            
            # 3. 应用替换
            new_content = self._apply_replacements(content, replacement_mapping)
            
            # 4. 验证情境自然度
            naturalness_score = self._check_naturalness(new_content)
            if naturalness_score < 0.5:
                # 尝试重新生成
                replacement_mapping = self._generate_replacements(
                    detected_contexts,
                    content,
                    retry=True,
                )
                new_content = self._apply_replacements(content, replacement_mapping)
                naturalness_score = self._check_naturalness(new_content)
            
            # 5. 计算目标难度(情境迁移不改变难度)
            target_difficulty = self._calculate_target_difficulty(
                original.difficulty,
                context.student_level,
                context.error_type,
            )
            # 由于情境迁移不改变难度，使用原题难度
            target_difficulty = original.difficulty
            
            # 6. 更新解题过程(情境相关部分)
            new_solution = None
            if original.solution_steps:
                new_solution = self._update_solution_context(
                    original.solution_steps,
                    replacement_mapping,
                )
            
            # 7. 验证结果
            validation_errors = self._validate_context_result(
                new_content, original, replacement_mapping
            )
            if validation_errors:
                return StrategyResult(
                    success=False,
                    error_message=f"验证失败: {'; '.join(validation_errors)}",
                )
            
            # 8. 创建变形题对象
            variant = self._create_variant_problem(
                original=original,
                content=new_content,
                answer=original.answer,  # 答案不变
                solution=new_solution,
                difficulty=target_difficulty,
                context=context,
            )
            
            # 记录元数据
            self._generation_metadata = {
                "detected_contexts": detected_contexts,
                "replacement_mapping": replacement_mapping,
                "naturalness_score": naturalness_score,
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
    
    def _detect_context_elements(
        self,
        content: str,
    ) -> List[Dict[str, Any]]:
        """识别题目中的情境元素.
        
        Args:
            content: 题目内容
            
        Returns:
            检测到的情境元素列表
        """
        detected = []
        
        for category_name, category_data in self.CONTEXT_CATEGORIES.items():
            for word in category_data["words"]:
                if word in content:
                    # 找到所有出现位置
                    for match in re.finditer(re.escape(word), content):
                        detected.append({
                            "category": category_name,
                            "word": word,
                            "position": (match.start(), match.end()),
                            "measure_words": category_data["measure"],
                        })
        
        # 检测情境类型
        context_types = []
        for ctx_type, keywords in self.CONTEXT_KEYWORDS.items():
            if any(kw in content for kw in keywords):
                context_types.append(ctx_type)
        
        return detected
    
    def _generate_replacements(
        self,
        detected_contexts: List[Dict[str, Any]],
        original_content: str,
        retry: bool = False,
    ) -> Dict[str, str]:
        """生成替换映射.
        
        Args:
            detected_contexts: 检测到的情境元素
            original_content: 原题内容
            retry: 是否是重试
            
        Returns:
            替换映射 {原词: 新词}
        """
        mapping = {}
        used_replacements = set()
        
        # 按类别分组
        by_category: Dict[str, List[Dict]] = {}
        for ctx in detected_contexts:
            cat = ctx["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(ctx)
        
        # 为每个类别生成替换
        for category, contexts in by_category.items():
            available_words = [
                w for w in self.CONTEXT_CATEGORIES[category]["words"]
                if w not in [c["word"] for c in contexts] and w not in used_replacements
            ]
            
            if retry:
                # 重试时使用不同的随机种子
                random.shuffle(available_words)
            
            for ctx in contexts:
                original_word = ctx["word"]
                if original_word in mapping:
                    continue
                
                # 选择替换词
                if available_words:
                    replacement = available_words.pop(0)
                    mapping[original_word] = replacement
                    used_replacements.add(replacement)
                else:
                    # 如果没有可用替换，尝试跨类别替换
                    replacement = self._find_cross_category_replacement(
                        ctx, used_replacements
                    )
                    if replacement:
                        mapping[original_word] = replacement
                        used_replacements.add(replacement)
        
        return mapping
    
    def _find_cross_category_replacement(
        self,
        context: Dict[str, Any],
        used: Set[str],
    ) -> Optional[str]:
        """查找跨类别替换词.
        
        Args:
            context: 情境元素
            used: 已使用的词
            
        Returns:
            替换词或None
        """
        # 寻找语义相近的类别
        category = context["category"]
        
        # 类别相似度映射
        similar_categories = {
            "fruit": ["food"],
            "food": ["fruit"],
            "person": ["family"],
            "family": ["person"],
            "toy": ["school"],
            "school": ["toy"],
        }
        
        similar = similar_categories.get(category, [])
        for sim_cat in similar:
            available = [
                w for w in self.CONTEXT_CATEGORIES[sim_cat]["words"]
                if w not in used
            ]
            if available:
                return random.choice(available)
        
        return None
    
    def _apply_replacements(
        self,
        content: str,
        mapping: Dict[str, str],
    ) -> str:
        """应用替换映射.
        
        Args:
            content: 原内容
            mapping: 替换映射
            
        Returns:
            替换后的内容
        """
        # 按长度排序，先替换长的避免部分替换
        sorted_items = sorted(mapping.items(), key=lambda x: len(x[0]), reverse=True)
        
        result = content
        for old, new in sorted_items:
            result = result.replace(old, new)
        
        return result
    
    def _check_naturalness(self, content: str) -> float:
        """检查情境自然度.
        
        评估替换后的题目是否自然、合理。
        
        Args:
            content: 题目内容
            
        Returns:
            自然度分数(0-1)
        """
        score = 1.0
        
        # 1. 检查量词搭配
        unnatural_patterns = [
            (r"\d+个\s*学校", 0.3),  # "个学校"不太自然
            (r"\d+只\s*汽车", 0.3),  # "只汽车"不自然
            (r"\d+辆\s*苹果", 0.3),  # "辆苹果"不自然
            (r"\d+本\s*铅笔", 0.3),  # "本铅笔"不自然
        ]
        
        for pattern, penalty in unnatural_patterns:
            if re.search(pattern, content):
                score -= penalty
        
        # 2. 检查句子流畅度
        # 检查是否有明显的语法问题
        grammar_issues = [
            r"[，,]\s*[，,]",  # 连续逗号
            r"的\s*的",  # 连续"的"
            r"了\s*了",  # 连续"了"
        ]
        
        for pattern in grammar_issues:
            if re.search(pattern, content):
                score -= 0.1
        
        # 3. 检查是否有不匹配的词汇组合
        weird_combinations = [
            ("飞机", "吃"),
            ("汽车", "喝"),
            ("铅笔", "吃"),
        ]
        
        for word1, word2 in weird_combinations:
            if word1 in content and word2 in content:
                score -= 0.2
        
        return max(0.0, score)
    
    def _update_solution_context(
        self,
        solution_steps: List[str],
        mapping: Dict[str, str],
    ) -> str:
        """更新解题过程中的情境.
        
        Args:
            solution_steps: 原解题步骤
            mapping: 替换映射
            
        Returns:
            更新后的解题过程
        """
        updated_steps = []
        
        for step in solution_steps:
            new_step = step
            for old, new in mapping.items():
                new_step = new_step.replace(old, new)
            updated_steps.append(new_step)
        
        return "\n".join(updated_steps)
    
    def _validate_context_result(
        self,
        content: str,
        original: Problem,
        mapping: Dict[str, str],
    ) -> List[str]:
        """验证情境迁移结果.
        
        Args:
            content: 新题目内容
            original: 原题
            mapping: 替换映射
            
        Returns:
            验证错误列表
        """
        errors = []
        
        # 1. 检查内容非空
        if not content or len(content.strip()) < 5:
            errors.append("题目内容过短")
        
        # 2. 检查是否有替换发生
        if not mapping:
            errors.append("没有进行情境替换")
        
        # 3. 检查内容变化
        if content == original.content:
            errors.append("题目内容未发生变化")
        
        # 4. 检查数字是否保持一致
        original_numbers = self._extract_numbers(original.content)
        new_numbers = self._extract_numbers(content)
        
        if len(original_numbers) != len(new_numbers):
            errors.append("数字数量不一致，可能替换过程出错")
        
        # 5. 检查运算符是否保持一致
        original_ops = set(c for c in original.content if c in "+-×÷*/=＋－＊／")
        new_ops = set(c for c in content if c in "+-×÷*/=＋－＊／")
        
        if original_ops != new_ops:
            errors.append("运算符发生变化")
        
        # 6. 检查自然度
        naturalness = self._check_naturalness(content)
        if naturalness < 0.3:
            errors.append(f"情境自然度过低({naturalness:.2f})")
        
        return errors
    
    def get_confidence_score(
        self,
        context: StrategyContext,
    ) -> float:
        """获取策略适用置信度.
        
        情境迁移对审题错误和粗心错误的置信度较高。
        
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
        if context.error_type == ErrorType.CARELESS_MISTAKE:
            base_confidence = 0.88
        elif context.error_type == ErrorType.CONCEPT_MISUNDERSTANDING:
            base_confidence = 0.85
        
        # 检测情境元素数量
        detected = self._detect_context_elements(context.original_problem.content)
        unique_categories = len(set(d["category"] for d in detected))
        if unique_categories >= 2:
            base_confidence += 0.05
        
        return min(1.0, base_confidence)
