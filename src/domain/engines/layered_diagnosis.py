"""分层诊断选项生成引擎.

功能追溯ID: F-LAYER-001, F-LAYER-002, F-LAYER-003
实现3选项分层选择诊断：
- 第一层假设生成（历史模式/知识缺口/情境因素）
- 第二层深挖选项
- 诊断路径记录
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.infrastructure.logging import get_logger
from src.domain.models.diagnosis import ErrorType
from src.domain.engines.error_attribution import ErrorAttributionResult
from src.domain.memory.memory_manager import MemoryManager
from src.domain.models.base import generate_id, now_timestamp

logger = get_logger(__name__)


class LayerOptionType(str, Enum):
    """选项类型."""
    HISTORICAL = "historical"      # 历史模式
    KNOWLEDGE = "knowledge"        # 知识缺口
    SITUATIONAL = "situational"    # 情境因素
    METHOD = "method"              # 方法问题
    CONCEPT = "concept"            # 概念问题
    CARELESS = "careless"          # 粗心问题


@dataclass
class LayerOption:
    """分层诊断选项.
    
    Attributes:
        option_id: 选项ID
        type: 选项类型
        title: 标题
        description: 描述
        icon: 图标
        confidence: 置信度
        sub_options: 子选项（第二层）
        knowledge_tags: 关联知识点标签
        related_factors: 相关归因因子
    """
    option_id: str
    type: LayerOptionType
    title: str
    description: str
    icon: str
    confidence: float
    sub_options: List['LayerOption'] = field(default_factory=list)
    knowledge_tags: List[str] = field(default_factory=list)
    related_factors: List[str] = field(default_factory=list)


@dataclass
class DiagnosisPath:
    """诊断路径.
    
    Attributes:
        path_id: 路径ID
        student_id: 学生ID
        problem_id: 题目ID
        selections: 选择序列
        start_time: 开始时间
        end_time: 结束时间
        final_diagnosis: 最终诊断
    """
    path_id: str
    student_id: str
    problem_id: str
    selections: List[Dict[str, Any]] = field(default_factory=list)
    start_time: datetime = field(default_factory=now_timestamp)
    end_time: Optional[datetime] = None
    final_diagnosis: Optional[str] = None
    
    def add_selection(
        self,
        layer: int,
        option_id: str,
        option_type: str,
    ) -> None:
        """添加选择.
        
        Args:
            layer: 层级(1或2)
            option_id: 选项ID
            option_type: 选项类型
        """
        self.selections.append({
            "layer": layer,
            "option_id": option_id,
            "option_type": option_type,
            "timestamp": now_timestamp().isoformat(),
        })
    
    def complete(self, final_diagnosis: str) -> None:
        """完成路径.
        
        Args:
            final_diagnosis: 最终诊断
        """
        self.end_time = now_timestamp()
        self.final_diagnosis = final_diagnosis
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "path_id": self.path_id,
            "student_id": self.student_id,
            "problem_id": self.problem_id,
            "selections": self.selections,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "final_diagnosis": self.final_diagnosis,
        }


class LayeredDiagnosisEngine:
    """分层诊断引擎.
    
    实现3选项分层选择诊断：
    1. 第一层假设（历史模式/知识缺口/情境因素）
    2. 第二层深挖（2-3个子选项）
    3. 选项展示与交互
    4. 诊断路径记录
    
    Example:
        >>> engine = LayeredDiagnosisEngine(memory_manager)
        >>> # 第一层
        >>> options = await engine.generate_first_layer(attribution_result)
        >>> # 用户选择后，生成第二层
        >>> sub_options = await engine.generate_second_layer(
        ...     student_id="stu_123",
        ...     problem_id="prob_456",
        ...     first_selection="option_1",
        ...     attribution_result=attribution_result,
        ... )
    """
    
    # 第一层选项模板
    FIRST_LAYER_TEMPLATES = [
        {
            "type": LayerOptionType.HISTORICAL,
            "title": "历史错误模式",
            "description": "这道题的错误与你之前的某些错误类似",
            "icon": "🔄",
            "base_confidence": 0.3,
        },
        {
            "type": LayerOptionType.KNOWLEDGE,
            "title": "知识掌握问题",
            "description": "相关知识点可能还没有完全掌握",
            "icon": "📚",
            "base_confidence": 0.35,
        },
        {
            "type": LayerOptionType.SITUATIONAL,
            "title": "情境因素影响",
            "description": "可能是状态、时间或环境因素的影响",
            "icon": "⏰",
            "base_confidence": 0.2,
        },
    ]
    
    # 第二层子选项模板
    SECOND_LAYER_TEMPLATES = {
        LayerOptionType.HISTORICAL: [
            {
                "type": LayerOptionType.HISTORICAL,
                "title": "同类题型易错",
                "description": "这种题型之前也错过，需要总结规律",
                "icon": "📝",
            },
            {
                "type": LayerOptionType.HISTORICAL,
                "title": "相同知识点错误",
                "description": "涉及的知识点之前掌握不牢",
                "icon": "🎯",
            },
            {
                "type": LayerOptionType.HISTORICAL,
                "title": "习惯性失误",
                "description": "总是在类似的步骤上出错",
                "icon": "⚠️",
            },
        ],
        LayerOptionType.KNOWLEDGE: [
            {
                "type": LayerOptionType.CONCEPT,
                "title": "概念理解不清",
                "description": "对核心概念的理解有偏差",
                "icon": "💡",
            },
            {
                "type": LayerOptionType.METHOD,
                "title": "方法应用不熟练",
                "description": "知道方法但用起来不熟练",
                "icon": "🔧",
            },
            {
                "type": LayerOptionType.KNOWLEDGE,
                "title": "前置知识缺失",
                "description": "需要的前置知识点没掌握好",
                "icon": "🏗️",
            },
        ],
        LayerOptionType.SITUATIONAL: [
            {
                "type": LayerOptionType.CARELESS,
                "title": "粗心大意",
                "description": "当时可能走神了或看漏了条件",
                "icon": "👀",
            },
            {
                "type": LayerOptionType.SITUATIONAL,
                "title": "时间压力",
                "description": "可能赶时间导致思考不充分",
                "icon": "⏱️",
            },
            {
                "type": LayerOptionType.SITUATIONAL,
                "title": "状态不佳",
                "description": "当时可能疲劳或注意力不集中",
                "icon": "😴",
            },
        ],
    }
    
    def __init__(self, memory_manager: MemoryManager):
        """初始化分层诊断引擎.
        
        Args:
            memory_manager: 记忆管理器
        """
        self.memory_manager = memory_manager
        self.logger = get_logger(__name__)
        self._active_paths: Dict[str, DiagnosisPath] = {}
    
    async def generate_first_layer(
        self,
        attribution_result: ErrorAttributionResult,
    ) -> List[LayerOption]:
        """生成第一层选项.
        
        基于归因结果生成3个第一层假设选项。
        
        Args:
            attribution_result: 归因分析结果
            
        Returns:
            3个选项列表
        """
        self.logger.info(
            "generate_first_layer",
            student_id=attribution_result.student_id,
            problem_id=attribution_result.problem_id,
        )
        
        options = []
        
        # 根据归因结果调整各选项置信度
        for template in self.FIRST_LAYER_TEMPLATES:
            confidence = template["base_confidence"]
            
            # 基于归因调整置信度
            if template["type"] == LayerOptionType.HISTORICAL:
                if attribution_result.historical_similarity > 0:
                    confidence += attribution_result.historical_similarity * 0.3
            
            elif template["type"] == LayerOptionType.KNOWLEDGE:
                if attribution_result.knowledge_gaps:
                    confidence += min(0.3, len(attribution_result.knowledge_gaps) * 0.1)
            
            elif template["type"] == LayerOptionType.SITUATIONAL:
                if attribution_result.is_careless_pattern:
                    confidence += 0.2
            
            option = LayerOption(
                option_id=generate_id("opt"),
                type=template["type"],
                title=template["title"],
                description=template["description"],
                icon=template["icon"],
                confidence=min(1.0, confidence),
                related_factors=[f.factor_type for f in attribution_result.factors],
            )
            
            options.append(option)
        
        # 按置信度排序
        options.sort(key=lambda o: o.confidence, reverse=True)
        
        # 确保返回3个选项
        return options[:3]
    
    async def generate_second_layer(
        self,
        student_id: str,
        problem_id: str,
        first_selection: str,
        attribution_result: ErrorAttributionResult,
        first_layer_options: Optional[List[LayerOption]] = None,
    ) -> List[LayerOption]:
        """生成第二层深挖选项.
        
        根据第一层选择展开2-3个子选项。
        
        Args:
            student_id: 学生ID
            problem_id: 题目ID
            first_selection: 第一层选择的选项ID
            attribution_result: 归因结果
            first_layer_options: 第一层选项（用于查找类型）
            
        Returns:
            2-3个子选项
        """
        self.logger.info(
            "generate_second_layer",
            student_id=student_id,
            problem_id=problem_id,
            first_selection=first_selection,
        )
        
        # 查找第一层选项类型
        selected_type = LayerOptionType.KNOWLEDGE  # 默认
        
        if first_layer_options:
            for opt in first_layer_options:
                if opt.option_id == first_selection:
                    selected_type = opt.type
                    break
        else:
            # 基于归因推断
            if attribution_result.is_careless_pattern:
                selected_type = LayerOptionType.SITUATIONAL
            elif attribution_result.historical_similarity > 0.3:
                selected_type = LayerOptionType.HISTORICAL
        
        # 生成子选项
        templates = self.SECOND_LAYER_TEMPLATES.get(selected_type, [])
        
        sub_options = []
        for template in templates[:3]:  # 最多3个
            confidence = 0.6
            
            # 基于归因调整
            if template["type"] == LayerOptionType.CARELESS:
                if attribution_result.is_careless_pattern:
                    confidence = 0.85
            elif template["type"] == LayerOptionType.CONCEPT:
                if attribution_result.error_type == ErrorType.CONCEPT_MISUNDERSTANDING:
                    confidence = 0.8
            
            option = LayerOption(
                option_id=generate_id("opt"),
                type=template["type"],
                title=template["title"],
                description=template["description"],
                icon=template["icon"],
                confidence=confidence,
                knowledge_tags=attribution_result.knowledge_gaps[:2],
            )
            
            sub_options.append(option)
        
        # 确保至少2个，最多3个
        return sub_options[:3] if len(sub_options) >= 2 else sub_options + [
            LayerOption(
                option_id=generate_id("opt"),
                type=LayerOptionType.KNOWLEDGE,
                title="其他原因",
                description="可能是其他复杂因素导致的",
                icon="❓",
                confidence=0.4,
            )
        ]
    
    def start_diagnosis_path(
        self,
        student_id: str,
        problem_id: str,
    ) -> DiagnosisPath:
        """开始诊断路径.
        
        Args:
            student_id: 学生ID
            problem_id: 题目ID
            
        Returns:
            诊断路径对象
        """
        path = DiagnosisPath(
            path_id=generate_id("path"),
            student_id=student_id,
            problem_id=problem_id,
        )
        
        self._active_paths[path.path_id] = path
        
        self.logger.info(
            "diagnosis_path_started",
            path_id=path.path_id,
            student_id=student_id,
            problem_id=problem_id,
        )
        
        return path
    
    def record_first_selection(
        self,
        path_id: str,
        option_id: str,
        option_type: str,
    ) -> Optional[DiagnosisPath]:
        """记录第一层选择.
        
        Args:
            path_id: 路径ID
            option_id: 选项ID
            option_type: 选项类型
            
        Returns:
            更新后的路径，不存在返回None
        """
        path = self._active_paths.get(path_id)
        if not path:
            self.logger.warning("path_not_found", path_id=path_id)
            return None
        
        path.add_selection(layer=1, option_id=option_id, option_type=option_type)
        
        self.logger.info(
            "first_selection_recorded",
            path_id=path_id,
            option_id=option_id,
            option_type=option_type,
        )
        
        return path
    
    def record_second_selection(
        self,
        path_id: str,
        option_id: str,
        option_type: str,
        final_diagnosis: str,
    ) -> Optional[DiagnosisPath]:
        """记录第二层选择并完成路径.
        
        Args:
            path_id: 路径ID
            option_id: 选项ID
            option_type: 选项类型
            final_diagnosis: 最终诊断
            
        Returns:
            完成的路径，不存在返回None
        """
        path = self._active_paths.get(path_id)
        if not path:
            self.logger.warning("path_not_found", path_id=path_id)
            return None
        
        path.add_selection(layer=2, option_id=option_id, option_type=option_type)
        path.complete(final_diagnosis)
        
        self.logger.info(
            "second_selection_recorded",
            path_id=path_id,
            option_id=option_id,
            final_diagnosis=final_diagnosis,
        )
        
        return path
    
    async def finalize_diagnosis(
        self,
        path_id: str,
        attribution_result: ErrorAttributionResult,
    ) -> Optional[Dict[str, Any]]:
        """完成诊断并生成最终结果.
        
        Args:
            path_id: 路径ID
            attribution_result: 归因结果
            
        Returns:
            最终诊断结果
        """
        path = self._active_paths.get(path_id)
        if not path:
            return None
        
        # 构建最终诊断
        final_diagnosis = self._build_final_diagnosis(path, attribution_result)
        
        # 从活跃路径中移除
        del self._active_paths[path_id]
        
        return {
            "path": path.to_dict(),
            "final_diagnosis": final_diagnosis,
            "confirmed_factors": self._extract_confirmed_factors(path, attribution_result),
        }
    
    def _build_final_diagnosis(
        self,
        path: DiagnosisPath,
        attribution_result: ErrorAttributionResult,
    ) -> str:
        """构建最终诊断.
        
        Args:
            path: 诊断路径
            attribution_result: 归因结果
            
        Returns:
            最终诊断文本
        """
        if not path.selections:
            return attribution_result.primary_cause
        
        # 获取第二层选择
        second_selection = None
        for sel in path.selections:
            if sel["layer"] == 2:
                second_selection = sel
                break
        
        if second_selection:
            option_type = second_selection["option_type"]
            
            diagnosis_map = {
                "careless": "粗心导致的失误",
                "method": "方法应用不熟练",
                "concept": "概念理解有偏差",
                "historical": "同类错误的重复",
                "knowledge": "知识点掌握不牢",
                "situational": "受情境因素影响",
            }
            
            return diagnosis_map.get(option_type, attribution_result.primary_cause)
        
        return attribution_result.primary_cause
    
    def _extract_confirmed_factors(
        self,
        path: DiagnosisPath,
        attribution_result: ErrorAttributionResult,
    ) -> List[str]:
        """提取确认的因素.
        
        Args:
            path: 诊断路径
            attribution_result: 归因结果
            
        Returns:
            因素列表
        """
        confirmed = []
        
        for sel in path.selections:
            option_type = sel.get("option_type", "")
            if option_type in ["careless", "historical"]:
                confirmed.append(option_type)
        
        return confirmed
    
    def get_option_recommendations(
        self,
        option_type: LayerOptionType,
        knowledge_gaps: List[str],
    ) -> List[str]:
        """获取选项对应的学习建议.
        
        Args:
            option_type: 选项类型
            knowledge_gaps: 知识缺口
            
        Returns:
            建议列表
        """
        recommendations = {
            LayerOptionType.HISTORICAL: [
                "建立这类题型的错题档案",
                "定期回顾同类错题，找出规律",
                "总结这类题型的解题模板",
            ],
            LayerOptionType.KNOWLEDGE: [
                f"重点复习：{', '.join(knowledge_gaps[:2])}" if knowledge_gaps else "系统复习相关知识",
                "做基础巩固练习",
                "建立知识点思维导图",
            ],
            LayerOptionType.SITUATIONAL: [
                "调整学习状态和时间安排",
                "做题时保持专注",
                "养成检查的好习惯",
            ],
            LayerOptionType.METHOD: [
                "多做变式练习巩固方法",
                "总结解题步骤和注意事项",
                "尝试用方法解决不同类型题目",
            ],
            LayerOptionType.CONCEPT: [
                "重新理解核心概念的定义",
                "通过例子加深概念理解",
                "对比易混淆的概念",
            ],
            LayerOptionType.CARELESS: [
                "培养仔细审题的习惯",
                "做完后反向验算",
                "标记关键条件避免遗漏",
            ],
        }
        
        return recommendations.get(option_type, ["继续观察，积累更多数据"])
