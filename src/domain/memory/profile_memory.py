"""Profile记忆层实现.

长期认知画像管理：
- 思维风格 (thinking_style)
- 错误DNA (error_dna)
- ZPD边界 (zone_of_proximal_development)
- 认知特征向量

功能追溯ID: F-MEM-001
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from pydantic import Field

from src.domain.models.base import DomainModel, generate_id, now_timestamp
from src.domain.models.diagnosis import ErrorType
from src.domain.models.memory import (
    CognitiveLevel,
    ConceptStrength,
    LearningStyle,
    MistakePattern,
)
from src.infrastructure.db.enums import GapStatus
from src.infrastructure.db.student import CognitiveProfile
from src.infrastructure.storage.repositories import (
    CognitiveGapRepository,
    CognitiveProfileRepository,
)


class ThinkingStyle(DomainModel):
    """思维风格特征.
    
    描述学生的思维偏好和认知模式。
    """
    
    analytical: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="分析型思维倾向",
    )
    intuitive: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="直觉型思维倾向",
    )
    systematic: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="系统性思维倾向",
    )
    creative: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="创造性思维倾向",
    )
    detail_oriented: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="细节导向程度",
    )
    
    def get_dominant_style(self) -> str:
        """获取主导思维风格.
        
        Returns:
            主导思维风格名称
        """
        styles = {
            "analytical": self.analytical,
            "intuitive": self.intuitive,
            "systematic": self.systematic,
            "creative": self.creative,
        }
        return max(styles.items(), key=lambda x: x[1])[0]


class ErrorDNA(DomainModel):
    """错误DNA模式.
    
    学生的错误特征指纹，用于识别重复错误模式。
    """
    
    error_patterns: List[MistakePattern] = Field(
        default_factory=list,
        description="错误模式列表",
    )
    recurring_errors: Dict[str, int] = Field(
        default_factory=dict,
        description="重复错误计数",
    )
    error_triggers: List[str] = Field(
        default_factory=list,
        description="常见错误触发因素",
    )
    last_analysis: datetime = Field(
        default_factory=now_timestamp,
        description="最后分析时间",
    )
    
    def add_pattern(self, pattern: MistakePattern) -> None:
        """添加错误模式.
        
        Args:
            pattern: 错误模式
        """
        # 检查是否已有类似模式
        for existing in self.error_patterns:
            if existing.error_type == pattern.error_type:
                existing.occurrence_count += pattern.occurrence_count
                existing.last_occurred_at = pattern.last_occurred_at
                self.recurring_errors[pattern.error_type.value] = \
                    self.recurring_errors.get(pattern.error_type.value, 0) + 1
                return
        
        self.error_patterns.append(pattern)
        self.recurring_errors[pattern.error_type.value] = 1
    
    def get_top_patterns(self, n: int = 3) -> List[MistakePattern]:
        """获取最常见的错误模式.
        
        Args:
            n: 返回数量
            
        Returns:
            最常见的n个错误模式
        """
        sorted_patterns = sorted(
            self.error_patterns,
            key=lambda p: p.occurrence_count,
            reverse=True
        )
        return sorted_patterns[:n]


class ZPDBoundary(DomainModel):
    """最近发展区(ZPD)边界.
    
    学生独立解决和需要协助的能力边界。
    """
    
    independent_level: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="独立解决能力水平",
    )
    assisted_level: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="协助下的能力水平",
    )
    challenge_zone: Tuple[float, float] = Field(
        default=(0.6, 0.8),
        description="挑战区域(下限,上限)",
    )
    optimal_difficulty: int = Field(
        default=5,
        ge=1,
        le=10,
        description="最优难度等级",
    )
    
    def is_in_zpd(self, difficulty: float) -> bool:
        """检查难度是否在ZPD内.
        
        Args:
            difficulty: 难度值(0-1)
            
        Returns:
            是否在ZPD内
        """
        return self.challenge_zone[0] <= difficulty <= self.challenge_zone[1]
    
    def update_boundary(self, success_rate: float) -> None:
        """根据成功率更新ZPD边界.
        
        Args:
            success_rate: 最近成功率
        """
        if success_rate > 0.8:
            # 提高难度
            self.independent_level = min(0.9, self.independent_level + 0.05)
            self.assisted_level = min(1.0, self.assisted_level + 0.05)
        elif success_rate < 0.5:
            # 降低难度
            self.independent_level = max(0.3, self.independent_level - 0.05)
            self.assisted_level = max(0.5, self.assisted_level - 0.05)
        
        self.challenge_zone = (self.independent_level, self.assisted_level)


class CognitiveFeatureVector(DomainModel):
    """认知特征向量.
    
    用于机器学习的多维认知特征表示。
    """
    
    dimensions: Dict[str, float] = Field(
        default_factory=dict,
        description="特征维度",
    )
    version: int = Field(
        default=1,
        ge=1,
        description="向量版本",
    )
    updated_at: datetime = Field(
        default_factory=now_timestamp,
        description="更新时间",
    )
    
    def __init__(self, **data):
        super().__init__(**data)
        if not self.dimensions:
            # 初始化默认维度
            self.dimensions = {
                "processing_speed": 0.5,
                "working_memory": 0.5,
                "pattern_recognition": 0.5,
                "abstract_thinking": 0.5,
                "attention_control": 0.5,
                "cognitive_flexibility": 0.5,
            }
    
    def cosine_similarity(self, other: "CognitiveFeatureVector") -> float:
        """计算与另一个特征向量的余弦相似度.
        
        Args:
            other: 另一个特征向量
            
        Returns:
            余弦相似度(-1到1)
        """
        common_dims = set(self.dimensions.keys()) & set(other.dimensions.keys())
        if not common_dims:
            return 0.0
        
        dot_product = sum(
            self.dimensions[d] * other.dimensions[d] for d in common_dims
        )
        norm_self = sum(self.dimensions[d] ** 2 for d in common_dims) ** 0.5
        norm_other = sum(other.dimensions[d] ** 2 for d in common_dims) ** 0.5
        
        if norm_self == 0 or norm_other == 0:
            return 0.0
        
        return dot_product / (norm_self * norm_other)


class StudentCognitiveProfile(DomainModel):
    """学生认知画像.
    
    Profile层记忆的完整表示。
    """
    
    student_id: str = Field(..., description="学生ID")
    version: int = Field(default=1, ge=1, description="版本号")
    
    # 核心认知特征
    thinking_style: ThinkingStyle = Field(
        default_factory=ThinkingStyle,
        description="思维风格",
    )
    error_dna: ErrorDNA = Field(
        default_factory=ErrorDNA,
        description="错误DNA",
    )
    zpd_boundary: ZPDBoundary = Field(
        default_factory=ZPDBoundary,
        description="ZPD边界",
    )
    cognitive_features: CognitiveFeatureVector = Field(
        default_factory=CognitiveFeatureVector,
        description="认知特征向量",
    )
    
    # 辅助特征
    learning_style: LearningStyle = Field(
        default_factory=LearningStyle,
        description="学习风格",
    )
    cognitive_level: CognitiveLevel = Field(
        default_factory=CognitiveLevel,
        description="认知水平",
    )
    
    # 元数据
    weak_concepts: List[ConceptStrength] = Field(
        default_factory=list,
        description="薄弱概念",
    )
    strong_concepts: List[ConceptStrength] = Field(
        default_factory=list,
        description="强势概念",
    )
    last_updated: datetime = Field(
        default_factory=now_timestamp,
        description="最后更新时间",
    )
    crystallized_at: Optional[datetime] = Field(
        None,
        description="固化时间(≥30天)",
    )
    
    def update_from_episodes(self, episodes_data: List[Dict[str, Any]]) -> None:
        """从学习事件更新画像.
        
        Args:
            episodes_data: 学习事件数据列表
        """
        if not episodes_data:
            return
        
        # 更新思维风格(简化算法)
        success_rate = sum(
            1 for ep in episodes_data if ep.get("is_correct", False)
        ) / len(episodes_data)
        
        if success_rate > 0.7:
            self.thinking_style.systematic = min(
                1.0, self.thinking_style.systematic + 0.05
            )
        
        # 更新ZPD边界
        self.zpd_boundary.update_boundary(success_rate)
        
        # 更新认知特征向量
        for ep in episodes_data:
            if ep.get("time_spent", 0) > 0:
                speed = 1.0 / max(1, ep["time_spent"] / 60)  # 每分钟
                self.cognitive_features.dimensions["processing_speed"] = (
                    self.cognitive_features.dimensions.get("processing_speed", 0.5)
                    * 0.9 + speed * 0.1
                )
        
        self.last_updated = now_timestamp()
        self.version += 1
    
    def should_crystallize(self) -> bool:
        """检查是否应该固化(≥30天).
        
        Returns:
            是否应该固化
        """
        if self.crystallized_at:
            return False
        
        days_since_update = (now_timestamp() - self.last_updated).days
        return days_since_update >= 30
    
    def to_db_model(self) -> CognitiveProfile:
        """转换为数据库模型.
        
        Returns:
            数据库模型实例
        """
        return CognitiveProfile(
            profile_id=generate_id("profile"),
            student_id=self.student_id,
            thinking_style=self.thinking_style.to_dict(),
            error_dna=self.error_dna.to_dict(),
            zpd_boundary=self.zpd_boundary.to_dict(),
            cognitive_features=self.cognitive_features.to_dict(),
            crystallized_at=self.crystallized_at,
        )


class ProfileMemory:
    """Profile记忆层管理器.
    
    管理学生长期认知画像的存取和更新。
    """
    
    def __init__(
        self,
        profile_repo: CognitiveProfileRepository,
        gap_repo: CognitiveGapRepository,
    ):
        """初始化Profile记忆层.
        
        Args:
            profile_repo: 认知画像Repository
            gap_repo: 认知缺口Repository
        """
        self._profile_repo = profile_repo
        self._gap_repo = gap_repo
    
    async def get_profile(
        self,
        student_id: str,
    ) -> Optional[StudentCognitiveProfile]:
        """获取学生认知画像.
        
        Args:
            student_id: 学生ID
            
        Returns:
            学生认知画像，不存在返回None
        """
        db_profile = await self._profile_repo.find_one(student_id=student_id)
        if not db_profile:
            return None
        
        return self._from_db_model(db_profile)
    
    async def create_profile(
        self,
        student_id: str,
    ) -> StudentCognitiveProfile:
        """创建新的认知画像.
        
        Args:
            student_id: 学生ID
            
        Returns:
            新创建的认知画像
        """
        profile = StudentCognitiveProfile(student_id=student_id)
        db_model = profile.to_db_model()
        await self._profile_repo.create(db_model)
        return profile
    
    async def update_profile(
        self,
        profile: StudentCognitiveProfile,
    ) -> StudentCognitiveProfile:
        """更新认知画像.
        
        Args:
            profile: 要更新的画像
            
        Returns:
            更新后的画像
        """
        db_profile = await self._profile_repo.find_one(
            student_id=profile.student_id
        )
        if db_profile:
            db_profile.thinking_style = profile.thinking_style.to_dict()
            db_profile.error_dna = profile.error_dna.to_dict()
            db_profile.zpd_boundary = profile.zpd_boundary.to_dict()
            db_profile.cognitive_features = profile.cognitive_features.to_dict()
            db_profile.crystallized_at = profile.crystallized_at
            await self._profile_repo.update(db_profile)
        
        return profile
    
    async def crystallize_profile(
        self,
        student_id: str,
    ) -> Optional[StudentCognitiveProfile]:
        """固化学生认知画像.
        
        Args:
            student_id: 学生ID
            
        Returns:
            固化后的画像，不存在返回None
        """
        profile = await self.get_profile(student_id)
        if not profile or not profile.should_crystallize():
            return profile
        
        profile.crystallized_at = now_timestamp()
        return await self.update_profile(profile)
    
    async def update_error_dna(
        self,
        student_id: str,
        error_type: ErrorType,
        related_concepts: List[str],
    ) -> Optional[StudentCognitiveProfile]:
        """更新错误DNA.
        
        Args:
            student_id: 学生ID
            error_type: 错误类型
            related_concepts: 相关概念
            
        Returns:
            更新后的画像
        """
        profile = await self.get_profile(student_id)
        if not profile:
            profile = await self.create_profile(student_id)
        
        pattern = MistakePattern(
            error_type=error_type,
            related_concepts=related_concepts,
        )
        profile.error_dna.add_pattern(pattern)
        profile.last_updated = now_timestamp()
        
        return await self.update_profile(profile)
    
    def _from_db_model(
        self,
        db_model: CognitiveProfile,
    ) -> StudentCognitiveProfile:
        """从数据库模型创建领域模型.
        
        Args:
            db_model: 数据库模型
            
        Returns:
            领域模型
        """
        return StudentCognitiveProfile(
            student_id=db_model.student_id,
            thinking_style=ThinkingStyle(**(db_model.thinking_style or {})),
            error_dna=ErrorDNA(**(db_model.error_dna or {})),
            zpd_boundary=ZPDBoundary(**(db_model.zpd_boundary or {})),
            cognitive_features=CognitiveFeatureVector(
                **(db_model.cognitive_features or {})
            ),
            crystallized_at=db_model.crystallized_at,
            last_updated=db_model.updated_at,
        )
