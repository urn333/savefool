"""启发式讲解生成引擎.

功能追溯ID: F-DIAG-003
基于错误归因生成讲解，使用生活化类比（适合13-16岁），
生成分步提示，进行内容安全性检查。
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.infrastructure.logging import get_logger
from src.domain.models.diagnosis import ErrorType
from src.domain.engines.error_attribution import ErrorAttributionResult

logger = get_logger(__name__)


@dataclass
class ExplanationContent:
    """讲解内容.
    
    Attributes:
        main_explanation: 主要讲解文本
        analogy: 生活化类比
        step_hints: 分步提示
        key_points: 关键点提醒
        visual_description: 可视化描述（可选）
        practice_suggestion: 练习建议
    """
    main_explanation: str
    analogy: str
    step_hints: List[str] = field(default_factory=list)
    key_points: List[str] = field(default_factory=list)
    visual_description: str = ""
    practice_suggestion: str = ""


@dataclass
class ExplanationResult:
    """讲解生成结果.
    
    Attributes:
        problem_id: 题目ID
        student_id: 学生ID
        content: 讲解内容
        safety_score: 安全性评分
        age_appropriate: 是否适合目标年龄段
        difficulty_level: 难度等级
        estimated_reading_time: 预计阅读时间(秒)
    """
    problem_id: str
    student_id: str
    content: ExplanationContent
    safety_score: float = 1.0
    age_appropriate: bool = True
    difficulty_level: str = "medium"
    estimated_reading_time: int = 30


class ExplanationGenerator:
    """启发式讲解生成引擎.
    
    基于错误归因生成适合13-16岁学生的启发式讲解：
    1. 使用生活化类比让抽象概念具体化
    2. 分步提示引导学生自主思考
    3. 内容安全性检查确保适合青少年
    
    Example:
        >>> generator = ExplanationGenerator()
        >>> result = await generator.generate(
        ...     attribution_result=attribution_result,
        ...     problem_content="解方程 2x + 5 = 15",
        ... )
    """
    
    # 类比模板库（适合13-16岁）
    ANALOGY_TEMPLATES = {
        ErrorType.CALCULATION_ERROR: [
            "就像打游戏算伤害值，少按一个技能就可能输掉团战",
            "好比手机电量计算，20%和2%的差别就是能不能撑到回家",
            "就像跑步计时，差0.1秒可能就是第一名和第十名的区别",
            "好比做奶茶配方，糖多了少了味道完全不一样",
        ],
        ErrorType.CONCEPT_MISUNDERSTANDING: [
            "就像把'点赞'理解成'收藏'，功能搞混了",
            "好比以为'WiFi'和'流量'是一回事，其实完全不同",
            "就像把'转发'当成'评论'，操作的对象搞错了",
            "好比以为所有耳机插口都一样，其实有3.5mm和Type-C之分",
        ],
        ErrorType.LOGICAL_FLAW: [
            "就像导航路线规划，少了一个转弯就到不了目的地",
            "好比解谜游戏，跳过关卡直接看结局就失去意义了",
            "就像搭积木，底层不稳上面再好看也会倒",
            "好比做饭，顺序错了可能就把糖当成盐放了",
        ],
        ErrorType.CARELESS_MISTAKE: [
            "就像发消息发错群，内容对了但地方错了",
            "好比输密码，数字都对但顺序错了就是打不开",
            "就像买东西看错价格标签，小数点看错就是10倍差距",
            "好比设置闹钟，AM和PM没分清就起不来了",
        ],
        ErrorType.KNOWLEDGE_GAP: [
            "就像玩游戏没解锁技能，看到高级操作不知道怎么放",
            "好比用手机不会截图，功能在那里就是不知道怎么用",
            "就像进了新地图，NPC说的术语听不懂",
            "好比看外语片没字幕，大概能猜但细节全错过了",
        ],
    }
    
    # 安全词过滤列表
    UNSAFE_PATTERNS = [
        r'\b(暴力|血腥|色情|赌博|毒品|自杀|自残)\w*',
        r'\b(杀死|伤害|攻击)\s+(?:他人|别人|同学)\b',
        r'\b(逃学|旷课)\s+(?:方法|技巧)\b',
        r'\b(作弊|抄袭)\s+(?:技巧|方法|攻略)\b',
    ]
    
    # 鼓励性结束语
    ENCOURAGEMENTS = [
        "错了没关系，找出原因下次就对了！",
        "每个错误都是进步的机会，继续加油！",
        "发现问题就是解决问题的开始，你很棒！",
        "掌握了这个，以后类似的题都难不倒你！",
        "错题是最好的老师，记住这次的经验！",
    ]
    
    def __init__(self):
        """初始化讲解生成器."""
        self.logger = get_logger(__name__)
    
    async def generate(
        self,
        attribution_result: ErrorAttributionResult,
        problem_content: str,
        correct_solution: Optional[str] = None,
        subject: str = "math",
    ) -> ExplanationResult:
        """生成启发式讲解.
        
        Args:
            attribution_result: 归因分析结果
            problem_content: 题目内容
            correct_solution: 正确解答（可选）
            subject: 学科
            
        Returns:
            讲解生成结果
        """
        self.logger.info(
            "explanation_generation_start",
            student_id=attribution_result.student_id,
            problem_id=attribution_result.problem_id,
            error_type=attribution_result.error_type.value if attribution_result.error_type else None,
        )
        
        # 生成主要讲解
        main_explanation = self._generate_main_explanation(
            attribution_result, problem_content, correct_solution
        )
        
        # 生成类比
        analogy = self._generate_analogy(attribution_result)
        
        # 生成分步提示
        step_hints = self._generate_step_hints(
            attribution_result, correct_solution
        )
        
        # 生成关键点
        key_points = self._generate_key_points(attribution_result)
        
        # 生成可视化描述
        visual_description = self._generate_visual_description(
            problem_content, attribution_result.error_type
        )
        
        # 生成练习建议
        practice_suggestion = self._generate_practice_suggestion(
            attribution_result
        )
        
        content = ExplanationContent(
            main_explanation=main_explanation,
            analogy=analogy,
            step_hints=step_hints,
            key_points=key_points,
            visual_description=visual_description,
            practice_suggestion=practice_suggestion,
        )
        
        # 安全性检查
        safety_score = self._check_safety(content)
        
        # 年龄适配性检查
        age_appropriate = self._check_age_appropriateness(content)
        
        # 计算难度等级
        difficulty_level = self._estimate_difficulty(content)
        
        # 估算阅读时间
        reading_time = self._estimate_reading_time(content)
        
        result = ExplanationResult(
            problem_id=attribution_result.problem_id,
            student_id=attribution_result.student_id,
            content=content,
            safety_score=safety_score,
            age_appropriate=age_appropriate,
            difficulty_level=difficulty_level,
            estimated_reading_time=reading_time,
        )
        
        self.logger.info(
            "explanation_generation_complete",
            problem_id=attribution_result.problem_id,
            safety_score=safety_score,
            age_appropriate=age_appropriate,
        )
        
        return result
    
    def _generate_main_explanation(
        self,
        attribution_result: ErrorAttributionResult,
        problem_content: str,
        correct_solution: Optional[str],
    ) -> str:
        """生成主要讲解.
        
        Args:
            attribution_result: 归因结果
            problem_content: 题目内容
            correct_solution: 正确解答
            
        Returns:
            主要讲解文本
        """
        parts = []
        
        # 开场：指出错误
        error_type = attribution_result.error_type
        if error_type == ErrorType.CARELESS_MISTAKE:
            parts.append("这道题你答错了，看起来可能是粗心导致的。")
        elif error_type == ErrorType.CALCULATION_ERROR:
            parts.append("这道题的计算过程有问题，让我帮你梳理一下。")
        elif error_type == ErrorType.CONCEPT_MISUNDERSTANDING:
            parts.append("这道题涉及到一些概念理解，我们一起来看看。")
        elif error_type == ErrorType.LOGICAL_FLAW:
            parts.append("这道题的推理过程有个小漏洞，我们来补上它。")
        else:
            parts.append("这道题答错了，没关系，我们一起来看看原因。")
        
        # 原因分析
        parts.append(f"\n主要原因是：{attribution_result.primary_cause}")
        
        if attribution_result.secondary_causes:
            parts.append(f"另外还可能涉及：{'、'.join(attribution_result.secondary_causes[:2])}")
        
        # 知识缺口提醒
        if attribution_result.knowledge_gaps:
            gaps_str = "、".join(attribution_result.knowledge_gaps[:2])
            parts.append(f"\n这里涉及的知识点：{gaps_str}")
        
        # 结束鼓励
        import random
        parts.append(f"\n{random.choice(self.ENCOURAGEMENTS)}")
        
        return "\n".join(parts)
    
    def _generate_analogy(
        self,
        attribution_result: ErrorAttributionResult,
    ) -> str:
        """生成生活化类比.
        
        Args:
            attribution_result: 归因结果
            
        Returns:
            类比文本
        """
        import random
        
        error_type = attribution_result.error_type
        if not error_type:
            error_type = ErrorType.KNOWLEDGE_GAP
        
        templates = self.ANALOGY_TEMPLATES.get(error_type, [])
        
        if templates:
            analogy = random.choice(templates)
            return f"💡 打个比方：{analogy}"
        
        return "💡 学习就像升级打怪，每个关卡都要稳扎稳打。"
    
    def _generate_step_hints(
        self,
        attribution_result: ErrorAttributionResult,
        correct_solution: Optional[str],
    ) -> List[str]:
        """生成分步提示.
        
        Args:
            attribution_result: 归因结果
            correct_solution: 正确解答
            
        Returns:
            分步提示列表
        """
        hints = []
        
        error_type = attribution_result.error_type
        
        # 基于错误类型生成提示
        if error_type == ErrorType.CARELESS_MISTAKE:
            hints.append("✓ 重新读一遍题目，圈出关键数字和条件")
            hints.append("✓ 把答案代入原题验算一下")
            hints.append("✓ 检查计算过程，特别是符号和小数点")
        elif error_type == ErrorType.CALCULATION_ERROR:
            hints.append("✓ 先列出所有已知条件和要求的量")
            hints.append("✓ 写出计算公式，再代入数字")
            hints.append("✓ 分步计算，不要跳步")
        elif error_type == ErrorType.CONCEPT_MISUNDERSTANDING:
            hints.append("✓ 回顾相关的定义和公式")
            hints.append("✓ 找一个简单的例子理解概念")
            hints.append("✓ 对比正确和错误的用法有什么区别")
        elif error_type == ErrorType.LOGICAL_FLAW:
            hints.append("✓ 画个流程图或思维导图理清思路")
            hints.append("✓ 检查每一步推理的依据")
            hints.append("✓ 看看有没有遗漏的条件")
        else:
            hints.append("✓ 先理解题目问的是什么")
            hints.append("✓ 回忆相关的知识点")
            hints.append("✓ 尝试用不同的方法解题")
        
        return hints[:4]  # 最多4个提示
    
    def _generate_key_points(
        self,
        attribution_result: ErrorAttributionResult,
    ) -> List[str]:
        """生成关键点提醒.
        
        Args:
            attribution_result: 归因结果
            
        Returns:
            关键点列表
        """
        points = []
        
        # 基于归因添加关键点
        if attribution_result.is_careless_pattern:
            points.append("⚠️ 你最近粗心错误较多，做题时要多留心")
        
        if attribution_result.historical_similarity > 0.5:
            points.append("⚠️ 这个错误类型你之前也出现过，需要重点注意")
        
        if attribution_result.knowledge_gaps:
            points.append(f"📚 重点掌握：{'、'.join(attribution_result.knowledge_gaps[:2])}")
        
        # 基于错误类型的通用关键点
        error_type = attribution_result.error_type
        if error_type == ErrorType.CALCULATION_ERROR:
            points.append("🧮 计算时注意：符号、小数点、进位借位")
        elif error_type == ErrorType.LOGICAL_FLAW:
            points.append("🧠 逻辑推理要步步有据")
        
        if not points:
            points.append("📝 整理错题，定期复习")
        
        return points[:3]
    
    def _generate_visual_description(
        self,
        problem_content: str,
        error_type: Optional[ErrorType],
    ) -> str:
        """生成可视化描述.
        
        Args:
            problem_content: 题目内容
            error_type: 错误类型
            
        Returns:
            可视化描述
        """
        # 根据题目类型提供可视化建议
        if "方程" in problem_content or "x" in problem_content:
            return "🎯 想象天平两边保持平衡，左边的操作右边也要同样做"
        elif "几何" in problem_content or "角" in problem_content or "边" in problem_content:
            return "🎯 在草稿纸上画出图形，把已知条件标上去"
        elif "函数" in problem_content or "图像" in problem_content:
            return "🎯 画出函数图像，观察关键点（顶点、交点、对称轴）"
        elif "概率" in problem_content or "统计" in problem_content:
            return "🎯 列出所有可能的结果，用树状图或表格整理"
        
        return "🎯 把题目信息整理成表格或图表，一目了然"
    
    def _generate_practice_suggestion(
        self,
        attribution_result: ErrorAttributionResult,
    ) -> str:
        """生成练习建议.
        
        Args:
            attribution_result: 归因结果
            
        Returns:
            练习建议
        """
        if attribution_result.is_careless_pattern:
            return "建议：每天做5道基础题，目标是100%正确率，培养细心习惯"
        
        if attribution_result.knowledge_gaps:
            gap = attribution_result.knowledge_gaps[0]
            return f"建议：先复习'{gap}'相关的基础例题，再做3-5道变式练习"
        
        if attribution_result.historical_similarity > 0.5:
            return "建议：把之前的同类错题整理在一起，找出共同规律"
        
        return "建议：把这道题讲给同学或家长听，能讲清楚才算真懂"
    
    def _check_safety(self, content: ExplanationContent) -> float:
        """检查内容安全性.
        
        Args:
            content: 讲解内容
            
        Returns:
            安全性评分(1.0为完全安全)
        """
        all_text = " ".join([
            content.main_explanation,
            content.analogy,
            " ".join(content.step_hints),
            " ".join(content.key_points),
            content.visual_description,
            content.practice_suggestion,
        ])
        
        unsafe_count = 0
        for pattern in self.UNSAFE_PATTERNS:
            if re.search(pattern, all_text, re.IGNORECASE):
                unsafe_count += 1
                self.logger.warning("safety_issue_detected", pattern=pattern)
        
        if unsafe_count == 0:
            return 1.0
        
        # 有违规内容，降低评分
        return max(0.0, 1.0 - (unsafe_count * 0.3))
    
    def _check_age_appropriateness(self, content: ExplanationContent) -> bool:
        """检查是否适合目标年龄段(13-16岁).
        
        Args:
            content: 讲解内容
            
        Returns:
            是否适合
        """
        all_text = " ".join([
            content.main_explanation,
            content.analogy,
            " ".join(content.step_hints),
        ])
        
        # 检查是否有过于幼稚的表达
        childish_patterns = [
            r'小宝宝', r'小盆友', r'乖乖', r'萌萌哒',
            r'超\w+的', r'酱紫', r'神马',
        ]
        
        for pattern in childish_patterns:
            if re.search(pattern, all_text):
                self.logger.warning("age_inappropriate_detected", pattern=pattern)
                return False
        
        # 检查是否有过于复杂的表达（简单启发式）
        sentences = all_text.split("。")
        avg_length = sum(len(s) for s in sentences) / max(len(sentences), 1)
        
        if avg_length > 100:  # 平均句子过长
            self.logger.warning("content_too_complex", avg_length=avg_length)
            return False
        
        return True
    
    def _estimate_difficulty(self, content: ExplanationContent) -> str:
        """估计难度等级.
        
        Args:
            content: 讲解内容
            
        Returns:
            难度等级
        """
        # 基于内容长度和提示数量估计
        hint_count = len(content.step_hints)
        text_length = len(content.main_explanation)
        
        if hint_count <= 2 and text_length < 200:
            return "easy"
        elif hint_count >= 4 or text_length > 400:
            return "hard"
        
        return "medium"
    
    def _estimate_reading_time(self, content: ExplanationContent) -> int:
        """估算阅读时间.
        
        Args:
            content: 讲解内容
            
        Returns:
            预计阅读时间(秒)
        """
        # 假设13-16岁学生阅读速度约为200字/分钟
        chars_per_minute = 200
        
        total_chars = len(content.main_explanation)
        total_chars += len(content.analogy)
        total_chars += sum(len(h) for h in content.step_hints)
        total_chars += sum(len(k) for k in content.key_points)
        
        minutes = total_chars / chars_per_minute
        seconds = int(minutes * 60)
        
        return max(10, min(120, seconds))  # 10秒到2分钟之间
    
    def regenerate_with_adjustment(
        self,
        original_result: ExplanationResult,
        adjustment_type: str,
    ) -> ExplanationResult:
        """根据反馈调整重新生成讲解.
        
        Args:
            original_result: 原始结果
            adjustment_type: 调整类型(simplify/complex/add_example)
            
        Returns:
            调整后的结果
        """
        content = original_result.content
        
        if adjustment_type == "simplify":
            # 简化讲解
            content.main_explanation = content.main_explanation[:200] + "..."
            content.step_hints = content.step_hints[:2]
        elif adjustment_type == "complex":
            # 增加深度
            content.key_points.append("💡 进阶思考：这类问题还有其他解法吗？")
        elif adjustment_type == "add_example":
            # 添加例子
            content.analogy += "\n再举个例子：就像解密码锁，顺序对了才能打开。"
        
        # 重新计算阅读时间
        original_result.estimated_reading_time = self._estimate_reading_time(content)
        
        return original_result
