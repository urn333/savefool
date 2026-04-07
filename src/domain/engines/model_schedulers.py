"""模型调度器.

实现三个模型的调度器，分别负责不同的诊断任务。
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

from src.infrastructure.logging import get_logger
from src.infrastructure.models.base import Message, ModelClient, ModelResponse
from src.domain.models.arbitration import ModelResult
from src.domain.models.diagnosis import ErrorType

logger = get_logger(__name__)


@dataclass
class SchedulerConfig:
    """调度器配置.
    
    Attributes:
        model_id: 模型标识
        model_name: 模型名称
        temperature: 生成温度
        max_tokens: 最大token数
        timeout: 超时时间(秒)
        weight: 在仲裁中的权重
    """
    model_id: str
    model_name: str
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout: float = 10.0
    weight: float = 1.0


@dataclass
class ParsedProblem:
    """解析后的题目信息.
    
    Attributes:
        content: 题目文本内容
        student_answer: 学生答案
        subject: 学科类型
        problem_type: 题目类型
        knowledge_points: 知识点列表
    """
    content: str
    student_answer: Optional[str] = None
    subject: Optional[str] = None
    problem_type: Optional[str] = None
    knowledge_points: List[str] = field(default_factory=list)


class BaseModelScheduler(ABC):
    """模型调度器基类.
    
    所有模型调度器的抽象基类，定义统一的调用接口。
    """
    
    def __init__(
        self,
        client: ModelClient,
        config: SchedulerConfig,
    ):
        """初始化调度器.
        
        Args:
            client: 模型客户端
            config: 调度器配置
        """
        self.client = client
        self.config = config
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
    
    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """系统提示词."""
        pass
    
    @abstractmethod
    def build_prompt(
        self,
        problem: ParsedProblem,
        images: Optional[List[str]] = None,
    ) -> List[Message]:
        """构建提示消息.
        
        Args:
            problem: 解析后的题目
            images: 图片列表(base64)
            
        Returns:
            消息列表
        """
        pass
    
    @abstractmethod
    def parse_response(self, response: ModelResponse) -> Dict[str, Any]:
        """解析模型响应.
        
        Args:
            response: 模型响应
            
        Returns:
            结构化结果
        """
        pass
    
    async def schedule(
        self,
        problem: ParsedProblem,
        images: Optional[List[str]] = None,
    ) -> ModelResult:
        """执行调度.
        
        Args:
            problem: 解析后的题目
            images: 图片列表(base64)
            
        Returns:
            模型结果
        """
        start_time = time.time()
        self.logger.info(
            "scheduler_start",
            model_id=self.config.model_id,
            problem_content=problem.content[:100] if problem.content else "",
        )
        
        try:
            # 构建提示
            messages = self.build_prompt(problem, images)
            
            # 调用模型
            if images:
                response = await self.client.complete_with_vision(
                    messages=messages,
                    images=images,
                    model=self.config.model_name,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
            else:
                response = await self.client.complete(
                    messages=messages,
                    model=self.config.model_name,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
            
            # 解析响应
            parsed = self.parse_response(response)
            
            latency_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                "scheduler_success",
                model_id=self.config.model_id,
                latency_ms=latency_ms,
                confidence=parsed.get("confidence", 0.0),
            )
            
            return ModelResult(
                model_id=self.config.model_id,
                is_correct=parsed.get("is_correct", True),
                error_type=parsed.get("error_type"),
                concept_scores=parsed.get("concept_scores", {}),
                confidence=parsed.get("confidence", 0.0),
                diagnosis=parsed.get("diagnosis", {}),
                latency_ms=latency_ms,
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self.logger.error(
                "scheduler_error",
                model_id=self.config.model_id,
                latency_ms=latency_ms,
                error=str(e),
            )
            raise


class ModelAScheduler(BaseModelScheduler):
    """模型A调度器 - GPT-4通用模型.
    
    负责: 题目解构、考点分类(≤3条)
    """
    
    @property
    def system_prompt(self) -> str:
        return """你是一位专业的教育题目分析专家。你的任务是：
1. 分析题目类型（选择题、填空题、计算题、应用题等）
2. 提取核心考点（最多3条）
3. 判断学生答案是否正确
4. 如果错误，初步判断错误类型

请按以下JSON格式输出：
{
    "problem_type": "题目类型",
    "subject": "学科",
    "knowledge_points": ["考点1", "考点2", "考点3"],
    "is_correct": true/false,
    "error_type": "错误类型（如果错误）",
    "confidence": 0.0-1.0,
    "analysis": "简要分析"
}"""
    
    def build_prompt(
        self,
        problem: ParsedProblem,
        images: Optional[List[str]] = None,
    ) -> List[Message]:
        """构建提示消息."""
        content = f"""请分析以下题目：

题目内容：
{problem.content}

学生答案：{problem.student_answer or "未提供"}
{"学科：" + problem.subject if problem.subject else ""}

请按照系统提示的格式输出分析结果。"""
        
        return [
            Message.system(self.system_prompt),
            Message.user(content),
        ]
    
    def parse_response(self, response: ModelResponse) -> Dict[str, Any]:
        """解析模型响应."""
        import json
        import re
        
        content = response.content.strip()
        
        # 尝试提取JSON
        try:
            # 先尝试直接解析
            result = json.loads(content)
        except json.JSONDecodeError:
            # 尝试从代码块中提取
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    result = self._fallback_parse(content)
            else:
                # 尝试找花括号包裹的内容
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        result = self._fallback_parse(content)
                else:
                    result = self._fallback_parse(content)
        
        # 映射错误类型
        error_type_str = result.get("error_type", "")
        error_type = None
        if error_type_str and not result.get("is_correct", True):
            error_type = self._map_error_type(error_type_str)
        
        return {
            "is_correct": result.get("is_correct", True),
            "error_type": error_type,
            "confidence": result.get("confidence", 0.8),
            "diagnosis": {
                "problem_type": result.get("problem_type", "unknown"),
                "subject": result.get("subject", "math"),
                "knowledge_points": result.get("knowledge_points", [])[:3],  # 最多3条
                "analysis": result.get("analysis", ""),
            },
            "concept_scores": self._extract_concept_scores(
                result.get("knowledge_points", [])
            ),
        }
    
    def _fallback_parse(self, content: str) -> Dict[str, Any]:
        """降级解析."""
        return {
            "problem_type": "unknown",
            "subject": "math",
            "knowledge_points": [],
            "is_correct": True,
            "confidence": 0.5,
            "analysis": content[:500],
        }
    
    def _map_error_type(self, error_str: str) -> Optional[ErrorType]:
        """映射错误类型."""
        error_map = {
            "概念": ErrorType.CONCEPT_MISUNDERSTANDING,
            "计算": ErrorType.CALCULATION_ERROR,
            "逻辑": ErrorType.LOGICAL_FLAW,
            "粗心": ErrorType.CARELESS_MISTAKE,
            "知识": ErrorType.KNOWLEDGE_GAP,
        }
        error_lower = error_str.lower()
        for key, value in error_map.items():
            if key in error_lower:
                return value
        return ErrorType.KNOWLEDGE_GAP
    
    def _extract_concept_scores(self, knowledge_points: List[str]) -> Dict[str, float]:
        """提取概念评分."""
        return {
            f"concept_{i}": 1.0 if i < 2 else 0.8
            for i, kp in enumerate(knowledge_points[:3])
        }


class ModelBScheduler(BaseModelScheduler):
    """模型B调度器 - DeepSeek-Math.
    
    负责: 逻辑推演、步骤验证
    """
    
    @property
    def system_prompt(self) -> str:
        return """你是一位数学逻辑分析专家。你的任务是：
1. 逐步分析解题过程
2. 验证每一步的正确性
3. 定位第一个错误步骤（如果有）
4. 评估整体逻辑严密性

请按以下JSON格式输出：
{
    "steps": [
        {"step": 1, "content": "步骤内容", "is_correct": true/false}
    ],
    "first_error_step": 错误步骤编号（如果没有则为null）,
    "is_correct": true/false,
    "logic_score": 0.0-1.0,
    "confidence": 0.0-1.0,
    "error_analysis": "错误分析（如果有）"
}"""
    
    def build_prompt(
        self,
        problem: ParsedProblem,
        images: Optional[List[str]] = None,
    ) -> List[Message]:
        """构建提示消息."""
        content = f"""请分析以下题目的解题逻辑：

题目内容：
{problem.content}

学生答案：{problem.student_answer or "未提供"}

请逐步分析解题过程，验证每一步的正确性。"""
        
        return [
            Message.system(self.system_prompt),
            Message.user(content),
        ]
    
    def parse_response(self, response: ModelResponse) -> Dict[str, Any]:
        """解析模型响应."""
        import json
        import re
        
        content = response.content.strip()
        
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    result = self._fallback_parse(content)
            else:
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        result = self._fallback_parse(content)
                else:
                    result = self._fallback_parse(content)
        
        # 确定是否错误
        is_correct = result.get("is_correct", True)
        first_error_step = result.get("first_error_step")
        
        # 如果有错误步骤，则整体错误
        if first_error_step is not None and first_error_step > 0:
            is_correct = False
        
        # 构建诊断信息
        diagnosis = {
            "steps": result.get("steps", []),
            "logic_score": result.get("logic_score", 0.8),
            "error_analysis": result.get("error_analysis", ""),
        }
        
        if first_error_step:
            diagnosis["first_error_step"] = first_error_step
        
        # 推断错误类型
        error_type = None
        if not is_correct:
            error_analysis = result.get("error_analysis", "").lower()
            if "计算" in error_analysis or "算" in error_analysis:
                error_type = ErrorType.CALCULATION_ERROR
            elif "逻辑" in error_analysis or "推理" in error_analysis:
                error_type = ErrorType.LOGICAL_FLAW
            else:
                error_type = ErrorType.LOGICAL_FLAW
        
        return {
            "is_correct": is_correct,
            "error_type": error_type,
            "confidence": result.get("confidence", 0.8),
            "diagnosis": diagnosis,
            "concept_scores": {"logic": result.get("logic_score", 0.8)},
        }
    
    def _fallback_parse(self, content: str) -> Dict[str, Any]:
        """降级解析."""
        return {
            "steps": [],
            "first_error_step": None,
            "is_correct": True,
            "logic_score": 0.7,
            "confidence": 0.6,
            "error_analysis": content[:500],
        }


class ModelCScheduler(BaseModelScheduler):
    """模型C调度器 - Llama-3-70B.
    
    负责: 概念映射、归因交叉验证
    """
    
    @property
    def system_prompt(self) -> str:
        return """你是一位教育心理学和概念分析专家。你的任务是：
1. 建立题目涉及的概念映射关系
2. 分析错误的根本原因
3. 验证归因的合理性
4. 识别潜在的概念缺口

请按以下JSON格式输出：
{
    "concept_map": {
        "核心概念": ["相关子概念1", "相关子概念2"]
    },
    "root_cause": "根本原因分析",
    "attribution_valid": true/false,
    "concept_gaps": ["概念缺口1", "概念缺口2"],
    "is_correct": true/false,
    "confidence": 0.0-1.0,
    "cross_validation": "交叉验证说明"
}"""
    
    def build_prompt(
        self,
        problem: ParsedProblem,
        images: Optional[List[str]] = None,
        intermediate_results: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Message]:
        """构建提示消息.
        
        Args:
            problem: 解析后的题目
            images: 图片列表
            intermediate_results: 其他模型的中间结果(用于交叉验证)
        """
        content = f"""请分析以下题目的概念映射和错误归因：

题目内容：
{problem.content}

学生答案：{problem.student_answer or "未提供"}
"""
        
        # 添加其他模型的中间结果
        if intermediate_results:
            content += "\n其他模型的初步分析结果：\n"
            for i, result in enumerate(intermediate_results):
                content += f"\n模型{i+1}分析：{str(result)[:200]}\n"
        
        content += "\n请进行概念映射和归因交叉验证。"
        
        return [
            Message.system(self.system_prompt),
            Message.user(content),
        ]
    
    def parse_response(self, response: ModelResponse) -> Dict[str, Any]:
        """解析模型响应."""
        import json
        import re
        
        content = response.content.strip()
        
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    result = self._fallback_parse(content)
            else:
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        result = self._fallback_parse(content)
                else:
                    result = self._fallback_parse(content)
        
        # 推断错误类型
        error_type = None
        is_correct = result.get("is_correct", True)
        
        if not is_correct:
            root_cause = result.get("root_cause", "").lower()
            if "概念" in root_cause:
                error_type = ErrorType.CONCEPT_MISUNDERSTANDING
            elif "知识" in root_cause:
                error_type = ErrorType.KNOWLEDGE_GAP
            elif "粗心" in root_cause or "仔细" in root_cause:
                error_type = ErrorType.CARELESS_MISTAKE
            else:
                error_type = ErrorType.KNOWLEDGE_GAP
        
        concept_gaps = result.get("concept_gaps", [])
        
        return {
            "is_correct": is_correct,
            "error_type": error_type,
            "confidence": result.get("confidence", 0.7),
            "diagnosis": {
                "concept_map": result.get("concept_map", {}),
                "root_cause": result.get("root_cause", ""),
                "attribution_valid": result.get("attribution_valid", True),
                "cross_validation": result.get("cross_validation", ""),
            },
            "concept_scores": {
                f"gap_{i}": 0.5 for i in range(len(concept_gaps))
            } if concept_gaps else {},
        }
    
    def _fallback_parse(self, content: str) -> Dict[str, Any]:
        """降级解析."""
        return {
            "concept_map": {},
            "root_cause": content[:500],
            "attribution_valid": True,
            "concept_gaps": [],
            "is_correct": True,
            "confidence": 0.5,
            "cross_validation": "解析失败",
        }
