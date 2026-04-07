"""
索引测试

验证所有索引是否正确创建，并测试查询性能
"""

import pytest
import sqlite3
import time


@pytest.mark.index
@pytest.mark.db
class TestIndexExistence:
    """测试索引是否存在"""
    
    def test_student_indexes(self, initialized_db: sqlite3.Connection):
        """
        测试student表索引
        
        Given: 数据库已初始化
        When: 查询student表的索引
        Then: 应存在所有设计要求的索引
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='student'")
        indexes = {row[0] for row in cursor.fetchall()}
        
        assert 'idx_student_grade' in indexes, "缺少idx_student_grade索引"
        assert 'idx_student_updated' in indexes, "缺少idx_student_updated索引"
    
    def test_cognitive_profile_indexes(self, initialized_db: sqlite3.Connection):
        """
        测试cognitive_profile表索引
        
        Given: 数据库已初始化
        When: 查询cognitive_profile表的索引
        Then: 应存在所有设计要求的索引
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='cognitive_profile'")
        indexes = {row[0] for row in cursor.fetchall()}
        
        assert 'idx_profile_student' in indexes, "缺少idx_profile_student索引"
        assert 'idx_profile_crystallized' in indexes, "缺少idx_profile_crystallized索引"
    
    def test_homework_indexes(self, initialized_db: sqlite3.Connection):
        """
        测试homework表索引
        
        Given: 数据库已初始化
        When: 查询homework表的索引
        Then: 应存在所有设计要求的索引
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='homework'")
        indexes = {row[0] for row in cursor.fetchall()}
        
        assert 'idx_homework_student' in indexes, "缺少idx_homework_student索引"
        assert 'idx_homework_status' in indexes, "缺少idx_homework_status索引"
        assert 'idx_homework_uploaded' in indexes, "缺少idx_homework_uploaded索引"
    
    def test_question_indexes(self, initialized_db: sqlite3.Connection):
        """
        测试question表索引
        
        Given: 数据库已初始化
        When: 查询question表的索引
        Then: 应存在所有设计要求的索引
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='question'")
        indexes = {row[0] for row in cursor.fetchall()}
        
        assert 'idx_question_homework' in indexes, "缺少idx_question_homework索引"
    
    def test_student_answer_indexes(self, initialized_db: sqlite3.Connection):
        """
        测试student_answer表索引
        
        Given: 数据库已初始化
        When: 查询student_answer表的索引
        Then: 应存在所有设计要求的索引
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='student_answer'")
        indexes = {row[0] for row in cursor.fetchall()}
        
        assert 'idx_answer_student' in indexes, "缺少idx_answer_student索引"
        assert 'idx_answer_question' in indexes, "缺少idx_answer_question索引"
        assert 'idx_answer_correct' in indexes, "缺少idx_answer_correct索引"
    
    def test_error_diagnosis_indexes(self, initialized_db: sqlite3.Connection):
        """
        测试error_diagnosis表索引
        
        Given: 数据库已初始化
        When: 查询error_diagnosis表的索引
        Then: 应存在所有设计要求的索引
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='error_diagnosis'")
        indexes = {row[0] for row in cursor.fetchall()}
        
        assert 'idx_diagnosis_student' in indexes, "缺少idx_diagnosis_student索引"
        assert 'idx_diagnosis_error_type' in indexes, "缺少idx_diagnosis_error_type索引"
        assert 'idx_diagnosis_confidence' in indexes, "缺少idx_diagnosis_confidence索引"
    
    def test_variant_question_indexes(self, initialized_db: sqlite3.Connection):
        """
        测试variant_question表索引
        
        Given: 数据库已初始化
        When: 查询variant_question表的索引
        Then: 应存在所有设计要求的索引
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='variant_question'")
        indexes = {row[0] for row in cursor.fetchall()}
        
        assert 'idx_variant_original' in indexes, "缺少idx_variant_original索引"
        assert 'idx_variant_status' in indexes, "缺少idx_variant_status索引"
    
    def test_cognitive_gap_indexes(self, initialized_db: sqlite3.Connection):
        """
        测试cognitive_gap表索引
        
        Given: 数据库已初始化
        When: 查询cognitive_gap表的索引
        Then: 应存在所有设计要求的索引
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='cognitive_gap'")
        indexes = {row[0] for row in cursor.fetchall()}
        
        assert 'idx_gap_student' in indexes, "缺少idx_gap_student索引"
        assert 'idx_gap_status' in indexes, "缺少idx_gap_status索引"
        assert 'idx_gap_crystallized' in indexes, "缺少idx_gap_crystallized索引"
    
    def test_all_expected_indexes(self, initialized_db: sqlite3.Connection):
        """
        测试所有预期索引是否都存在
        
        Given: 数据库已初始化
        When: 查询所有索引
        Then: 应包含所有设计要求的索引
        """
        cursor = initialized_db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        indexes = {row[0] for row in cursor.fetchall()}
        
        expected_indexes = {
            'idx_student_grade',
            'idx_student_updated',
            'idx_profile_student',
            'idx_profile_crystallized',
            'idx_homework_student',
            'idx_homework_status',
            'idx_homework_uploaded',
            'idx_question_homework',
            'idx_analysis_homework',
            'idx_answer_student',
            'idx_answer_question',
            'idx_answer_correct',
            'idx_trace_answer',
            'idx_diagnosis_student',
            'idx_diagnosis_error_type',
            'idx_diagnosis_confidence',
            'idx_path_diagnosis',
            'idx_variant_original',
            'idx_variant_status',
            'idx_variant_answer_student',
            'idx_variant_answer_result',
            'idx_knowledge_subject_grade',
            'idx_knowledge_parent',
            'idx_dependency_knowledge',
            'idx_dependency_prereq',
            'idx_mastery_student',
            'idx_mastery_level',
            'idx_tag_knowledge',
            'idx_misconception_knowledge',
            'idx_gap_student',
            'idx_gap_status',
            'idx_gap_crystallized',
            'idx_evidence_gap',
            'idx_evidence_diagnosis',
            'idx_description_student',
            'idx_parse_description',
            'idx_parse_confidence',
        }
        
        missing = expected_indexes - indexes
        assert not missing, f"缺少以下索引: {missing}"


@pytest.mark.index
@pytest.mark.db
class TestQueryPerformance:
    """测试索引对查询性能的提升"""
    
    def _insert_test_data(self, db: sqlite3.Connection, count: int = 1000):
        """插入测试数据"""
        cursor = db.cursor()
        
        # 创建学生
        for i in range(10):
            cursor.execute("""
                INSERT INTO student (student_id, name, grade)
                VALUES (?, ?, ?)
            """, (f'stu_perf_{i}', f'Student {i}', '七年级' if i % 2 == 0 else '八年级'))
        
        # 创建作业
        for i in range(count):
            student_id = f'stu_perf_{i % 10}'
            cursor.execute("""
                INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls, uploaded_at)
                VALUES (?, ?, '数学', 1, '[\"test.jpg\"]', datetime('now', ?))
            """, (f'hw_perf_{i}', student_id, f'-{i} days'))
        
        db.commit()
    
    def test_student_grade_index_performance(self, initialized_db: sqlite3.Connection):
        """
        测试student年级索引查询性能
        
        Given: 有大量学生数据
        When: 按年级查询
        Then: 应在合理时间内返回结果
        """
        cursor = initialized_db.cursor()
        
        # 插入测试数据
        for i in range(100):
            cursor.execute("""
                INSERT INTO student (student_id, name, grade)
                VALUES (?, ?, ?)
            """, (f'stu_grade_{i}', f'Student {i}', '七年级' if i % 2 == 0 else '八年级'))
        
        initialized_db.commit()
        
        # 查询并计时
        start = time.time()
        cursor.execute("SELECT COUNT(*) FROM student WHERE grade = '七年级'")
        count = cursor.fetchone()[0]
        elapsed = time.time() - start
        
        assert count == 50, "查询结果数量错误"
        assert elapsed < 1.0, f"查询耗时过长: {elapsed}s"
    
    def test_homework_student_index_performance(self, initialized_db: sqlite3.Connection):
        """
        测试homework学生索引查询性能
        
        Given: 有大量作业数据
        When: 按学生查询作业列表
        Then: 应在合理时间内返回结果
        """
        self._insert_test_data(initialized_db, 500)
        
        cursor = initialized_db.cursor()
        
        # 查询并计时
        start = time.time()
        cursor.execute("""
            SELECT homework_id FROM homework 
            WHERE student_id = 'stu_perf_0' 
            ORDER BY uploaded_at DESC
        """)
        results = cursor.fetchall()
        elapsed = time.time() - start
        
        assert len(results) == 50, f"查询结果数量错误: {len(results)}"
        assert elapsed < 1.0, f"查询耗时过长: {elapsed}s"
    
    def test_cognitive_gap_status_index_performance(self, initialized_db: sqlite3.Connection):
        """
        测试cognitive_gap状态索引查询性能
        
        Given: 有大量认知缺口数据
        When: 按状态查询待处理缺口
        Then: 应在合理时间内返回结果
        """
        cursor = initialized_db.cursor()
        
        # 插入学生和认知缺口
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_gap_perf', 'Test', '七年级')")
        
        for i in range(200):
            status = 'pending' if i % 3 == 0 else ('crystallized' if i % 3 == 1 else 'dismissed')
            cursor.execute("""
                INSERT INTO cognitive_gap (gap_id, student_id, gap_type, status, discovered_at)
                VALUES (?, 'stu_gap_perf', 'concept_gap', ?, datetime('now', ?))
            """, (f'gap_perf_{i}', status, f'-{i} hours'))
        
        initialized_db.commit()
        
        # 查询pending状态
        start = time.time()
        cursor.execute("""
            SELECT gap_id FROM cognitive_gap 
            WHERE status = 'pending' AND discovered_at <= datetime('now', '-24 hours')
        """)
        results = cursor.fetchall()
        elapsed = time.time() - start
        
        assert elapsed < 1.0, f"查询耗时过长: {elapsed}s"


@pytest.mark.index
@pytest.mark.db
class TestUniqueConstraints:
    """测试唯一约束"""
    
    def test_cognitive_profile_student_unique(self, initialized_db: sqlite3.Connection):
        """
        测试cognitive_profile的student_id唯一约束
        
        Given: 已有一个学生的认知画像
        When: 尝试创建同一学生的第二个画像
        Then: 应触发唯一约束错误
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_unique', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO cognitive_profile (profile_id, student_id)
            VALUES ('prof_001', 'stu_unique')
        """)
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO cognitive_profile (profile_id, student_id)
                VALUES ('prof_002', 'stu_unique')
            """)
        
        initialized_db.rollback()
    
    def test_homework_analysis_homework_unique(self, initialized_db: sqlite3.Connection):
        """
        测试homework_analysis的homework_id唯一约束
        
        Given: 已有一个作业的分析
        When: 尝试创建同一作业的第二个分析
        Then: 应触发唯一约束错误
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_hwa', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_unique', 'stu_hwa', '数学', 1, '[\"test.jpg\"]')
        """)
        cursor.execute("""
            INSERT INTO homework_analysis (analysis_id, homework_id)
            VALUES ('ana_001', 'hw_unique')
        """)
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO homework_analysis (analysis_id, homework_id)
                VALUES ('ana_002', 'hw_unique')
            """)
        
        initialized_db.rollback()
    
    def test_knowledge_dependency_unique(self, initialized_db: sqlite3.Connection):
        """
        测试knowledge_dependency的唯一约束
        
        Given: 已存在知识依赖关系
        When: 尝试创建重复的依赖关系
        Then: 应触发唯一约束错误
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("""
            INSERT INTO knowledge_point (knowledge_id, subject, grade_level, knowledge_name)
            VALUES ('k_a', '数学', '七年级', '知识点A')
        """)
        cursor.execute("""
            INSERT INTO knowledge_point (knowledge_id, subject, grade_level, knowledge_name)
            VALUES ('k_b', '数学', '七年级', '知识点B')
        """)
        cursor.execute("""
            INSERT INTO knowledge_dependency (dependency_id, knowledge_id, prerequisite_id)
            VALUES ('dep_001', 'k_a', 'k_b')
        """)
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO knowledge_dependency (dependency_id, knowledge_id, prerequisite_id)
                VALUES ('dep_002', 'k_a', 'k_b')
            """)
        
        initialized_db.rollback()
    
    def test_student_knowledge_mastery_unique(self, initialized_db: sqlite3.Connection):
        """
        测试student_knowledge_mastery的唯一约束
        
        Given: 已存在学生知识掌握度记录
        When: 尝试创建重复的记录
        Then: 应触发唯一约束错误
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_mastery', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO knowledge_point (knowledge_id, subject, grade_level, knowledge_name)
            VALUES ('k_mastery', '数学', '七年级', '测试知识点')
        """)
        cursor.execute("""
            INSERT INTO student_knowledge_mastery (mastery_id, student_id, knowledge_id)
            VALUES ('m_001', 'stu_mastery', 'k_mastery')
        """)
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO student_knowledge_mastery (mastery_id, student_id, knowledge_id)
                VALUES ('m_002', 'stu_mastery', 'k_mastery')
            """)
        
        initialized_db.rollback()
    
    def test_question_knowledge_tag_unique(self, initialized_db: sqlite3.Connection):
        """
        测试question_knowledge_tag的唯一约束
        
        Given: 已存在题目知识点标签
        When: 尝试创建重复的标签
        Then: 应触发唯一约束错误
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_tag', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_tag', 'stu_tag', '数学', 1, '[\"test.jpg\"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_tag', 'hw_tag')")
        cursor.execute("""
            INSERT INTO knowledge_point (knowledge_id, subject, grade_level, knowledge_name)
            VALUES ('k_tag', '数学', '七年级', '测试知识点')
        """)
        cursor.execute("""
            INSERT INTO question_knowledge_tag (tag_id, question_id, knowledge_id)
            VALUES ('t_001', 'q_tag', 'k_tag')
        """)
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO question_knowledge_tag (tag_id, question_id, knowledge_id)
                VALUES ('t_002', 'q_tag', 'k_tag')
            """)
        
        initialized_db.rollback()
