"""
Pytest配置和全局Fixtures

为AI助教系统提供测试基础设施：
- 数据库连接管理
- 测试数据工厂
- 异步测试支持
"""

import asyncio
import os
import sqlite3
import tempfile
import uuid
from datetime import datetime
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio


# =============================================================================
# 测试配置
# =============================================================================

def pytest_configure(config):
    """配置pytest环境"""
    config.addinivalue_line("markers", "db: 数据库相关测试")
    config.addinivalue_line("markers", "schema: 表结构测试")
    config.addinivalue_line("markers", "fk: 外键约束测试")
    config.addinivalue_line("markers", "index: 索引测试")
    config.addinivalue_line("markers", "crud: CRUD操作测试")
    config.addinivalue_line("markers", "enum: 枚举值测试")


# =============================================================================
# 工具函数
# =============================================================================

def generate_id(prefix: str = "") -> str:
    """生成测试用唯一ID"""
    return f"{prefix}{uuid.uuid4().hex[:16]}"


def get_current_timestamp() -> datetime:
    """获取当前时间戳"""
    return datetime.now()


# =============================================================================
# 数据库Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def db_path() -> str:
    """
    创建测试数据库文件路径
    
    Returns:
        测试数据库文件路径
    """
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_ai_tutor_")
    os.close(fd)
    yield path
    # 清理
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(scope="function")
def db_connection(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """
    创建数据库连接
    
    Given: 测试数据库已创建
    When: 请求数据库连接
    Then: 返回启用了外键约束的连接
    
    Args:
        db_path: 数据库文件路径
        
    Yields:
        sqlite3.Connection: 数据库连接对象
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    
    yield conn
    
    conn.close()


@pytest.fixture(scope="function")
def db_cursor(db_connection: sqlite3.Connection) -> sqlite3.Cursor:
    """
    创建数据库游标
    
    Args:
        db_connection: 数据库连接
        
    Returns:
        sqlite3.Cursor: 数据库游标
    """
    return db_connection.cursor()


@pytest.fixture(scope="function")
def initialized_db(db_connection: sqlite3.Connection) -> sqlite3.Connection:
    """
    初始化完整的数据库Schema
    
    Given: 空数据库连接
    When: 执行DDL创建所有表、索引、触发器
    Then: 返回包含完整Schema的数据库连接
    
    Args:
        db_connection: 数据库连接
        
    Returns:
        已初始化Schema的数据库连接
    """
    cursor = db_connection.cursor()
    
    # 1. 学生相关表
    cursor.executescript("""
    -- 学生表
    CREATE TABLE IF NOT EXISTS student (
        student_id VARCHAR(32) PRIMARY KEY,
        name VARCHAR(64) NOT NULL,
        grade VARCHAR(16) NOT NULL,
        preferred_subjects JSON DEFAULT '[]',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_student_grade ON student(grade);
    CREATE INDEX IF NOT EXISTS idx_student_updated ON student(updated_at);
    
    -- 认知画像表
    CREATE TABLE IF NOT EXISTS cognitive_profile (
        profile_id VARCHAR(32) PRIMARY KEY,
        student_id VARCHAR(32) NOT NULL UNIQUE,
        thinking_style JSON DEFAULT '{}',
        error_dna JSON DEFAULT '{}',
        zpd_boundary JSON DEFAULT '{}',
        cognitive_features JSON DEFAULT '{}',
        crystallized_at DATETIME,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_profile_student ON cognitive_profile(student_id);
    CREATE INDEX IF NOT EXISTS idx_profile_crystallized ON cognitive_profile(crystallized_at);
    """)
    
    # 2. 作业相关表
    cursor.executescript("""
    -- 作业表
    CREATE TABLE IF NOT EXISTS homework (
        homework_id VARCHAR(32) PRIMARY KEY,
        student_id VARCHAR(32) NOT NULL,
        subject VARCHAR(32) NOT NULL,
        page_count INTEGER NOT NULL CHECK (page_count > 0),
        uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        image_urls JSON NOT NULL,
        status VARCHAR(16) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
        archived_at DATETIME,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_homework_student ON homework(student_id, uploaded_at DESC);
    CREATE INDEX IF NOT EXISTS idx_homework_status ON homework(status, archived_at);
    CREATE INDEX IF NOT EXISTS idx_homework_uploaded ON homework(uploaded_at);
    
    -- 题目表
    CREATE TABLE IF NOT EXISTS question (
        question_id VARCHAR(32) PRIMARY KEY,
        homework_id VARCHAR(32) NOT NULL,
        original_image_url VARCHAR(512),
        ocr_text TEXT,
        parsed_content JSON,
        question_number INTEGER NOT NULL DEFAULT 1,
        difficulty_level VARCHAR(16),
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (homework_id) REFERENCES homework(homework_id) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_question_homework ON question(homework_id, question_number);
    
    -- 作业分析表
    CREATE TABLE IF NOT EXISTS homework_analysis (
        analysis_id VARCHAR(32) PRIMARY KEY,
        homework_id VARCHAR(32) NOT NULL UNIQUE,
        cognitive_features JSON DEFAULT '{}',
        key_decisions JSON DEFAULT '[]',
        analyzed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (homework_id) REFERENCES homework(homework_id) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_analysis_homework ON homework_analysis(homework_id);
    """)
    
    # 3. 答题与诊断表
    cursor.executescript("""
    -- 学生答案表
    CREATE TABLE IF NOT EXISTS student_answer (
        answer_id VARCHAR(32) PRIMARY KEY,
        question_id VARCHAR(32) NOT NULL,
        student_id VARCHAR(32) NOT NULL,
        answer_content TEXT NOT NULL,
        answered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        is_correct BOOLEAN,
        confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (question_id) REFERENCES question(question_id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_answer_student ON student_answer(student_id, answered_at DESC);
    CREATE INDEX IF NOT EXISTS idx_answer_question ON student_answer(question_id);
    CREATE INDEX IF NOT EXISTS idx_answer_correct ON student_answer(student_id, is_correct, answered_at);
    
    -- 答题轨迹表
    CREATE TABLE IF NOT EXISTS answer_trace (
        trace_id VARCHAR(32) PRIMARY KEY,
        answer_id VARCHAR(32) NOT NULL,
        decision_path JSON NOT NULL,
        recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (answer_id) REFERENCES student_answer(answer_id) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_trace_answer ON answer_trace(answer_id);
    
    -- 错题诊断表
    CREATE TABLE IF NOT EXISTS error_diagnosis (
        diagnosis_id VARCHAR(32) PRIMARY KEY,
        answer_id VARCHAR(32) NOT NULL,
        question_id VARCHAR(32) NOT NULL,
        student_id VARCHAR(32) NOT NULL,
        error_type VARCHAR(32) NOT NULL CHECK (error_type IN ('careless', 'method_error', 'concept_gap', 'calculation_error', 'reading_error', 'unknown')),
        knowledge_tags JSON NOT NULL DEFAULT '[]',
        confidence_score FLOAT NOT NULL DEFAULT 0.5 CHECK (confidence_score >= 0 AND confidence_score <= 1),
        diagnosis_path TEXT,
        diagnosed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (answer_id) REFERENCES student_answer(answer_id) ON DELETE CASCADE,
        FOREIGN KEY (question_id) REFERENCES question(question_id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_diagnosis_student ON error_diagnosis(student_id, diagnosed_at DESC);
    CREATE INDEX IF NOT EXISTS idx_diagnosis_error_type ON error_diagnosis(student_id, error_type, diagnosed_at);
    CREATE INDEX IF NOT EXISTS idx_diagnosis_confidence ON error_diagnosis(confidence_score);
    
    -- 诊断路径表
    CREATE TABLE IF NOT EXISTS diagnosis_path (
        path_id VARCHAR(32) PRIMARY KEY,
        diagnosis_id VARCHAR(32) NOT NULL,
        step_number INTEGER NOT NULL CHECK (step_number > 0),
        option_selected VARCHAR(64) NOT NULL,
        reasoning TEXT,
        FOREIGN KEY (diagnosis_id) REFERENCES error_diagnosis(diagnosis_id) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_path_diagnosis ON diagnosis_path(diagnosis_id, step_number);
    """)
    
    # 4. 变形题表
    cursor.executescript("""
    -- 变形题表
    CREATE TABLE IF NOT EXISTS variant_question (
        variant_id VARCHAR(32) PRIMARY KEY,
        original_question_id VARCHAR(32) NOT NULL,
        variant_type VARCHAR(32) NOT NULL CHECK (variant_type IN ('numeric_change', 'inverse_operation', 'context_transfer', 'difficulty_adjust', 'format_change')),
        variant_content TEXT NOT NULL,
        validation_status VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (validation_status IN ('pending', 'validated', 'failed', 'expired')),
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (original_question_id) REFERENCES question(question_id) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_variant_original ON variant_question(original_question_id);
    CREATE INDEX IF NOT EXISTS idx_variant_status ON variant_question(validation_status, created_at);
    
    -- 变形题答案表
    CREATE TABLE IF NOT EXISTS variant_answer (
        variant_answer_id VARCHAR(32) PRIMARY KEY,
        variant_id VARCHAR(32) NOT NULL,
        student_id VARCHAR(32) NOT NULL,
        answer_content TEXT NOT NULL,
        is_correct BOOLEAN NOT NULL DEFAULT 0,
        answered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (variant_id) REFERENCES variant_question(variant_id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_variant_answer_student ON variant_answer(student_id, variant_id);
    CREATE INDEX IF NOT EXISTS idx_variant_answer_result ON variant_answer(variant_id, is_correct);
    """)
    
    # 5. 知识图谱表
    cursor.executescript("""
    -- 知识点表
    CREATE TABLE IF NOT EXISTS knowledge_point (
        knowledge_id VARCHAR(32) PRIMARY KEY,
        subject VARCHAR(32) NOT NULL,
        grade_level VARCHAR(16) NOT NULL,
        knowledge_name VARCHAR(128) NOT NULL,
        description TEXT,
        parent_knowledge_id VARCHAR(32),
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (parent_knowledge_id) REFERENCES knowledge_point(knowledge_id) ON DELETE SET NULL
    );
    
    CREATE INDEX IF NOT EXISTS idx_knowledge_subject_grade ON knowledge_point(subject, grade_level);
    CREATE INDEX IF NOT EXISTS idx_knowledge_parent ON knowledge_point(parent_knowledge_id);
    
    -- 知识依赖表
    CREATE TABLE IF NOT EXISTS knowledge_dependency (
        dependency_id VARCHAR(32) PRIMARY KEY,
        knowledge_id VARCHAR(32) NOT NULL,
        prerequisite_id VARCHAR(32) NOT NULL,
        dependency_strength FLOAT NOT NULL DEFAULT 0.5 CHECK (dependency_strength >= 0 AND dependency_strength <= 1),
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (knowledge_id) REFERENCES knowledge_point(knowledge_id) ON DELETE CASCADE,
        FOREIGN KEY (prerequisite_id) REFERENCES knowledge_point(knowledge_id) ON DELETE CASCADE,
        CHECK (knowledge_id != prerequisite_id),
        UNIQUE(knowledge_id, prerequisite_id)
    );
    
    CREATE INDEX IF NOT EXISTS idx_dependency_knowledge ON knowledge_dependency(knowledge_id);
    CREATE INDEX IF NOT EXISTS idx_dependency_prereq ON knowledge_dependency(prerequisite_id);
    
    -- 学生知识掌握度表
    CREATE TABLE IF NOT EXISTS student_knowledge_mastery (
        mastery_id VARCHAR(32) PRIMARY KEY,
        student_id VARCHAR(32) NOT NULL,
        knowledge_id VARCHAR(32) NOT NULL,
        mastery_level FLOAT NOT NULL DEFAULT 0 CHECK (mastery_level >= 0 AND mastery_level <= 1),
        practice_count INTEGER NOT NULL DEFAULT 0 CHECK (practice_count >= 0),
        last_practiced DATETIME,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE,
        FOREIGN KEY (knowledge_id) REFERENCES knowledge_point(knowledge_id) ON DELETE CASCADE,
        UNIQUE(student_id, knowledge_id)
    );
    
    CREATE INDEX IF NOT EXISTS idx_mastery_student ON student_knowledge_mastery(student_id, mastery_level);
    CREATE INDEX IF NOT EXISTS idx_mastery_level ON student_knowledge_mastery(mastery_level, practice_count);
    
    -- 题目知识点标签表
    CREATE TABLE IF NOT EXISTS question_knowledge_tag (
        tag_id VARCHAR(32) PRIMARY KEY,
        question_id VARCHAR(32) NOT NULL,
        knowledge_id VARCHAR(32) NOT NULL,
        relevance_score FLOAT NOT NULL DEFAULT 1.0 CHECK (relevance_score >= 0 AND relevance_score <= 1),
        FOREIGN KEY (question_id) REFERENCES question(question_id) ON DELETE CASCADE,
        FOREIGN KEY (knowledge_id) REFERENCES knowledge_point(knowledge_id) ON DELETE CASCADE,
        UNIQUE(question_id, knowledge_id)
    );
    
    CREATE INDEX IF NOT EXISTS idx_tag_knowledge ON question_knowledge_tag(knowledge_id);
    
    -- 概念误解表
    CREATE TABLE IF NOT EXISTS misconception (
        misconception_id VARCHAR(32) PRIMARY KEY,
        knowledge_id VARCHAR(32) NOT NULL,
        misconception_pattern TEXT NOT NULL,
        correct_concept TEXT NOT NULL,
        verified_count INTEGER NOT NULL DEFAULT 0 CHECK (verified_count >= 0),
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (knowledge_id) REFERENCES knowledge_point(knowledge_id) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_misconception_knowledge ON misconception(knowledge_id);
    """)
    
    # 6. 认知缺口表
    cursor.executescript("""
    -- 认知缺口表
    CREATE TABLE IF NOT EXISTS cognitive_gap (
        gap_id VARCHAR(32) PRIMARY KEY,
        student_id VARCHAR(32) NOT NULL,
        gap_type VARCHAR(32) NOT NULL,
        status VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'crystallized', 'dismissed')),
        related_knowledge JSON NOT NULL DEFAULT '[]',
        discovered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        crystallized_at DATETIME,
        occurrence_count INTEGER NOT NULL DEFAULT 1 CHECK (occurrence_count >= 1),
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_gap_student ON cognitive_gap(student_id, status, discovered_at);
    CREATE INDEX IF NOT EXISTS idx_gap_status ON cognitive_gap(status, discovered_at);
    CREATE INDEX IF NOT EXISTS idx_gap_crystallized ON cognitive_gap(crystallized_at);
    
    -- 缺口证据表
    CREATE TABLE IF NOT EXISTS gap_evidence (
        evidence_id VARCHAR(32) PRIMARY KEY,
        gap_id VARCHAR(32) NOT NULL,
        diagnosis_id VARCHAR(32) NOT NULL,
        evidence_type VARCHAR(32) NOT NULL CHECK (evidence_type IN ('initial_diagnosis', 'repeat_error', 'variant_failed', 'cross_homework')),
        recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (gap_id) REFERENCES cognitive_gap(gap_id) ON DELETE CASCADE,
        FOREIGN KEY (diagnosis_id) REFERENCES error_diagnosis(diagnosis_id) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_evidence_gap ON gap_evidence(gap_id, recorded_at);
    CREATE INDEX IF NOT EXISTS idx_evidence_diagnosis ON gap_evidence(diagnosis_id);
    """)
    
    # 7. 家长描述表
    cursor.executescript("""
    -- 家长描述表
    CREATE TABLE IF NOT EXISTS parent_description (
        description_id VARCHAR(32) PRIMARY KEY,
        student_id VARCHAR(32) NOT NULL,
        raw_text TEXT NOT NULL,
        submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        source_type VARCHAR(32) NOT NULL DEFAULT 'text' CHECK (source_type IN ('text', 'voice', 'video')),
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_description_student ON parent_description(student_id, submitted_at DESC);
    
    -- 描述解析表
    CREATE TABLE IF NOT EXISTS description_parse (
        parse_id VARCHAR(32) PRIMARY KEY,
        description_id VARCHAR(32) NOT NULL UNIQUE,
        explicit_statements JSON NOT NULL DEFAULT '[]',
        implicit_observations JSON NOT NULL DEFAULT '[]',
        confidence_score FLOAT NOT NULL DEFAULT 0.5 CHECK (confidence_score >= 0 AND confidence_score <= 1),
        parsed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (description_id) REFERENCES parent_description(description_id) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_parse_description ON description_parse(description_id);
    CREATE INDEX IF NOT EXISTS idx_parse_confidence ON description_parse(confidence_score);
    """)
    
    # 8. 全文搜索虚拟表
    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS question_fts USING fts5(
        question_id,
        ocr_text,
        content='question',
        content_rowid='rowid'
    )
    """)
    
    db_connection.commit()
    
    yield db_connection
    
    # 清理所有数据（跳过虚拟表）
    cursor.execute("SELECT name, type FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    for table in tables:
        name = table[0]
        if not name.startswith("sqlite_") and not name.endswith("_fts"):
            cursor.execute(f"DELETE FROM {name}")
    db_connection.commit()


# =============================================================================
# 测试数据Fixtures
# =============================================================================

@pytest.fixture
def sample_student_data() -> dict:
    """示例学生数据"""
    return {
        "student_id": generate_id("stu_"),
        "name": "测试学生",
        "grade": "七年级",
        "preferred_subjects": '[\"数学", "英语\"]'
    }


@pytest.fixture
def sample_homework_data() -> dict:
    """示例作业数据"""
    return {
        "homework_id": generate_id("hw_"),
        "subject": "数学",
        "page_count": 2,
        "image_urls": '[\"url1.jpg", "url2.jpg\"]',
        "status": "active"
    }


@pytest.fixture
def sample_question_data() -> dict:
    """示例题目数据"""
    return {
        "question_id": generate_id("q_"),
        "original_image_url": "http://example.com/img.jpg",
        "ocr_text": "1 + 1 = ?",
        "parsed_content": '{"type": "math", "answer": "2"}',
        "question_number": 1,
        "difficulty_level": "easy"
    }


@pytest.fixture
def sample_answer_data() -> dict:
    """示例答案数据"""
    return {
        "answer_id": generate_id("ans_"),
        "answer_content": "2",
        "is_correct": True,
        "confidence_score": 0.95
    }


@pytest.fixture
def sample_diagnosis_data() -> dict:
    """示例诊断数据"""
    return {
        "diagnosis_id": generate_id("diag_"),
        "error_type": "careless",
        "knowledge_tags": '[\"加法运算\"]',
        "confidence_score": 0.85,
        "diagnosis_path": "Step1:A -> Step2:B"
    }


@pytest.fixture
def sample_knowledge_point_data() -> dict:
    """示例知识点数据"""
    return {
        "knowledge_id": generate_id("k_"),
        "subject": "数学",
        "grade_level": "七年级",
        "knowledge_name": "一元一次方程",
        "description": "形如ax + b = c的方程"
    }


@pytest.fixture
def sample_cognitive_gap_data() -> dict:
    """示例认知缺口数据"""
    return {
        "gap_id": generate_id("gap_"),
        "gap_type": "concept_gap",
        "status": "pending",
        "related_knowledge": '[\"k_001", "k_002\"]',
        "occurrence_count": 1
    }


@pytest.fixture
def sample_variant_question_data() -> dict:
    """示例变形题数据"""
    return {
        "variant_id": generate_id("var_"),
        "variant_type": "numeric_change",
        "variant_content": "2 + 3 = ?",
        "validation_status": "pending"
    }


@pytest.fixture
def sample_parent_description_data() -> dict:
    """示例家长描述数据"""
    return {
        "description_id": generate_id("desc_"),
        "raw_text": "孩子最近对数学很感兴趣",
        "source_type": "text"
    }
