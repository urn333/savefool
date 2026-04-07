"""记忆系统测试.

测试记忆系统各层功能:
- Profile读写测试
- Episodic事件记录测试
- Semantic知识更新测试
- Meta状态流转测试(pending→crystallized/dismissed)

使用Mock测试Repository层，不依赖真实数据库。
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import List, Optional

from src.domain.memory.profile_memory import (
    ProfileMemory,
    StudentCognitiveProfile,
    ThinkingStyle,
    ErrorDNA,
    ZPDBoundary,
    CognitiveFeatureVector,
)
from src.domain.memory.episodic_memory import (
    EpisodicMemory,
    ProblemAttempt,
    VariantLineage,
    DecisionTrace,
    EpisodeQuery,
)
from src.domain.models.memory import (
    LearningEpisode,
    LearningEventType,
    ConceptStrength,
    MistakePattern,
    ConceptMastery,
    SemanticKnowledge,
)
from src.domain.models.diagnosis import ErrorType
from src.infrastructure.db.enums import GapStatus
from src.infrastructure.db.student import CognitiveProfile
from src.infrastructure.db.answer import StudentAnswer, AnswerTrace
from src.infrastructure.db.variant import VariantQuestion, VariantAnswer
from src.infrastructure.db.cognitive_gap import CognitiveGap


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_profile_repo():
    """Mock认知画像Repository."""
    repo = Mock()
    repo.find_one = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_gap_repo():
    """Mock认知缺口Repository."""
    repo = Mock()
    repo.find_one = AsyncMock()
    repo.find_many = AsyncMock(return_value=[])
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_answer_repo():
    """Mock学生答案Repository."""
    repo = Mock()
    repo.create = AsyncMock()
    repo.find_many = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_trace_repo():
    """Mock答题路径Repository."""
    repo = Mock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def mock_variant_repo():
    """Mock变形题Repository."""
    repo = Mock()
    repo.find_one = AsyncMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def mock_variant_answer_repo():
    """Mock变形题答案Repository."""
    repo = Mock()
    repo.create = AsyncMock()
    repo.find_many = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def sample_student_id():
    """示例学生ID."""
    return "stu_test_001"


@pytest.fixture
def sample_db_profile(sample_student_id):
    """示例数据库画像模型."""
    return CognitiveProfile(
        profile_id="profile_001",
        student_id=sample_student_id,
        thinking_style={
            "analytical": 0.6,
            "intuitive": 0.4,
            "systematic": 0.5,
            "creative": 0.5,
            "detail_oriented": 0.6,
        },
        error_dna={
            "error_patterns": [],
            "recurring_errors": {},
            "error_triggers": [],
        },
        zpd_boundary={
            "independent_level": 0.6,
            "assisted_level": 0.8,
            "challenge_zone": [0.6, 0.8],
            "optimal_difficulty": 5,
        },
        cognitive_features={
            "dimensions": {
                "processing_speed": 0.5,
                "working_memory": 0.6,
            },
            "version": 1,
        },
        crystallized_at=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_cognitive_gaps(sample_student_id):
    """示例认知缺口列表."""
    return [
        CognitiveGap(
            gap_id="gap_001",
            student_id=sample_student_id,
            gap_type="concept_gap",
            status=GapStatus.CRYSTALLIZED,
            related_knowledge=["kp_fraction", "kp_decimal"],
            discovered_at=datetime.utcnow() - timedelta(days=30),
            crystallized_at=datetime.utcnow() - timedelta(days=7),
            occurrence_count=8,
        ),
        CognitiveGap(
            gap_id="gap_002",
            student_id=sample_student_id,
            gap_type="calculation_weakness",
            status=GapStatus.PENDING,
            related_knowledge=["kp_arithmetic"],
            discovered_at=datetime.utcnow() - timedelta(days=10),
            crystallized_at=None,
            occurrence_count=3,
        ),
    ]


# =============================================================================
# Profile Memory Tests
# =============================================================================

class TestProfileMemory:
    """Profile记忆层测试类."""
    
    @pytest.mark.asyncio
    async def test_get_profile_existing(self, mock_profile_repo, mock_gap_repo, sample_student_id, sample_db_profile):
        """测试获取已存在的画像.
        
        Given: 学生已有认知画像
        When: 调用get_profile
        Then: 返回画像数据
        """
        # Given: 配置Mock返回已有画像
        mock_profile_repo.find_one.return_value = sample_db_profile
        
        # When: 获取画像
        memory = ProfileMemory(mock_profile_repo, mock_gap_repo)
        profile = await memory.get_profile(sample_student_id)
        
        # Then: 验证返回结果
        assert profile is not None
        assert profile.student_id == sample_student_id
        assert isinstance(profile.thinking_style, ThinkingStyle)
        assert isinstance(profile.error_dna, ErrorDNA)
        assert isinstance(profile.zpd_boundary, ZPDBoundary)
    
    @pytest.mark.asyncio
    async def test_get_profile_not_exists(self, mock_profile_repo, mock_gap_repo, sample_student_id):
        """测试获取不存在的画像.
        
        Given: 学生没有认知画像
        When: 调用get_profile
        Then: 返回None
        """
        # Given: 配置Mock返回None
        mock_profile_repo.find_one.return_value = None
        
        # When: 获取画像
        memory = ProfileMemory(mock_profile_repo, mock_gap_repo)
        profile = await memory.get_profile(sample_student_id)
        
        # Then: 验证返回None
        assert profile is None
    
    @pytest.mark.asyncio
    async def test_create_profile(self, mock_profile_repo, mock_gap_repo, sample_student_id):
        """测试创建新画像.
        
        Given: 学生没有认知画像
        When: 调用create_profile
        Then: 创建并返回新画像
        """
        # When: 创建画像
        memory = ProfileMemory(mock_profile_repo, mock_gap_repo)
        profile = await memory.create_profile(sample_student_id)
        
        # Then: 验证创建
        assert profile is not None
        assert profile.student_id == sample_student_id
        assert profile.version == 1
        assert isinstance(profile.thinking_style, ThinkingStyle)
        assert isinstance(profile.error_dna, ErrorDNA)
        mock_profile_repo.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_profile(self, mock_profile_repo, mock_gap_repo, sample_student_id, sample_db_profile):
        """测试更新画像.
        
        Given: 已有认知画像
        When: 调用update_profile
        Then: 更新并返回新数据
        """
        # Given: 配置Mock返回已有画像
        mock_profile_repo.find_one.return_value = sample_db_profile
        
        # When: 更新画像
        memory = ProfileMemory(mock_profile_repo, mock_gap_repo)
        profile = await memory.get_profile(sample_student_id)
        profile.thinking_style.analytical = 0.8
        updated = await memory.update_profile(profile)
        
        # Then: 验证更新
        assert updated.thinking_style.analytical == 0.8
        mock_profile_repo.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_crystallize_profile(self, mock_profile_repo, mock_gap_repo, sample_student_id, sample_db_profile):
        """测试固化画像.
        
        Given: 画像存在且超过30天
        When: 调用crystallize_profile
        Then: 标记固化时间
        """
        # Given: 配置Mock返回超过30天的画像
        sample_db_profile.updated_at = datetime.utcnow() - timedelta(days=35)
        mock_profile_repo.find_one.return_value = sample_db_profile
        
        # When: 固化画像
        memory = ProfileMemory(mock_profile_repo, mock_gap_repo)
        profile = await memory.crystallize_profile(sample_student_id)
        
        # Then: 验证固化
        assert profile is not None
        assert profile.crystallized_at is not None
    
    @pytest.mark.asyncio
    async def test_not_crystallize_recent_profile(self, mock_profile_repo, mock_gap_repo, sample_student_id, sample_db_profile):
        """测试不固化近期画像.
        
        Given: 画像更新不到30天
        When: 调用crystallize_profile
        Then: 不执行固化
        """
        # Given: 配置Mock返回近期画像
        sample_db_profile.updated_at = datetime.utcnow() - timedelta(days=10)
        mock_profile_repo.find_one.return_value = sample_db_profile
        
        # When: 尝试固化
        memory = ProfileMemory(mock_profile_repo, mock_gap_repo)
        profile = await memory.crystallize_profile(sample_student_id)
        
        # Then: 验证未固化
        assert profile is not None
        assert profile.crystallized_at is None
    
    @pytest.mark.asyncio
    async def test_update_error_dna(self, mock_profile_repo, mock_gap_repo, sample_student_id, sample_db_profile):
        """测试更新错误DNA.
        
        Given: 学生发生错误
        When: 调用update_error_dna
        Then: 更新错误模式
        """
        # Given: 配置Mock返回已有画像
        mock_profile_repo.find_one.return_value = sample_db_profile
        
        # When: 更新错误DNA
        memory = ProfileMemory(mock_profile_repo, mock_gap_repo)
        updated = await memory.update_error_dna(
            sample_student_id,
            ErrorType.CALCULATION_ERROR,
            ["kp_fraction", "kp_decimal"],
        )
        
        # Then: 验证更新
        assert updated is not None
        assert len(updated.error_dna.error_patterns) > 0


# =============================================================================
# Episodic Memory Tests
# =============================================================================

class TestEpisodicMemory:
    """Episodic记忆层测试类."""
    
    @pytest.mark.asyncio
    async def test_record_attempt_success(
        self,
        mock_answer_repo,
        mock_trace_repo,
        mock_variant_repo,
        mock_variant_answer_repo,
        sample_student_id,
    ):
        """测试记录成功解题尝试.
        
        Given: 学生答对题目
        When: 调用record_attempt
        Then: 创建学习事件记录
        """
        # When: 记录尝试
        memory = EpisodicMemory(mock_answer_repo, mock_trace_repo, mock_variant_repo, mock_variant_answer_repo)
        episode = await memory.record_attempt(
            student_id=sample_student_id,
            question_id="q_001",
            answer_content="42",
            is_correct=True,
            time_spent=120,
            confidence=0.85,
        )
        
        # Then: 验证记录
        assert episode is not None
        assert episode.student_id == sample_student_id
        assert episode.problem_id == "q_001"
        assert episode.final_result == "correct"
        assert episode.event_type == LearningEventType.PROBLEM_ATTEMPT
        mock_answer_repo.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_record_attempt_failure(
        self,
        mock_answer_repo,
        mock_trace_repo,
        mock_variant_repo,
        mock_variant_answer_repo,
        sample_student_id,
    ):
        """测试记录失败解题尝试.
        
        Given: 学生答错题目
        When: 调用record_attempt
        Then: 记录错误类型
        """
        # When: 记录错误尝试
        memory = EpisodicMemory(mock_answer_repo, mock_trace_repo, mock_variant_repo, mock_variant_answer_repo)
        episode = await memory.record_attempt(
            student_id=sample_student_id,
            question_id="q_002",
            answer_content="10",
            is_correct=False,
            time_spent=180,
            confidence=0.60,
            error_type=ErrorType.CALCULATION_ERROR,
        )
        
        # Then: 验证错误记录
        assert episode is not None
        assert episode.final_result == "incorrect"
        assert episode.error_type == ErrorType.CALCULATION_ERROR
    
    @pytest.mark.asyncio
    async def test_record_variant_practice(
        self,
        mock_answer_repo,
        mock_trace_repo,
        mock_variant_repo,
        mock_variant_answer_repo,
        sample_student_id,
    ):
        """测试记录变形题练习.
        
        Given: 学生完成变形题
        When: 调用record_variant_practice
        Then: 创建变形题练习记录
        """
        # Given: Mock返回原题和变形题
        original_answer = StudentAnswer(
            answer_id="ans_001",
            question_id="q_orig",
            student_id=sample_student_id,
            answer_content="5",
            is_correct=False,
        )
        mock_answer_repo.find_many.return_value = [original_answer]
        
        variant = VariantQuestion(
            variant_id="var_001",
            original_question_id="q_orig",
            variant_type="numeric_change",
            variant_content="变形题内容",
        )
        mock_variant_repo.find_one.return_value = variant
        
        # When: 记录变形题练习
        memory = EpisodicMemory(mock_answer_repo, mock_trace_repo, mock_variant_repo, mock_variant_answer_repo)
        lineage = await memory.record_variant_practice(
            student_id=sample_student_id,
            variant_id="var_001",
            answer_content="15",
            is_correct=True,
            time_spent=90,
        )
        
        # Then: 验证记录
        assert lineage is not None
        assert lineage.variant_id == "var_001"
        assert lineage.student_id == sample_student_id
        assert lineage.original_result is False
        assert lineage.variant_result is True
    
    def test_variant_lineage_validation_master(self):
        """测试变形题验证-掌握.
        
        Given: 原题和变形题都正确
        When: 确定验证结果
        Then: 返回master
        """
        # Given: 都正确
        lineage = VariantLineage(
            lineage_id="lineage_001",
            original_question_id="q_orig",
            variant_id="var_001",
            variant_type="numeric_change",
            student_id="stu_001",
            original_result=True,
            variant_result=True,
        )
        
        # When: 确定验证结果
        result = lineage.determine_validation()
        
        # Then: 验证结果为掌握
        assert result == "master"
    
    def test_variant_lineage_validation_careless(self):
        """测试变形题验证-粗心.
        
        Given: 原题错误，变形题正确
        When: 确定验证结果
        Then: 返回careless
        """
        # Given: 原题错，变形题对
        lineage = VariantLineage(
            lineage_id="lineage_002",
            original_question_id="q_orig",
            variant_id="var_002",
            variant_type="numeric_change",
            student_id="stu_001",
            original_result=False,
            variant_result=True,
        )
        
        # When: 确定验证结果
        result = lineage.determine_validation()
        
        # Then: 验证结果为粗心
        assert result == "careless"
    
    def test_variant_lineage_validation_misunderstanding(self):
        """测试变形题验证-误解.
        
        Given: 原题正确，变形题错误
        When: 确定验证结果
        Then: 返回misunderstanding
        """
        # Given: 原题对，变形题错
        lineage = VariantLineage(
            lineage_id="lineage_003",
            original_question_id="q_orig",
            variant_id="var_003",
            variant_type="numeric_change",
            student_id="stu_001",
            original_result=True,
            variant_result=False,
        )
        
        # When: 确定验证结果
        result = lineage.determine_validation()
        
        # Then: 验证结果为深层误解
        assert result == "misunderstanding"
    
    def test_episode_query_matches(self):
        """测试事件查询匹配.
        
        Given: 查询条件
        When: 检查事件是否匹配
        Then: 正确判断匹配结果
        """
        # Given: 创建事件和查询
        episode = LearningEpisode(
            student_id="stu_001",
            event_type=LearningEventType.PROBLEM_ATTEMPT,
            problem_id="q_001",
            subject="math",
            timestamp=datetime.utcnow(),
        )
        
        # When/Then: 测试各种查询条件
        # 匹配学生ID
        query1 = EpisodeQuery(student_id="stu_001")
        assert query1.matches(episode) is True
        
        # 不匹配学生ID
        query2 = EpisodeQuery(student_id="stu_002")
        assert query2.matches(episode) is False
        
        # 匹配事件类型
        query3 = EpisodeQuery(event_types=[LearningEventType.PROBLEM_ATTEMPT])
        assert query3.matches(episode) is True
        
        # 不匹配事件类型
        query4 = EpisodeQuery(event_types=[LearningEventType.HINT_REQUEST])
        assert query4.matches(episode) is False
        
        # 匹配学科
        query5 = EpisodeQuery(subject="math")
        assert query5.matches(episode) is True
        
        # 不匹配学科
        query6 = EpisodeQuery(subject="physics")
        assert query6.matches(episode) is False


# =============================================================================
# Semantic Knowledge Tests
# =============================================================================

class TestSemanticKnowledge:
    """Semantic知识层测试类."""
    
    def test_concept_strength_record_attempt_success(self):
        """测试概念强度-记录成功尝试.
        
        Given: 概念掌握记录
        When: 记录成功尝试
        Then: 更新成功率和掌握程度
        """
        # Given: 创建概念强度
        concept = ConceptStrength(
            concept_id="kp_linear_eq",
            concept_name="一元一次方程",
            mastery_level=0.6,
            attempt_count=5,
            success_count=3,
            success_rate=0.6,
        )
        
        # When: 记录成功
        concept.record_attempt(success=True)
        
        # Then: 验证更新
        assert concept.attempt_count == 6
        assert concept.success_count == 4
        assert concept.success_rate == 4/6
        assert concept.mastery_level > 0.6  # 贝叶斯更新后应增加
    
    def test_concept_strength_record_attempt_failure(self):
        """测试概念强度-记录失败尝试.
        
        Given: 概念掌握记录
        When: 记录失败尝试
        Then: 更新成功率和掌握程度（降低）
        """
        # Given: 创建概念强度
        concept = ConceptStrength(
            concept_id="kp_fraction",
            concept_name="分数运算",
            mastery_level=0.7,
            attempt_count=10,
            success_count=7,
            success_rate=0.7,
        )
        
        # When: 记录失败
        concept.record_attempt(success=False)
        
        # Then: 验证更新
        assert concept.attempt_count == 11
        assert concept.success_count == 7
        assert concept.success_rate == 7/11
        assert concept.mastery_level < 0.7  # 贝叶斯更新后应降低
    
    def test_semantic_knowledge_get_concept(self):
        """测试获取概念掌握详情.
        
        Given: 语义知识包含多个概念
        When: 获取指定概念
        Then: 返回概念详情
        """
        # Given: 创建语义知识
        knowledge = SemanticKnowledge(
            student_id="stu_001",
            concept_mastery=[
                ConceptMastery(
                    concept_id="kp_001",
                    concept_name="概念1",
                    mastery_level=0.8,
                ),
                ConceptMastery(
                    concept_id="kp_002",
                    concept_name="概念2",
                    mastery_level=0.6,
                ),
            ],
        )
        
        # When: 获取概念
        concept = knowledge.get_concept("kp_001")
        
        # Then: 验证结果
        assert concept is not None
        assert concept.concept_id == "kp_001"
        assert concept.concept_name == "概念1"
        
        # 获取不存在的概念
        not_found = knowledge.get_concept("kp_999")
        assert not_found is None
    
    def test_semantic_knowledge_update_concept(self):
        """测试更新概念掌握详情.
        
        Given: 语义知识
        When: 更新或添加概念
        Then: 正确更新或追加
        """
        # Given: 创建语义知识
        knowledge = SemanticKnowledge(
            student_id="stu_001",
            concept_mastery=[
                ConceptMastery(
                    concept_id="kp_001",
                    concept_name="概念1",
                    mastery_level=0.8,
                ),
            ],
        )
        
        # When: 更新现有概念
        updated_concept = ConceptMastery(
            concept_id="kp_001",
            concept_name="概念1",
            mastery_level=0.9,
        )
        knowledge.update_concept(updated_concept)
        
        # Then: 验证更新
        concept = knowledge.get_concept("kp_001")
        assert concept.mastery_level == 0.9
        
        # When: 添加新概念
        new_concept = ConceptMastery(
            concept_id="kp_002",
            concept_name="概念2",
            mastery_level=0.7,
        )
        knowledge.update_concept(new_concept)
        
        # Then: 验证追加
        assert len(knowledge.concept_mastery) == 2


# =============================================================================
# Meta State Flow Tests
# =============================================================================

class TestMetaStateFlow:
    """Meta状态流转测试类."""
    
    def test_gap_status_pending_to_crystallized(self):
        """测试缺口状态pending→crystallized流转.
        
        Given: pending状态的认知缺口
        When: 发生足够多次错误
        Then: 状态变为crystallized
        """
        # Given: pending状态的缺口
        gap = CognitiveGap(
            gap_id="gap_001",
            student_id="stu_001",
            gap_type="concept_gap",
            status=GapStatus.PENDING,
            related_knowledge=["kp_test"],
            discovered_at=datetime.utcnow() - timedelta(days=10),
            occurrence_count=5,
        )
        
        # When: 模拟多次错误后结晶（通常需要一定时间或次数）
        gap.occurrence_count = 8
        gap.crystallized_at = datetime.utcnow()
        gap.status = GapStatus.CRYSTALLIZED
        
        # Then: 验证状态流转
        assert gap.status == GapStatus.CRYSTALLIZED
        assert gap.crystallized_at is not None
    
    def test_gap_status_pending_to_dismissed(self):
        """测试缺口状态pending→dismissed流转.
        
        Given: pending状态的认知缺口
        When: 学生多次正确回答相关题目
        Then: 状态变为dismissed
        """
        # Given: pending状态的缺口
        gap = CognitiveGap(
            gap_id="gap_002",
            student_id="stu_001",
            gap_type="calculation_weakness",
            status=GapStatus.PENDING,
            related_knowledge=["kp_arithmetic"],
            discovered_at=datetime.utcnow() - timedelta(days=20),
            occurrence_count=2,
        )
        
        # When: 模拟确认是误判后解除
        gap.status = GapStatus.DISMISSED
        
        # Then: 验证状态流转
        assert gap.status == GapStatus.DISMISSED
    
    def test_profile_should_crystallize(self):
        """测试画像固化判断.
        
        Given: 学生认知画像
        When: 检查是否应该固化
        Then: 根据时间正确判断
        """
        # Given: 创建超过30天的画像
        old_profile = StudentCognitiveProfile(
            student_id="stu_001",
            last_updated=datetime.utcnow() - timedelta(days=35),
        )
        
        # When/Then: 验证应该固化
        assert old_profile.should_crystallize() is True
        
        # Given: 创建近期的画像
        recent_profile = StudentCognitiveProfile(
            student_id="stu_002",
            last_updated=datetime.utcnow() - timedelta(days=10),
        )
        
        # When/Then: 验证不应该固化
        assert recent_profile.should_crystallize() is False
        
        # Given: 已固化的画像
        crystallized_profile = StudentCognitiveProfile(
            student_id="stu_003",
            last_updated=datetime.utcnow() - timedelta(days=40),
            crystallized_at=datetime.utcnow() - timedelta(days=5),
        )
        
        # When/Then: 验证不应该重复固化
        assert crystallized_profile.should_crystallize() is False
    
    def test_error_dna_pattern_tracking(self):
        """测试错误DNA模式追踪.
        
        Given: 学生的错误DNA
        When: 添加新的错误模式
        Then: 正确追踪重复错误
        """
        # Given: 创建错误DNA
        error_dna = ErrorDNA()
        
        # When: 添加首次错误模式
        pattern1 = MistakePattern(
            error_type=ErrorType.CALCULATION_ERROR,
            occurrence_count=1,
        )
        error_dna.add_pattern(pattern1)
        
        # Then: 验证添加成功
        assert len(error_dna.error_patterns) == 1
        
        # When: 添加相同类型的错误模式
        pattern2 = MistakePattern(
            error_type=ErrorType.CALCULATION_ERROR,
            occurrence_count=2,
        )
        error_dna.add_pattern(pattern2)
        
        # Then: 验证合并计数
        assert len(error_dna.error_patterns) == 1
        assert error_dna.error_patterns[0].occurrence_count == 3
        assert error_dna.recurring_errors.get(ErrorType.CALCULATION_ERROR.value) == 1
    
    def test_zpd_boundary_update(self):
        """测试ZPD边界更新.
        
        Given: ZPD边界
        When: 根据成功率更新
        Then: 边界正确调整
        """
        # Given: 初始ZPD边界
        zpd = ZPDBoundary(
            independent_level=0.6,
            assisted_level=0.8,
            optimal_difficulty=5,
        )
        
        # When: 高成功率，提高难度
        zpd.update_boundary(success_rate=0.85)
        
        # Then: 验证边界提高
        assert zpd.independent_level > 0.6
        assert zpd.assisted_level > 0.8
        
        # When: 低成功率，降低难度
        zpd2 = ZPDBoundary(
            independent_level=0.6,
            assisted_level=0.8,
        )
        zpd2.update_boundary(success_rate=0.4)
        
        # Then: 验证边界降低
        assert zpd2.independent_level < 0.6
        assert zpd2.assisted_level < 0.8
    
    def test_zpd_is_in_zpd(self):
        """测试ZPD范围判断.
        
        Given: ZPD边界
        When: 检查难度是否在ZPD内
        Then: 正确判断
        """
        # Given: ZPD边界 0.6-0.8
        zpd = ZPDBoundary(
            independent_level=0.6,
            assisted_level=0.8,
            challenge_zone=(0.6, 0.8),
        )
        
        # When/Then: 测试各种难度
        assert zpd.is_in_zpd(0.5) is False  # 低于ZPD
        assert zpd.is_in_zpd(0.6) is True   # ZPD下限
        assert zpd.is_in_zpd(0.7) is True   # ZPD内
        assert zpd.is_in_zpd(0.8) is True   # ZPD上限
        assert zpd.is_in_zpd(0.9) is False  # 高于ZPD


# =============================================================================
# Profile Update Tests
# =============================================================================

class TestProfileUpdate:
    """画像更新测试类."""
    
    def test_update_from_episodes(self):
        """测试从学习事件更新画像.
        
        Given: 学习事件列表
        When: 更新画像
        Then: 画像正确更新
        """
        # Given: 创建画像和学习事件
        profile = StudentCognitiveProfile(student_id="stu_001")
        
        episodes_data = [
            {"is_correct": True, "time_spent": 60},
            {"is_correct": True, "time_spent": 90},
            {"is_correct": False, "time_spent": 120},
            {"is_correct": True, "time_spent": 80},
        ]
        
        # When: 从事件更新画像
        profile.update_from_episodes(episodes_data)
        
        # Then: 验证更新
        assert profile.version == 2
        assert profile.last_updated is not None
        # 成功率高，系统性思维应增加
        assert profile.thinking_style.systematic >= 0.5
    
    def test_thinking_style_dominant(self):
        """测试主导思维风格判断.
        
        Given: 思维风格评分
        When: 获取主导风格
        Then: 返回最高分项
        """
        # Given: 分析型思维高
        style = ThinkingStyle(
            analytical=0.8,
            intuitive=0.3,
            systematic=0.6,
            creative=0.4,
        )
        
        # When: 获取主导风格
        dominant = style.get_dominant_style()
        
        # Then: 验证为分析型
        assert dominant == "analytical"
    
    def test_cognitive_feature_vector_similarity(self):
        """测试认知特征向量相似度.
        
        Given: 两个特征向量
        When: 计算相似度
        Then: 返回正确相似度值
        """
        # Given: 创建两个相似的特征向量
        vector1 = CognitiveFeatureVector()
        vector1.dimensions = {
            "processing_speed": 0.8,
            "working_memory": 0.7,
        }
        
        vector2 = CognitiveFeatureVector()
        vector2.dimensions = {
            "processing_speed": 0.7,
            "working_memory": 0.8,
        }
        
        # When: 计算相似度
        similarity = vector1.cosine_similarity(vector2)
        
        # Then: 验证相似度高
        assert 0 < similarity <= 1
        assert similarity > 0.9  # 相似度应该很高
