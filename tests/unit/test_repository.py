"""
CRUD测试

测试创建、读取、更新、删除操作以及批量操作、分页查询
"""

import pytest
import sqlite3
from typing import List, Dict, Any
from datetime import datetime, timedelta


@pytest.mark.crud
@pytest.mark.db
class TestStudentCRUD:
    """测试学生表的CRUD操作"""
    
    def test_create_student(self, initialized_db: sqlite3.Connection, sample_student_data: dict):
        """
        测试创建学生
        
        Given: 学生数据
        When: 插入到student表
        Then: 应成功创建并返回正确数据
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("""
            INSERT INTO student (student_id, name, grade, preferred_subjects)
            VALUES (?, ?, ?, ?)
        """, (
            sample_student_data["student_id"],
            sample_student_data["name"],
            sample_student_data["grade"],
            sample_student_data["preferred_subjects"]
        ))
        
        initialized_db.commit()
        
        # 验证插入
        cursor.execute("SELECT * FROM student WHERE student_id = ?", (sample_student_data["student_id"],))
        row = cursor.fetchone()
        
        assert row is not None, "学生应已创建"
        assert row[1] == sample_student_data["name"], "姓名不匹配"
        assert row[2] == sample_student_data["grade"], "年级不匹配"
    
    def test_read_student(self, initialized_db: sqlite3.Connection):
        """
        测试读取学生
        
        Given: 已存在学生记录
        When: 查询该学生
        Then: 应返回正确的学生数据
        """
        cursor = initialized_db.cursor()
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_read', 'Test Read', '七年级')")
        initialized_db.commit()
        
        cursor.execute("SELECT student_id, name, grade FROM student WHERE student_id = 'stu_read'")
        row = cursor.fetchone()
        
        assert row is not None, "应找到学生"
        assert row[0] == 'stu_read'
        assert row[1] == 'Test Read'
        assert row[2] == '七年级'
    
    def test_update_student(self, initialized_db: sqlite3.Connection):
        """
        测试更新学生
        
        Given: 已存在学生记录
        When: 更新学生信息
        Then: 应成功更新并返回新数据
        """
        cursor = initialized_db.cursor()
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_update', 'Old Name', '七年级')")
        initialized_db.commit()
        
        # 更新
        cursor.execute("""
            UPDATE student SET name = 'New Name', grade = '八年级', preferred_subjects = '["数学"]'
            WHERE student_id = 'stu_update'
        """)
        initialized_db.commit()
        
        # 验证更新
        cursor.execute("SELECT name, grade, preferred_subjects FROM student WHERE student_id = 'stu_update'")
        row = cursor.fetchone()
        
        assert row[0] == 'New Name', "姓名未更新"
        assert row[1] == '八年级', "年级未更新"
        assert row[2] == '["数学"]', "偏好未更新"
    
    def test_delete_student(self, initialized_db: sqlite3.Connection):
        """
        测试删除学生
        
        Given: 已存在学生记录
        When: 删除该学生
        Then: 应成功删除且记录不存在
        """
        cursor = initialized_db.cursor()
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_delete', 'To Delete', '七年级')")
        initialized_db.commit()
        
        # 删除
        cursor.execute("DELETE FROM student WHERE student_id = 'stu_delete'")
        initialized_db.commit()
        
        # 验证删除
        cursor.execute("SELECT COUNT(*) FROM student WHERE student_id = 'stu_delete'")
        count = cursor.fetchone()[0]
        
        assert count == 0, "学生应已删除"


@pytest.mark.crud
@pytest.mark.db
class TestHomeworkCRUD:
    """测试作业表的CRUD操作"""
    
    def test_create_homework_with_student(self, initialized_db: sqlite3.Connection):
        """
        测试创建作业（关联学生）
        
        Given: 学生已存在
        When: 创建关联的作业
        Then: 应成功创建并正确关联
        """
        cursor = initialized_db.cursor()
        
        # 创建学生
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_hw', 'Test', '七年级')")
        
        # 创建作业
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_001', 'stu_hw', '数学', 3, '["img1.jpg", "img2.jpg"]')
        """)
        initialized_db.commit()
        
        # 验证
        cursor.execute("SELECT subject, page_count FROM homework WHERE homework_id = 'hw_001'")
        row = cursor.fetchone()
        
        assert row[0] == '数学'
        assert row[1] == 3
    
    def test_update_homework_status(self, initialized_db: sqlite3.Connection):
        """
        测试更新作业状态
        
        Given: 作业已存在
        When: 更新作业状态为archived
        Then: 应成功更新并设置archived_at
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_arch', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls, status)
            VALUES ('hw_arch', 'stu_arch', '数学', 1, '["test.jpg"]', 'active')
        """)
        initialized_db.commit()
        
        # 更新状态
        cursor.execute("""
            UPDATE homework 
            SET status = 'archived', archived_at = datetime('now')
            WHERE homework_id = 'hw_arch'
        """)
        initialized_db.commit()
        
        # 验证
        cursor.execute("SELECT status, archived_at FROM homework WHERE homework_id = 'hw_arch'")
        row = cursor.fetchone()
        
        assert row[0] == 'archived'
        assert row[1] is not None


@pytest.mark.crud
@pytest.mark.db
class TestQuestionCRUD:
    """测试题目表的CRUD操作"""
    
    def test_create_question_with_homework(self, initialized_db: sqlite3.Connection):
        """
        测试创建题目（关联作业）
        
        Given: 作业已存在
        When: 创建关联的题目
        Then: 应成功创建
        """
        cursor = initialized_db.cursor()
        
        # 创建基础数据
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_q', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_q', 'stu_q', '数学', 1, '["test.jpg"]')
        """)
        
        # 创建题目
        cursor.execute("""
            INSERT INTO question (question_id, homework_id, ocr_text, question_number, difficulty_level)
            VALUES ('q_001', 'hw_q', '2 + 2 = ?', 1, 'easy')
        """)
        initialized_db.commit()
        
        # 验证
        cursor.execute("SELECT ocr_text, difficulty_level FROM question WHERE question_id = 'q_001'")
        row = cursor.fetchone()
        
        assert row[0] == '2 + 2 = ?'
        assert row[1] == 'easy'
    
    def test_batch_create_questions(self, initialized_db: sqlite3.Connection):
        """
        测试批量创建题目
        
        Given: 作业已存在
        When: 批量插入多道题目
        Then: 应成功创建所有题目
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_batch', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_batch', 'stu_batch', '数学', 5, '["test.jpg"]')
        """)
        
        # 批量插入
        questions = [
            ('q_batch_1', 'hw_batch', '1 + 1 = ?', 1),
            ('q_batch_2', 'hw_batch', '2 + 2 = ?', 2),
            ('q_batch_3', 'hw_batch', '3 + 3 = ?', 3),
            ('q_batch_4', 'hw_batch', '4 + 4 = ?', 4),
            ('q_batch_5', 'hw_batch', '5 + 5 = ?', 5),
        ]
        
        cursor.executemany("""
            INSERT INTO question (question_id, homework_id, ocr_text, question_number)
            VALUES (?, ?, ?, ?)
        """, questions)
        initialized_db.commit()
        
        # 验证
        cursor.execute("SELECT COUNT(*) FROM question WHERE homework_id = 'hw_batch'")
        count = cursor.fetchone()[0]
        
        assert count == 5, f"应创建5道题目，实际创建{count}道"


@pytest.mark.crud
@pytest.mark.db
class TestAnswerCRUD:
    """测试答案表的CRUD操作"""
    
    def test_create_answer(self, initialized_db: sqlite3.Connection):
        """
        测试创建答案
        
        Given: 学生和题目已存在
        When: 创建答案
        Then: 应成功创建
        """
        cursor = initialized_db.cursor()
        
        # 创建基础数据
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_ans', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_ans', 'stu_ans', '数学', 1, '["test.jpg"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_ans', 'hw_ans')")
        
        # 创建答案
        cursor.execute("""
            INSERT INTO student_answer (answer_id, question_id, student_id, answer_content, is_correct, confidence_score)
            VALUES ('ans_001', 'q_ans', 'stu_ans', '4', 1, 0.95)
        """)
        initialized_db.commit()
        
        # 验证
        cursor.execute("SELECT answer_content, is_correct, confidence_score FROM student_answer WHERE answer_id = 'ans_001'")
        row = cursor.fetchone()
        
        assert row[0] == '4'
        assert row[1] == 1
        assert row[2] == 0.95


@pytest.mark.crud
@pytest.mark.db
class TestDiagnosisCRUD:
    """测试诊断表的CRUD操作"""
    
    def test_create_diagnosis(self, initialized_db: sqlite3.Connection):
        """
        测试创建诊断
        
        Given: 答案已存在
        When: 创建诊断
        Then: 应成功创建
        """
        cursor = initialized_db.cursor()
        
        # 创建基础数据
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_diag', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_diag', 'stu_diag', '数学', 1, '["test.jpg"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_diag', 'hw_diag')")
        cursor.execute("""
            INSERT INTO student_answer (answer_id, question_id, student_id, answer_content)
            VALUES ('ans_diag', 'q_diag', 'stu_diag', '3')
        """)
        
        # 创建诊断
        cursor.execute("""
            INSERT INTO error_diagnosis (diagnosis_id, answer_id, question_id, student_id, error_type, knowledge_tags, confidence_score)
            VALUES ('diag_001', 'ans_diag', 'q_diag', 'stu_diag', 'careless', '["加法运算"]', 0.85)
        """)
        initialized_db.commit()
        
        # 验证
        cursor.execute("SELECT error_type, confidence_score FROM error_diagnosis WHERE diagnosis_id = 'diag_001'")
        row = cursor.fetchone()
        
        assert row[0] == 'careless'
        assert row[1] == 0.85
    
    def test_create_diagnosis_path(self, initialized_db: sqlite3.Connection):
        """
        测试创建诊断路径
        
        Given: 诊断已存在
        When: 创建诊断路径步骤
        Then: 应成功创建
        """
        cursor = initialized_db.cursor()
        
        # 创建基础数据链
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_path', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_path', 'stu_path', '数学', 1, '["test.jpg"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_path', 'hw_path')")
        cursor.execute("""
            INSERT INTO student_answer (answer_id, question_id, student_id, answer_content)
            VALUES ('ans_path', 'q_path', 'stu_path', '3')
        """)
        cursor.execute("""
            INSERT INTO error_diagnosis (diagnosis_id, answer_id, question_id, student_id, error_type)
            VALUES ('diag_path', 'ans_path', 'q_path', 'stu_path', 'careless')
        """)
        
        # 创建诊断路径
        cursor.execute("""
            INSERT INTO diagnosis_path (path_id, diagnosis_id, step_number, option_selected, reasoning)
            VALUES ('p_001', 'diag_path', 1, 'A', '计算步骤有误')
        """)
        cursor.execute("""
            INSERT INTO diagnosis_path (path_id, diagnosis_id, step_number, option_selected, reasoning)
            VALUES ('p_002', 'diag_path', 2, 'B', '进位错误')
        """)
        initialized_db.commit()
        
        # 验证
        cursor.execute("SELECT COUNT(*) FROM diagnosis_path WHERE diagnosis_id = 'diag_path'")
        count = cursor.fetchone()[0]
        
        assert count == 2


@pytest.mark.crud
@pytest.mark.db
class TestVariantCRUD:
    """测试变形题表的CRUD操作"""
    
    def test_create_variant_question(self, initialized_db: sqlite3.Connection):
        """
        测试创建变形题
        
        Given: 原题已存在
        When: 创建变形题
        Then: 应成功创建
        """
        cursor = initialized_db.cursor()
        
        # 创建基础数据
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_var', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_var', 'stu_var', '数学', 1, '["test.jpg"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id, ocr_text) VALUES ('q_var', 'hw_var', '2 + 3 = ?')")
        
        # 创建变形题
        cursor.execute("""
            INSERT INTO variant_question (variant_id, original_question_id, variant_type, variant_content)
            VALUES ('var_001', 'q_var', 'numeric_change', '4 + 5 = ?')
        """)
        initialized_db.commit()
        
        # 验证
        cursor.execute("SELECT variant_type, validation_status FROM variant_question WHERE variant_id = 'var_001'")
        row = cursor.fetchone()
        
        assert row[0] == 'numeric_change'
        assert row[1] == 'pending'  # 默认值
    
    def test_create_variant_answer(self, initialized_db: sqlite3.Connection):
        """
        测试创建变形题答案
        
        Given: 变形题和学生已存在
        When: 创建变形题答案
        Then: 应成功创建
        """
        cursor = initialized_db.cursor()
        
        # 创建基础数据
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_var_ans', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_var_ans', 'stu_var_ans', '数学', 1, '["test.jpg"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_var_ans', 'hw_var_ans')")
        cursor.execute("""
            INSERT INTO variant_question (variant_id, original_question_id, variant_type, variant_content)
            VALUES ('var_ans', 'q_var_ans', 'numeric_change', '2 + 2 = ?')
        """)
        
        # 创建答案
        cursor.execute("""
            INSERT INTO variant_answer (variant_answer_id, variant_id, student_id, answer_content, is_correct)
            VALUES ('var_ans_001', 'var_ans', 'stu_var_ans', '4', 1)
        """)
        initialized_db.commit()
        
        # 验证
        cursor.execute("SELECT answer_content, is_correct FROM variant_answer WHERE variant_answer_id = 'var_ans_001'")
        row = cursor.fetchone()
        
        assert row[0] == '4'
        assert row[1] == 1


@pytest.mark.crud
@pytest.mark.db
class TestKnowledgeCRUD:
    """测试知识图谱表的CRUD操作"""
    
    def test_create_knowledge_point(self, initialized_db: sqlite3.Connection):
        """
        测试创建知识点
        
        Given: 无依赖
        When: 创建知识点
        Then: 应成功创建
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("""
            INSERT INTO knowledge_point (knowledge_id, subject, grade_level, knowledge_name, description)
            VALUES ('k_001', '数学', '七年级', '一元一次方程', '形如ax + b = c的方程')
        """)
        initialized_db.commit()
        
        cursor.execute("SELECT subject, knowledge_name FROM knowledge_point WHERE knowledge_id = 'k_001'")
        row = cursor.fetchone()
        
        assert row[0] == '数学'
        assert row[1] == '一元一次方程'
    
    def test_create_knowledge_dependency(self, initialized_db: sqlite3.Connection):
        """
        测试创建知识依赖
        
        Given: 两个知识点已存在
        When: 创建依赖关系
        Then: 应成功创建
        """
        cursor = initialized_db.cursor()
        
        # 创建知识点
        cursor.execute("""
            INSERT INTO knowledge_point (knowledge_id, subject, grade_level, knowledge_name)
            VALUES ('k_pre', '数学', '七年级', '整数运算')
        """)
        cursor.execute("""
            INSERT INTO knowledge_point (knowledge_id, subject, grade_level, knowledge_name)
            VALUES ('k_post', '数学', '七年级', '分数运算')
        """)
        
        # 创建依赖关系
        cursor.execute("""
            INSERT INTO knowledge_dependency (dependency_id, knowledge_id, prerequisite_id, dependency_strength)
            VALUES ('dep_001', 'k_post', 'k_pre', 0.8)
        """)
        initialized_db.commit()
        
        # 验证
        cursor.execute("SELECT dependency_strength FROM knowledge_dependency WHERE dependency_id = 'dep_001'")
        row = cursor.fetchone()
        
        assert row[0] == 0.8
    
    def test_create_student_mastery(self, initialized_db: sqlite3.Connection):
        """
        测试创建学生知识掌握度
        
        Given: 学生和知识点已存在
        When: 创建掌握度记录
        Then: 应成功创建
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_mastery', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO knowledge_point (knowledge_id, subject, grade_level, knowledge_name)
            VALUES ('k_mastery', '数学', '七年级', '加法运算')
        """)
        cursor.execute("""
            INSERT INTO student_knowledge_mastery (mastery_id, student_id, knowledge_id, mastery_level, practice_count)
            VALUES ('m_001', 'stu_mastery', 'k_mastery', 0.75, 10)
        """)
        initialized_db.commit()
        
        cursor.execute("SELECT mastery_level, practice_count FROM student_knowledge_mastery WHERE mastery_id = 'm_001'")
        row = cursor.fetchone()
        
        assert row[0] == 0.75
        assert row[1] == 10


@pytest.mark.crud
@pytest.mark.db
class TestCognitiveGapCRUD:
    """测试认知缺口表的CRUD操作"""
    
    def test_create_cognitive_gap(self, initialized_db: sqlite3.Connection):
        """
        测试创建认知缺口
        
        Given: 学生已存在
        When: 创建认知缺口
        Then: 应成功创建
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_gap', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO cognitive_gap (gap_id, student_id, gap_type, related_knowledge)
            VALUES ('gap_001', 'stu_gap', 'concept_gap', '["k_001", "k_002"]')
        """)
        initialized_db.commit()
        
        cursor.execute("SELECT gap_type, status, occurrence_count FROM cognitive_gap WHERE gap_id = 'gap_001'")
        row = cursor.fetchone()
        
        assert row[0] == 'concept_gap'
        assert row[1] == 'pending'  # 默认值
        assert row[2] == 1  # 默认值
    
    def test_create_gap_evidence(self, initialized_db: sqlite3.Connection):
        """
        测试创建缺口证据
        
        Given: 认知缺口和诊断已存在
        When: 创建证据
        Then: 应成功创建
        """
        cursor = initialized_db.cursor()
        
        # 创建基础数据链
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_ev', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_ev', 'stu_ev', '数学', 1, '["test.jpg"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_ev', 'hw_ev')")
        cursor.execute("""
            INSERT INTO student_answer (answer_id, question_id, student_id, answer_content)
            VALUES ('ans_ev', 'q_ev', 'stu_ev', 'test')
        """)
        cursor.execute("""
            INSERT INTO error_diagnosis (diagnosis_id, answer_id, question_id, student_id, error_type)
            VALUES ('diag_ev', 'ans_ev', 'q_ev', 'stu_ev', 'careless')
        """)
        cursor.execute("""
            INSERT INTO cognitive_gap (gap_id, student_id, gap_type)
            VALUES ('gap_ev', 'stu_ev', 'concept_gap')
        """)
        
        # 创建证据
        cursor.execute("""
            INSERT INTO gap_evidence (evidence_id, gap_id, diagnosis_id, evidence_type)
            VALUES ('ev_001', 'gap_ev', 'diag_ev', 'initial_diagnosis')
        """)
        initialized_db.commit()
        
        cursor.execute("SELECT evidence_type FROM gap_evidence WHERE evidence_id = 'ev_001'")
        row = cursor.fetchone()
        
        assert row[0] == 'initial_diagnosis'


@pytest.mark.crud
@pytest.mark.db
class TestPagination:
    """测试分页查询"""
    
    def test_student_list_pagination(self, initialized_db: sqlite3.Connection):
        """
        测试学生列表分页查询
        
        Given: 有多条学生记录
        When: 分页查询
        Then: 应正确返回分页结果
        """
        cursor = initialized_db.cursor()
        
        # 插入50条学生记录
        for i in range(50):
            cursor.execute("""
                INSERT INTO student (student_id, name, grade)
                VALUES (?, ?, ?)
            """, (f'stu_page_{i}', f'Student {i}', '七年级' if i % 2 == 0 else '八年级'))
        
        initialized_db.commit()
        
        # 分页查询 - 第1页，每页10条
        cursor.execute("""
            SELECT student_id, name FROM student
            ORDER BY student_id
            LIMIT 10 OFFSET 0
        """)
        page1 = cursor.fetchall()
        
        assert len(page1) == 10, "第1页应有10条记录"
        
        # 分页查询 - 第2页
        cursor.execute("""
            SELECT student_id, name FROM student
            ORDER BY student_id
            LIMIT 10 OFFSET 10
        """)
        page2 = cursor.fetchall()
        
        assert len(page2) == 10, "第2页应有10条记录"
        assert page1[0][0] != page2[0][0], "两页数据应不同"
    
    def test_homework_by_student_pagination(self, initialized_db: sqlite3.Connection):
        """
        测试按学生查询作业分页
        
        Given: 学生有多条作业记录
        When: 分页查询
        Then: 应正确返回分页结果
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_hw_page', 'Test', '七年级')")
        
        # 插入30条作业记录
        for i in range(30):
            cursor.execute("""
                INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls, uploaded_at)
                VALUES (?, 'stu_hw_page', '数学', 1, '["test.jpg"]', datetime('now', ?))
            """, (f'hw_page_{i}', f'-{i} days'))
        
        initialized_db.commit()
        
        # 查询前10条，按时间倒序
        cursor.execute("""
            SELECT homework_id FROM homework
            WHERE student_id = 'stu_hw_page'
            ORDER BY uploaded_at DESC
            LIMIT 10
        """)
        results = cursor.fetchall()
        
        assert len(results) == 10


@pytest.mark.crud
@pytest.mark.db
class TestBatchOperations:
    """测试批量操作"""
    
    def test_batch_insert_students(self, initialized_db: sqlite3.Connection):
        """
        测试批量插入学生
        
        Given: 多条学生数据
        When: 批量插入
        Then: 应成功插入所有记录
        """
        cursor = initialized_db.cursor()
        
        students = [
            (f'stu_batch_{i}', f'Student {i}', '七年级')
            for i in range(100)
        ]
        
        cursor.executemany("""
            INSERT INTO student (student_id, name, grade)
            VALUES (?, ?, ?)
        """, students)
        
        initialized_db.commit()
        
        cursor.execute("SELECT COUNT(*) FROM student WHERE student_id LIKE 'stu_batch_%'")
        count = cursor.fetchone()[0]
        
        assert count == 100, f"应插入100条记录，实际插入{count}条"
    
    def test_batch_update_status(self, initialized_db: sqlite3.Connection):
        """
        测试批量更新状态
        
        Given: 多条认知缺口记录
        When: 批量更新状态
        Then: 应成功更新所有记录
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_batch_up', 'Test', '七年级')")
        
        # 创建多条pending状态的gap
        for i in range(10):
            cursor.execute("""
                INSERT INTO cognitive_gap (gap_id, student_id, gap_type, status)
                VALUES (?, 'stu_batch_up', 'concept_gap', 'pending')
            """, (f'gap_batch_{i}',))
        
        initialized_db.commit()
        
        # 批量更新为crystallized
        cursor.execute("""
            UPDATE cognitive_gap 
            SET status = 'crystallized', crystallized_at = datetime('now')
            WHERE student_id = 'stu_batch_up' AND status = 'pending'
        """)
        initialized_db.commit()
        
        cursor.execute("SELECT COUNT(*) FROM cognitive_gap WHERE student_id = 'stu_batch_up' AND status = 'crystallized'")
        count = cursor.fetchone()[0]
        
        assert count == 10, f"应更新10条记录，实际更新{count}条"
    
    def test_batch_delete(self, initialized_db: sqlite3.Connection):
        """
        测试批量删除
        
        Given: 多条作业记录
        When: 批量删除
        Then: 应成功删除所有匹配记录
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_batch_del', 'Test', '七年级')")
        
        # 创建多条作业
        for i in range(20):
            cursor.execute("""
                INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls, uploaded_at)
                VALUES (?, 'stu_batch_del', '数学', 1, '["test.jpg"]', datetime('now', ?))
            """, (f'hw_batch_{i}', f'-{i} days'))
        
        initialized_db.commit()
        
        # 批量删除30天前的作业
        cursor.execute("""
            DELETE FROM homework
            WHERE student_id = 'stu_batch_del' AND uploaded_at <= datetime('now', '-15 days')
        """)
        initialized_db.commit()
        
        cursor.execute("SELECT COUNT(*) FROM homework WHERE student_id = 'stu_batch_del'")
        count = cursor.fetchone()[0]
        
        # 16-19天前的记录应该被删除（约5条）
        assert count < 20, f"应有记录被删除，剩余{count}条"
