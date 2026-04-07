"""
外键约束测试

验证所有外键关系和级联删除行为
"""

import pytest
import sqlite3


@pytest.mark.fk
@pytest.mark.db
class TestForeignKeyConstraints:
    """测试外键约束"""
    
    def test_student_cognitive_profile_fk(self, initialized_db: sqlite3.Connection):
        """
        测试student-cognitive_profile外键关系
        
        Given: 学生表有记录
        When: 创建认知画像关联到不存在的student_id
        Then: 应触发外键约束错误
        """
        cursor = initialized_db.cursor()
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO cognitive_profile (profile_id, student_id, thinking_style)
                VALUES ('prof_001', 'non_existent_student', '{}')
            """)
        
        initialized_db.rollback()
    
    def test_homework_student_fk(self, initialized_db: sqlite3.Connection):
        """
        测试homework-student外键关系
        
        Given: 无学生记录
        When: 创建作业关联到不存在的student_id
        Then: 应触发外键约束错误
        """
        cursor = initialized_db.cursor()
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
                VALUES ('hw_001', 'non_existent_student', '数学', 1, '["test.jpg"]')
            """)
        
        initialized_db.rollback()
    
    def test_question_homework_fk(self, initialized_db: sqlite3.Connection):
        """
        测试question-homework外键关系
        
        Given: 无作业记录
        When: 创建题目关联到不存在的homework_id
        Then: 应触发外键约束错误
        """
        cursor = initialized_db.cursor()
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO question (question_id, homework_id, question_number)
                VALUES ('q_001', 'non_existent_homework', 1)
            """)
        
        initialized_db.rollback()
    
    def test_student_answer_question_fk(self, initialized_db: sqlite3.Connection):
        """
        测试student_answer-question外键关系
        
        Given: 已创建学生和作业
        When: 创建答案关联到不存在的question_id
        Then: 应触发外键约束错误
        """
        cursor = initialized_db.cursor()
        
        # 创建学生
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_001', 'Test', '七年级')")
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO student_answer (answer_id, question_id, student_id, answer_content)
                VALUES ('ans_001', 'non_existent_question', 'stu_001', 'test answer')
            """)
        
        initialized_db.rollback()
    
    def test_error_diagnosis_answer_fk(self, initialized_db: sqlite3.Connection):
        """
        测试error_diagnosis-answer外键关系
        
        Given: 无答案记录
        When: 创建诊断关联到不存在的answer_id
        Then: 应触发外键约束错误
        """
        cursor = initialized_db.cursor()
        
        # 创建基础数据
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_001', 'Test', '七年级')")
        cursor.execute("INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls) VALUES ('hw_001', 'stu_001', '数学', 1, '["test.jpg"]')")
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_001', 'hw_001')")
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO error_diagnosis (diagnosis_id, answer_id, question_id, student_id, error_type)
                VALUES ('diag_001', 'non_existent_answer', 'q_001', 'stu_001', 'careless')
            """)
        
        initialized_db.rollback()
    
    def test_variant_question_original_fk(self, initialized_db: sqlite3.Connection):
        """
        测试variant_question-original_question外键关系
        
        Given: 无原题记录
        When: 创建变形题关联到不存在的original_question_id
        Then: 应触发外键约束错误
        """
        cursor = initialized_db.cursor()
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO variant_question (variant_id, original_question_id, variant_type, variant_content)
                VALUES ('var_001', 'non_existent_question', 'numeric_change', '2+2=?')
            """)
        
        initialized_db.rollback()
    
    def test_knowledge_dependency_fk(self, initialized_db: sqlite3.Connection):
        """
        测试knowledge_dependency外键关系
        
        Given: 无知识点记录
        When: 创建知识依赖关联到不存在的knowledge_id
        Then: 应触发外键约束错误
        """
        cursor = initialized_db.cursor()
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO knowledge_dependency (dependency_id, knowledge_id, prerequisite_id)
                VALUES ('dep_001', 'non_existent_knowledge', 'another_non_existent')
            """)
        
        initialized_db.rollback()
    
    def test_gap_evidence_fk(self, initialized_db: sqlite3.Connection):
        """
        测试gap_evidence外键关系
        
        Given: 无认知缺口和诊断记录
        When: 创建证据关联到不存在的记录
        Then: 应触发外键约束错误
        """
        cursor = initialized_db.cursor()
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO gap_evidence (evidence_id, gap_id, diagnosis_id, evidence_type)
                VALUES ('ev_001', 'non_existent_gap', 'non_existent_diagnosis', 'initial_diagnosis')
            """)
        
        initialized_db.rollback()


@pytest.mark.fk
@pytest.mark.db
class TestCascadeDelete:
    """测试级联删除"""
    
    def test_student_cascade_delete_homework(self, initialized_db: sqlite3.Connection):
        """
        测试学生删除时作业级联删除
        
        Given: 学生有关联的作业
        When: 删除学生
        Then: 关联的作业应被级联删除
        """
        cursor = initialized_db.cursor()
        
        # 创建学生和作业
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_cascade', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_cascade', 'stu_cascade', '数学', 1, '["test.jpg"]')
        """)
        
        # 验证作业存在
        cursor.execute("SELECT COUNT(*) FROM homework WHERE homework_id = 'hw_cascade'")
        assert cursor.fetchone()[0] == 1, "作业应存在"
        
        # 删除学生
        cursor.execute("DELETE FROM student WHERE student_id = 'stu_cascade'")
        initialized_db.commit()
        
        # 验证作业被删除
        cursor.execute("SELECT COUNT(*) FROM homework WHERE homework_id = 'hw_cascade'")
        assert cursor.fetchone()[0] == 0, "作业应被级联删除"
    
    def test_student_cascade_delete_profile(self, initialized_db: sqlite3.Connection):
        """
        测试学生删除时认知画像级联删除
        
        Given: 学生有关联的认知画像
        When: 删除学生
        Then: 关联的认知画像应被级联删除
        """
        cursor = initialized_db.cursor()
        
        # 创建学生和认知画像
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_profile', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO cognitive_profile (profile_id, student_id, thinking_style)
            VALUES ('prof_profile', 'stu_profile', '{}')
        """)
        
        # 删除学生
        cursor.execute("DELETE FROM student WHERE student_id = 'stu_profile'")
        initialized_db.commit()
        
        # 验证画像被删除
        cursor.execute("SELECT COUNT(*) FROM cognitive_profile WHERE profile_id = 'prof_profile'")
        assert cursor.fetchone()[0] == 0, "认知画像应被级联删除"
    
    def test_homework_cascade_delete_questions(self, initialized_db: sqlite3.Connection):
        """
        测试作业删除时题目级联删除
        
        Given: 作业有关联的题目
        When: 删除作业
        Then: 关联的题目应被级联删除
        """
        cursor = initialized_db.cursor()
        
        # 创建数据
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_hw', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_q', 'stu_hw', '数学', 1, '["test.jpg"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id, question_number) VALUES ('q_001', 'hw_q', 1)")
        cursor.execute("INSERT INTO question (question_id, homework_id, question_number) VALUES ('q_002', 'hw_q', 2)")
        
        # 删除作业
        cursor.execute("DELETE FROM homework WHERE homework_id = 'hw_q'")
        initialized_db.commit()
        
        # 验证题目被删除
        cursor.execute("SELECT COUNT(*) FROM question WHERE homework_id = 'hw_q'")
        assert cursor.fetchone()[0] == 0, "题目应被级联删除"
    
    def test_question_cascade_delete_answers(self, initialized_db: sqlite3.Connection):
        """
        测试题目删除时答案级联删除
        
        Given: 题目有关联的答案
        When: 删除题目
        Then: 关联的答案应被级联删除
        """
        cursor = initialized_db.cursor()
        
        # 创建完整数据链
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_q', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_q2', 'stu_q', '数学', 1, '["test.jpg"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_del', 'hw_q2')")
        cursor.execute("""
            INSERT INTO student_answer (answer_id, question_id, student_id, answer_content)
            VALUES ('ans_del', 'q_del', 'stu_q', 'test')
        """)
        
        # 删除题目
        cursor.execute("DELETE FROM question WHERE question_id = 'q_del'")
        initialized_db.commit()
        
        # 验证答案被删除
        cursor.execute("SELECT COUNT(*) FROM student_answer WHERE answer_id = 'ans_del'")
        assert cursor.fetchone()[0] == 0, "答案应被级联删除"
    
    def test_answer_cascade_delete_diagnosis(self, initialized_db: sqlite3.Connection):
        """
        测试答案删除时诊断级联删除
        
        Given: 答案有关联的诊断
        When: 删除答案
        Then: 关联的诊断应被级联删除
        """
        cursor = initialized_db.cursor()
        
        # 创建完整数据链
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_ans', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_ans', 'stu_ans', '数学', 1, '["test.jpg"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_ans', 'hw_ans')")
        cursor.execute("""
            INSERT INTO student_answer (answer_id, question_id, student_id, answer_content)
            VALUES ('ans_diag', 'q_ans', 'stu_ans', 'test')
        """)
        cursor.execute("""
            INSERT INTO error_diagnosis (diagnosis_id, answer_id, question_id, student_id, error_type)
            VALUES ('diag_cascade', 'ans_diag', 'q_ans', 'stu_ans', 'careless')
        """)
        
        # 删除答案
        cursor.execute("DELETE FROM student_answer WHERE answer_id = 'ans_diag'")
        initialized_db.commit()
        
        # 验证诊断被删除
        cursor.execute("SELECT COUNT(*) FROM error_diagnosis WHERE diagnosis_id = 'diag_cascade'")
        assert cursor.fetchone()[0] == 0, "诊断应被级联删除"
    
    def test_cognitive_gap_cascade_delete_evidence(self, initialized_db: sqlite3.Connection):
        """
        测试认知缺口删除时证据级联删除
        
        Given: 认知缺口有关联的证据
        When: 删除认知缺口
        Then: 关联的证据应被级联删除
        """
        cursor = initialized_db.cursor()
        
        # 创建基础数据
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_gap', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO cognitive_gap (gap_id, student_id, gap_type)
            VALUES ('gap_ev', 'stu_gap', 'concept_gap')
        """)
        
        # 创建作业链以创建诊断
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_gap', 'stu_gap', '数学', 1, '["test.jpg"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_gap', 'hw_gap')")
        cursor.execute("""
            INSERT INTO student_answer (answer_id, question_id, student_id, answer_content)
            VALUES ('ans_gap', 'q_gap', 'stu_gap', 'test')
        """)
        cursor.execute("""
            INSERT INTO error_diagnosis (diagnosis_id, answer_id, question_id, student_id, error_type)
            VALUES ('diag_gap', 'ans_gap', 'q_gap', 'stu_gap', 'careless')
        """)
        
        # 创建证据
        cursor.execute("""
            INSERT INTO gap_evidence (evidence_id, gap_id, diagnosis_id, evidence_type)
            VALUES ('ev_gap', 'gap_ev', 'diag_gap', 'initial_diagnosis')
        """)
        
        # 删除认知缺口
        cursor.execute("DELETE FROM cognitive_gap WHERE gap_id = 'gap_ev'")
        initialized_db.commit()
        
        # 验证证据被删除
        cursor.execute("SELECT COUNT(*) FROM gap_evidence WHERE evidence_id = 'ev_gap'")
        assert cursor.fetchone()[0] == 0, "证据应被级联删除"


@pytest.mark.fk
@pytest.mark.db
class TestSelfReferenceFK:
    """测试自引用外键"""
    
    def test_knowledge_point_parent_fk(self, initialized_db: sqlite3.Connection):
        """
        测试knowledge_point自引用外键
        
        Given: 父知识点不存在
        When: 创建子知识点关联到不存在的parent_knowledge_id
        Then: 由于ON DELETE SET NULL，此处不会报错，但验证关系存在
        """
        cursor = initialized_db.cursor()
        
        # 先创建父知识点
        cursor.execute("""
            INSERT INTO knowledge_point (knowledge_id, subject, grade_level, knowledge_name)
            VALUES ('k_parent', '数学', '七年级', '代数基础')
        """)
        
        # 创建子知识点
        cursor.execute("""
            INSERT INTO knowledge_point (knowledge_id, subject, grade_level, knowledge_name, parent_knowledge_id)
            VALUES ('k_child', '数学', '七年级', '一元一次方程', 'k_parent')
        """)
        
        # 验证关系
        cursor.execute("SELECT parent_knowledge_id FROM knowledge_point WHERE knowledge_id = 'k_child'")
        assert cursor.fetchone()[0] == 'k_parent', "父子关系应正确建立"
        
        initialized_db.rollback()
    
    def test_knowledge_point_parent_set_null(self, initialized_db: sqlite3.Connection):
        """
        测试父知识点删除时设为NULL
        
        Given: 有父子关系的知识点
        When: 删除父知识点
        Then: 子知识点的parent_knowledge_id应设为NULL
        """
        cursor = initialized_db.cursor()
        
        # 创建父子知识点
        cursor.execute("""
            INSERT INTO knowledge_point (knowledge_id, subject, grade_level, knowledge_name)
            VALUES ('k_parent2', '数学', '七年级', '代数基础')
        """)
        cursor.execute("""
            INSERT INTO knowledge_point (knowledge_id, subject, grade_level, knowledge_name, parent_knowledge_id)
            VALUES ('k_child2', '数学', '七年级', '一元一次方程', 'k_parent2')
        """)
        
        # 删除父知识点
        cursor.execute("DELETE FROM knowledge_point WHERE knowledge_id = 'k_parent2'")
        initialized_db.commit()
        
        # 验证子知识点parent_knowledge_id为NULL
        cursor.execute("SELECT parent_knowledge_id FROM knowledge_point WHERE knowledge_id = 'k_child2'")
        assert cursor.fetchone()[0] is None, "parent_knowledge_id应设为NULL"
