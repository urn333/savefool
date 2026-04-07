"""
表结构测试

验证所有表、字段、约束是否正确创建
"""

import pytest
import sqlite3


@pytest.mark.schema
@pytest.mark.db
class TestTableStructure:
    """测试数据库表结构"""
    
    def test_student_table_exists(self, initialized_db: sqlite3.Connection):
        """
        测试student表是否存在且结构正确
        
        Given: 数据库已初始化
        When: 查询student表结构
        Then: 应存在且包含所有必需字段
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='student'")
        result = cursor.fetchone()
        
        assert result is not None, "student表不存在"
        schema = result[0].lower()
        
        # 验证必需字段
        assert "student_id" in schema, "缺少student_id字段"
        assert "name" in schema, "缺少name字段"
        assert "grade" in schema, "缺少grade字段"
        assert "preferred_subjects" in schema, "缺少preferred_subjects字段"
        assert "created_at" in schema, "缺少created_at字段"
        assert "updated_at" in schema, "缺少updated_at字段"
    
    def test_cognitive_profile_table_exists(self, initialized_db: sqlite3.Connection):
        """
        测试cognitive_profile表结构
        
        Given: 数据库已初始化
        When: 查询cognitive_profile表结构
        Then: 应存在且包含所有认知画像字段
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='cognitive_profile'")
        result = cursor.fetchone()
        
        assert result is not None, "cognitive_profile表不存在"
        schema = result[0].lower()
        
        assert "profile_id" in schema, "缺少profile_id字段"
        assert "student_id" in schema, "缺少student_id字段"
        assert "thinking_style" in schema, "缺少thinking_style字段"
        assert "error_dna" in schema, "缺少error_dna字段"
        assert "zpd_boundary" in schema, "缺少zpd_boundary字段"
        assert "cognitive_features" in schema, "缺少cognitive_features字段"
        assert "crystallized_at" in schema, "缺少crystallized_at字段"
    
    def test_homework_table_exists(self, initialized_db: sqlite3.Connection):
        """
        测试homework表结构
        
        Given: 数据库已初始化
        When: 查询homework表结构
        Then: 应存在且包含所有作业字段
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='homework'")
        result = cursor.fetchone()
        
        assert result is not None, "homework表不存在"
        schema = result[0].lower()
        
        assert "homework_id" in schema, "缺少homework_id字段"
        assert "student_id" in schema, "缺少student_id字段"
        assert "subject" in schema, "缺少subject字段"
        assert "page_count" in schema, "缺少page_count字段"
        assert "uploaded_at" in schema, "缺少uploaded_at字段"
        assert "image_urls" in schema, "缺少image_urls字段"
        assert "status" in schema, "缺少status字段"
        assert "archived_at" in schema, "缺少archived_at字段"
    
    def test_question_table_exists(self, initialized_db: sqlite3.Connection):
        """
        测试question表结构
        
        Given: 数据库已初始化
        When: 查询question表结构
        Then: 应存在且包含所有题目字段
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='question'")
        result = cursor.fetchone()
        
        assert result is not None, "question表不存在"
        schema = result[0].lower()
        
        assert "question_id" in schema, "缺少question_id字段"
        assert "homework_id" in schema, "缺少homework_id字段"
        assert "original_image_url" in schema, "缺少original_image_url字段"
        assert "ocr_text" in schema, "缺少ocr_text字段"
        assert "parsed_content" in schema, "缺少parsed_content字段"
        assert "question_number" in schema, "缺少question_number字段"
        assert "difficulty_level" in schema, "缺少difficulty_level字段"
    
    def test_student_answer_table_exists(self, initialized_db: sqlite3.Connection):
        """
        测试student_answer表结构
        
        Given: 数据库已初始化
        When: 查询student_answer表结构
        Then: 应存在且包含所有答案字段
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='student_answer'")
        result = cursor.fetchone()
        
        assert result is not None, "student_answer表不存在"
        schema = result[0].lower()
        
        assert "answer_id" in schema, "缺少answer_id字段"
        assert "question_id" in schema, "缺少question_id字段"
        assert "student_id" in schema, "缺少student_id字段"
        assert "answer_content" in schema, "缺少answer_content字段"
        assert "answered_at" in schema, "缺少answered_at字段"
        assert "is_correct" in schema, "缺少is_correct字段"
        assert "confidence_score" in schema, "缺少confidence_score字段"
    
    def test_error_diagnosis_table_exists(self, initialized_db: sqlite3.Connection):
        """
        测试error_diagnosis表结构
        
        Given: 数据库已初始化
        When: 查询error_diagnosis表结构
        Then: 应存在且包含所有诊断字段
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='error_diagnosis'")
        result = cursor.fetchone()
        
        assert result is not None, "error_diagnosis表不存在"
        schema = result[0].lower()
        
        assert "diagnosis_id" in schema, "缺少diagnosis_id字段"
        assert "answer_id" in schema, "缺少answer_id字段"
        assert "question_id" in schema, "缺少question_id字段"
        assert "student_id" in schema, "缺少student_id字段"
        assert "error_type" in schema, "缺少error_type字段"
        assert "knowledge_tags" in schema, "缺少knowledge_tags字段"
        assert "confidence_score" in schema, "缺少confidence_score字段"
        assert "diagnosis_path" in schema, "缺少diagnosis_path字段"
    
    def test_variant_question_table_exists(self, initialized_db: sqlite3.Connection):
        """
        测试variant_question表结构
        
        Given: 数据库已初始化
        When: 查询variant_question表结构
        Then: 应存在且包含所有变形题字段
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='variant_question'")
        result = cursor.fetchone()
        
        assert result is not None, "variant_question表不存在"
        schema = result[0].lower()
        
        assert "variant_id" in schema, "缺少variant_id字段"
        assert "original_question_id" in schema, "缺少original_question_id字段"
        assert "variant_type" in schema, "缺少variant_type字段"
        assert "variant_content" in schema, "缺少variant_content字段"
        assert "validation_status" in schema, "缺少validation_status字段"
    
    def test_knowledge_point_table_exists(self, initialized_db: sqlite3.Connection):
        """
        测试knowledge_point表结构
        
        Given: 数据库已初始化
        When: 查询knowledge_point表结构
        Then: 应存在且包含所有知识点字段
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='knowledge_point'")
        result = cursor.fetchone()
        
        assert result is not None, "knowledge_point表不存在"
        schema = result[0].lower()
        
        assert "knowledge_id" in schema, "缺少knowledge_id字段"
        assert "subject" in schema, "缺少subject字段"
        assert "grade_level" in schema, "缺少grade_level字段"
        assert "knowledge_name" in schema, "缺少knowledge_name字段"
        assert "description" in schema, "缺少description字段"
        assert "parent_knowledge_id" in schema, "缺少parent_knowledge_id字段"
    
    def test_cognitive_gap_table_exists(self, initialized_db: sqlite3.Connection):
        """
        测试cognitive_gap表结构
        
        Given: 数据库已初始化
        When: 查询cognitive_gap表结构
        Then: 应存在且包含所有认知缺口字段
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='cognitive_gap'")
        result = cursor.fetchone()
        
        assert result is not None, "cognitive_gap表不存在"
        schema = result[0].lower()
        
        assert "gap_id" in schema, "缺少gap_id字段"
        assert "student_id" in schema, "缺少student_id字段"
        assert "gap_type" in schema, "缺少gap_type字段"
        assert "status" in schema, "缺少status字段"
        assert "related_knowledge" in schema, "缺少related_knowledge字段"
        assert "occurrence_count" in schema, "缺少occurrence_count字段"
    
    def test_all_tables_created(self, initialized_db: sqlite3.Connection):
        """
        测试所有表是否都已创建
        
        Given: 数据库已初始化
        When: 查询所有表名
        Then: 应包含所有20个表
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = {row[0] for row in cursor.fetchall()}
        
        expected_tables = {
            'student',
            'cognitive_profile',
            'homework',
            'question',
            'homework_analysis',
            'student_answer',
            'answer_trace',
            'error_diagnosis',
            'diagnosis_path',
            'variant_question',
            'variant_answer',
            'knowledge_point',
            'knowledge_dependency',
            'student_knowledge_mastery',
            'question_knowledge_tag',
            'misconception',
            'cognitive_gap',
            'gap_evidence',
            'parent_description',
            'description_parse',
            'question_fts'
        }
        
        missing = expected_tables - tables
        assert not missing, f"缺少以下表: {missing}"


@pytest.mark.schema
@pytest.mark.db
class TestFieldTypes:
    """测试字段类型和约束"""
    
    def test_student_field_types(self, initialized_db: sqlite3.Connection):
        """
        测试student表字段类型
        
        Given: student表已创建
        When: 查询表结构
        Then: 字段类型应符合设计要求
        """
        cursor = initialized_db.cursor()
        cursor.execute("PRAGMA table_info(student)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        # VARCHAR字段在SQLite中存储为TEXT
        assert columns['student_id'] == 'VARCHAR(32)', f"student_id类型错误: {columns['student_id']}"
        assert columns['name'] == 'VARCHAR(64)', f"name类型错误: {columns['name']}"
        assert columns['grade'] == 'VARCHAR(16)', f"grade类型错误: {columns['grade']}"
        assert columns['preferred_subjects'] == "JSON", f"preferred_subjects类型错误"
        assert columns['created_at'] == 'DATETIME', f"created_at类型错误"
    
    def test_homework_constraints(self, initialized_db: sqlite3.Connection):
        """
        测试homework表约束
        
        Given: homework表已创建
        When: 验证CHECK约束
        Then: page_count必须大于0，status必须是有效值
        """
        cursor = initialized_db.cursor()
        
        # 测试page_count CHECK约束
        student_id = "test_stu_001"
        cursor.execute("""
            INSERT INTO student (student_id, name, grade) 
            VALUES (?, 'Test', '七年级')
        """, (student_id,))
        
        # 尝试插入page_count=0的数据，应该失败
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
                VALUES ('hw_001', ?, '数学', 0, '["test.jpg"]')
            """, (student_id,))
        
        initialized_db.rollback()
    
    def test_confidence_score_range(self, initialized_db: sqlite3.Connection):
        """
        测试confidence_score范围约束
        
        Given: 相关表已创建
        When: 插入超出0-1范围的confidence_score
        Then: 应触发约束错误
        """
        cursor = initialized_db.cursor()
        
        # 准备基础数据
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_001', 'Test', '七年级')")
        cursor.execute("INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls) VALUES ('hw_001', 'stu_001', '数学', 1, '["test.jpg"]')")
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_001', 'hw_001')")
        cursor.execute("INSERT INTO student_answer (answer_id, question_id, student_id, answer_content) VALUES ('ans_001', 'q_001', 'stu_001', 'test')")
        
        # 测试超出范围的confidence_score
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO error_diagnosis (diagnosis_id, answer_id, question_id, student_id, error_type, confidence_score)
                VALUES ('diag_001', 'ans_001', 'q_001', 'stu_001', 'careless', 1.5)
            """)
        
        initialized_db.rollback()


@pytest.mark.schema
@pytest.mark.db
class TestDefaultValues:
    """测试默认值"""
    
    def test_student_default_values(self, initialized_db: sqlite3.Connection):
        """
        测试student表默认值
        
        Given: student表已创建
        When: 插入仅含必需字段的数据
        Then: 默认值应正确填充
        """
        cursor = initialized_db.cursor()
        cursor.execute("""
            INSERT INTO student (student_id, name, grade)
            VALUES ('stu_default', 'Test', '七年级')
        """)
        
        cursor.execute("SELECT preferred_subjects, created_at, updated_at FROM student WHERE student_id = 'stu_default'")
        row = cursor.fetchone()
        
        assert row[0] == '[]', f"preferred_subjects默认值错误: {row[0]}"
        assert row[1] is not None, "created_at未设置默认值"
        assert row[2] is not None, "updated_at未设置默认值"
        
        initialized_db.rollback()
    
    def test_homework_default_status(self, initialized_db: sqlite3.Connection):
        """
        测试homework表默认状态
        
        Given: homework表已创建
        When: 插入不含status的数据
        Then: status应为'active'
        """
        cursor = initialized_db.cursor()
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_001', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_001', 'stu_001', '数学', 1, '["test.jpg"]')
        """)
        
        cursor.execute("SELECT status FROM homework WHERE homework_id = 'hw_001'")
        row = cursor.fetchone()
        
        assert row[0] == 'active', f"status默认值错误: {row[0]}"
        
        initialized_db.rollback()
    
    def test_cognitive_gap_default_status(self, initialized_db: sqlite3.Connection):
        """
        测试cognitive_gap表默认状态
        
        Given: cognitive_gap表已创建
        When: 插入不含status的数据
        Then: status应为'pending'
        """
        cursor = initialized_db.cursor()
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_001', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO cognitive_gap (gap_id, student_id, gap_type)
            VALUES ('gap_001', 'stu_001', 'concept_gap')
        """)
        
        cursor.execute("SELECT status, occurrence_count FROM cognitive_gap WHERE gap_id = 'gap_001'")
        row = cursor.fetchone()
        
        assert row[0] == 'pending', f"status默认值错误: {row[0]}"
        assert row[1] == 1, f"occurrence_count默认值错误: {row[1]}"
        
        initialized_db.rollback()
