"""
枚举值测试

验证所有CHECK约束的枚举值是否正确工作
"""

import pytest
import sqlite3


@pytest.mark.enum
@pytest.mark.db
class TestErrorTypeEnum:
    """测试错因类型枚举"""
    
    def test_valid_error_types(self, initialized_db: sqlite3.Connection):
        """
        测试有效的错因类型
        
        Given: 基础数据已准备
        When: 插入各种有效error_type
        Then: 应全部成功
        """
        cursor = initialized_db.cursor()
        
        # 创建基础数据
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_err', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_err', 'stu_err', '数学', 1, '[\"test.jpg\"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_err', 'hw_err')")
        
        valid_types = ['careless', 'method_error', 'concept_gap', 'calculation_error', 'reading_error', 'unknown']
        
        for i, error_type in enumerate(valid_types):
            cursor.execute("""
                INSERT INTO student_answer (answer_id, question_id, student_id, answer_content)
                VALUES (?, 'q_err', 'stu_err', 'test')
            """, (f'ans_err_{i}',))
            
            cursor.execute("""
                INSERT INTO error_diagnosis (diagnosis_id, answer_id, question_id, student_id, error_type)
                VALUES (?, ?, 'q_err', 'stu_err', ?)
            """, (f'diag_err_{i}', f'ans_err_{i}', error_type))
        
        initialized_db.commit()
        
        # 验证
        cursor.execute("SELECT COUNT(*) FROM error_diagnosis WHERE error_type IN (?, ?, ?, ?, ?, ?)", 
                      tuple(valid_types))
        count = cursor.fetchone()[0]
        
        assert count == len(valid_types), f"应插入{len(valid_types)}条记录，实际{count}条"
    
    def test_invalid_error_type(self, initialized_db: sqlite3.Connection):
        """
        测试无效的错因类型
        
        Given: 基础数据已准备
        When: 插入无效error_type
        Then: 应触发约束错误
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_err2', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_err2', 'stu_err2', '数学', 1, '[\"test.jpg\"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_err2', 'hw_err2')")
        cursor.execute("""
            INSERT INTO student_answer (answer_id, question_id, student_id, answer_content)
            VALUES ('ans_err2', 'q_err2', 'stu_err2', 'test')
        """)
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO error_diagnosis (diagnosis_id, answer_id, question_id, student_id, error_type)
                VALUES ('diag_invalid', 'ans_err2', 'q_err2', 'stu_err2', 'invalid_type')
            """)
        
        initialized_db.rollback()


@pytest.mark.enum
@pytest.mark.db
class TestVariantTypeEnum:
    """测试变形类型枚举"""
    
    def test_valid_variant_types(self, initialized_db: sqlite3.Connection):
        """
        测试有效的变形类型
        
        Given: 基础数据已准备
        When: 插入各种有效variant_type
        Then: 应全部成功
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_var', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_var', 'stu_var', '数学', 1, '[\"test.jpg\"]')
        """)
        
        valid_types = ['numeric_change', 'inverse_operation', 'context_transfer', 'difficulty_adjust', 'format_change']
        
        for i, var_type in enumerate(valid_types):
            cursor.execute("INSERT INTO question (question_id, homework_id) VALUES (?, 'hw_var')", (f'q_var_{i}',))
            cursor.execute("""
                INSERT INTO variant_question (variant_id, original_question_id, variant_type, variant_content)
                VALUES (?, ?, ?, 'test content')
            """, (f'var_{i}', f'q_var_{i}', var_type))
        
        initialized_db.commit()
        
        cursor.execute("SELECT COUNT(*) FROM variant_question WHERE variant_type IN (?, ?, ?, ?, ?)", 
                      tuple(valid_types))
        count = cursor.fetchone()[0]
        
        assert count == len(valid_types)
    
    def test_invalid_variant_type(self, initialized_db: sqlite3.Connection):
        """
        测试无效的变形类型
        
        Given: 基础数据已准备
        When: 插入无效variant_type
        Then: 应触发约束错误
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_var2', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_var2', 'stu_var2', '数学', 1, '[\"test.jpg\"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_var2', 'hw_var2')")
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO variant_question (variant_id, original_question_id, variant_type, variant_content)
                VALUES ('var_invalid', 'q_var2', 'invalid_type', 'test content')
            """)
        
        initialized_db.rollback()


@pytest.mark.enum
@pytest.mark.db
class TestGapStatusEnum:
    """测试认知缺口状态枚举"""
    
    def test_valid_gap_status(self, initialized_db: sqlite3.Connection):
        """
        测试有效的缺口状态
        
        Given: 学生已存在
        When: 插入各种有效status
        Then: 应全部成功
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_gap', 'Test', '七年级')")
        
        valid_statuses = ['pending', 'crystallized', 'dismissed']
        
        for i, status in enumerate(valid_statuses):
            cursor.execute("""
                INSERT INTO cognitive_gap (gap_id, student_id, gap_type, status)
                VALUES (?, 'stu_gap', 'concept_gap', ?)
            """, (f'gap_{i}', status))
        
        initialized_db.commit()
        
        cursor.execute("SELECT COUNT(*) FROM cognitive_gap WHERE status IN (?, ?, ?)", tuple(valid_statuses))
        count = cursor.fetchone()[0]
        
        assert count == len(valid_statuses)
    
    def test_invalid_gap_status(self, initialized_db: sqlite3.Connection):
        """
        测试无效的缺口状态
        
        Given: 学生已存在
        When: 插入无效status
        Then: 应触发约束错误
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_gap2', 'Test', '七年级')")
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO cognitive_gap (gap_id, student_id, gap_type, status)
                VALUES ('gap_invalid', 'stu_gap2', 'concept_gap', 'invalid_status')
            """)
        
        initialized_db.rollback()
    
    def test_default_gap_status(self, initialized_db: sqlite3.Connection):
        """
        测试缺口状态默认值
        
        Given: 学生已存在
        When: 插入不指定status的缺口
        Then: status应为'pending'
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_gap_def', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO cognitive_gap (gap_id, student_id, gap_type)
            VALUES ('gap_def', 'stu_gap_def', 'concept_gap')
        """)
        initialized_db.commit()
        
        cursor.execute("SELECT status FROM cognitive_gap WHERE gap_id = 'gap_def'")
        status = cursor.fetchone()[0]
        
        assert status == 'pending', f"默认状态应为pending，实际是{status}"


@pytest.mark.enum
@pytest.mark.db
class TestValidationStatusEnum:
    """测试变形题验证状态枚举"""
    
    def test_valid_validation_status(self, initialized_db: sqlite3.Connection):
        """
        测试有效的验证状态
        
        Given: 基础数据已准备
        When: 插入各种有效validation_status
        Then: 应全部成功
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_val', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_val', 'stu_val', '数学', 1, '[\"test.jpg\"]')
        """)
        
        valid_statuses = ['pending', 'validated', 'failed', 'expired']
        
        for i, status in enumerate(valid_statuses):
            cursor.execute("INSERT INTO question (question_id, homework_id) VALUES (?, 'hw_val')", (f'q_val_{i}',))
            cursor.execute("""
                INSERT INTO variant_question (variant_id, original_question_id, variant_type, variant_content, validation_status)
                VALUES (?, ?, 'numeric_change', 'test', ?)
            """, (f'var_val_{i}', f'q_val_{i}', status))
        
        initialized_db.commit()
        
        cursor.execute("SELECT COUNT(*) FROM variant_question WHERE validation_status IN (?, ?, ?, ?)", 
                      tuple(valid_statuses))
        count = cursor.fetchone()[0]
        
        assert count == len(valid_statuses)
    
    def test_invalid_validation_status(self, initialized_db: sqlite3.Connection):
        """
        测试无效的验证状态
        
        Given: 基础数据已准备
        When: 插入无效validation_status
        Then: 应触发约束错误
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_val2', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_val2', 'stu_val2', '数学', 1, '[\"test.jpg\"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_val2', 'hw_val2')")
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO variant_question (variant_id, original_question_id, variant_type, variant_content, validation_status)
                VALUES ('var_val_inv', 'q_val2', 'numeric_change', 'test', 'invalid_status')
            """)
        
        initialized_db.rollback()
    
    def test_default_validation_status(self, initialized_db: sqlite3.Connection):
        """
        测试验证状态默认值
        
        Given: 基础数据已准备
        When: 插入不指定validation_status的变形题
        Then: validation_status应为'pending'
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_val_def', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_val_def', 'stu_val_def', '数学', 1, '[\"test.jpg\"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_val_def', 'hw_val_def')")
        cursor.execute("""
            INSERT INTO variant_question (variant_id, original_question_id, variant_type, variant_content)
            VALUES ('var_val_def', 'q_val_def', 'numeric_change', 'test content')
        """)
        initialized_db.commit()
        
        cursor.execute("SELECT validation_status FROM variant_question WHERE variant_id = 'var_val_def'")
        status = cursor.fetchone()[0]
        
        assert status == 'pending', f"默认状态应为pending，实际是{status}"


@pytest.mark.enum
@pytest.mark.db
class TestHomeworkStatusEnum:
    """测试作业状态枚举"""
    
    def test_valid_homework_status(self, initialized_db: sqlite3.Connection):
        """
        测试有效的作业状态
        
        Given: 学生已存在
        When: 插入各种有效status
        Then: 应全部成功
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_hw_st', 'Test', '七年级')")
        
        valid_statuses = ['active', 'archived', 'deleted']
        
        for i, status in enumerate(valid_statuses):
            cursor.execute("""
                INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls, status)
                VALUES (?, 'stu_hw_st', '数学', 1, '[\"test.jpg\"]', ?)
            """, (f'hw_st_{i}', status))
        
        initialized_db.commit()
        
        cursor.execute("SELECT COUNT(*) FROM homework WHERE status IN (?, ?, ?)", tuple(valid_statuses))
        count = cursor.fetchone()[0]
        
        assert count == len(valid_statuses)
    
    def test_invalid_homework_status(self, initialized_db: sqlite3.Connection):
        """
        测试无效的作业状态
        
        Given: 学生已存在
        When: 插入无效status
        Then: 应触发约束错误
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_hw_st2', 'Test', '七年级')")
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls, status)
                VALUES ('hw_st_inv', 'stu_hw_st2', '数学', 1, '[\"test.jpg\"]', 'invalid_status')
            """)
        
        initialized_db.rollback()
    
    def test_default_homework_status(self, initialized_db: sqlite3.Connection):
        """
        测试作业状态默认值
        
        Given: 学生已存在
        When: 插入不指定status的作业
        Then: status应为'active'
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_hw_def', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_def', 'stu_hw_def', '数学', 1, '[\"test.jpg\"]')
        """)
        initialized_db.commit()
        
        cursor.execute("SELECT status FROM homework WHERE homework_id = 'hw_def'")
        status = cursor.fetchone()[0]
        
        assert status == 'active', f"默认状态应为active，实际是{status}"


@pytest.mark.enum
@pytest.mark.db
class TestEvidenceTypeEnum:
    """测试证据类型枚举"""
    
    def test_valid_evidence_types(self, initialized_db: sqlite3.Connection):
        """
        测试有效的证据类型
        
        Given: 基础数据已准备
        When: 插入各种有效evidence_type
        Then: 应全部成功
        """
        cursor = initialized_db.cursor()
        
        # 创建基础数据链
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_ev', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_ev', 'stu_ev', '数学', 1, '[\"test.jpg\"]')
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
        
        valid_types = ['initial_diagnosis', 'repeat_error', 'variant_failed', 'cross_homework']
        
        for i, ev_type in enumerate(valid_types):
            cursor.execute("""
                INSERT INTO gap_evidence (evidence_id, gap_id, diagnosis_id, evidence_type)
                VALUES (?, 'gap_ev', 'diag_ev', ?)
            """, (f'ev_{i}', ev_type))
        
        initialized_db.commit()
        
        cursor.execute("SELECT COUNT(*) FROM gap_evidence WHERE evidence_type IN (?, ?, ?, ?)", 
                      tuple(valid_types))
        count = cursor.fetchone()[0]
        
        assert count == len(valid_types)
    
    def test_invalid_evidence_type(self, initialized_db: sqlite3.Connection):
        """
        测试无效的证据类型
        
        Given: 基础数据已准备
        When: 插入无效evidence_type
        Then: 应触发约束错误
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_ev2', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_ev2', 'stu_ev2', '数学', 1, '[\"test.jpg\"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_ev2', 'hw_ev2')")
        cursor.execute("""
            INSERT INTO student_answer (answer_id, question_id, student_id, answer_content)
            VALUES ('ans_ev2', 'q_ev2', 'stu_ev2', 'test')
        """)
        cursor.execute("""
            INSERT INTO error_diagnosis (diagnosis_id, answer_id, question_id, student_id, error_type)
            VALUES ('diag_ev2', 'ans_ev2', 'q_ev2', 'stu_ev2', 'careless')
        """)
        cursor.execute("""
            INSERT INTO cognitive_gap (gap_id, student_id, gap_type)
            VALUES ('gap_ev2', 'stu_ev2', 'concept_gap')
        """)
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO gap_evidence (evidence_id, gap_id, diagnosis_id, evidence_type)
                VALUES ('ev_inv', 'gap_ev2', 'diag_ev2', 'invalid_type')
            """)
        
        initialized_db.rollback()


@pytest.mark.enum
@pytest.mark.db
class TestSourceTypeEnum:
    """测试来源类型枚举"""
    
    def test_valid_source_types(self, initialized_db: sqlite3.Connection):
        """
        测试有效的来源类型
        
        Given: 学生已存在
        When: 插入各种有效source_type
        Then: 应全部成功
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_src', 'Test', '七年级')")
        
        valid_types = ['text', 'voice', 'video']
        
        for i, src_type in enumerate(valid_types):
            cursor.execute("""
                INSERT INTO parent_description (description_id, student_id, raw_text, source_type)
                VALUES (?, 'stu_src', 'test description', ?)
            """, (f'desc_{i}', src_type))
        
        initialized_db.commit()
        
        cursor.execute("SELECT COUNT(*) FROM parent_description WHERE source_type IN (?, ?, ?)", 
                      tuple(valid_types))
        count = cursor.fetchone()[0]
        
        assert count == len(valid_types)
    
    def test_invalid_source_type(self, initialized_db: sqlite3.Connection):
        """
        测试无效的来源类型
        
        Given: 学生已存在
        When: 插入无效source_type
        Then: 应触发约束错误
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_src2', 'Test', '七年级')")
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO parent_description (description_id, student_id, raw_text, source_type)
                VALUES ('desc_inv', 'stu_src2', 'test description', 'invalid_type')
            """)
        
        initialized_db.rollback()
    
    def test_default_source_type(self, initialized_db: sqlite3.Connection):
        """
        测试来源类型默认值
        
        Given: 学生已存在
        When: 插入不指定source_type的描述
        Then: source_type应为'text'
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_src_def', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO parent_description (description_id, student_id, raw_text)
            VALUES ('desc_def', 'stu_src_def', 'test description')
        """)
        initialized_db.commit()
        
        cursor.execute("SELECT source_type FROM parent_description WHERE description_id = 'desc_def'")
        src_type = cursor.fetchone()[0]
        
        assert src_type == 'text', f"默认来源类型应为text，实际是{src_type}"


@pytest.mark.enum
@pytest.mark.db
class TestRangeConstraints:
    """测试范围约束"""
    
    def test_confidence_score_range_valid(self, initialized_db: sqlite3.Connection):
        """
        测试有效的置信度范围
        
        Given: 基础数据已准备
        When: 插入0-1范围内的confidence_score
        Then: 应全部成功
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_conf', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_conf', 'stu_conf', '数学', 1, '[\"test.jpg\"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_conf', 'hw_conf')")
        cursor.execute("""
            INSERT INTO student_answer (answer_id, question_id, student_id, answer_content)
            VALUES ('ans_conf', 'q_conf', 'stu_conf', 'test')
        """)
        
        valid_scores = [0, 0.0, 0.5, 0.75, 1.0, 1]
        
        for i, score in enumerate(valid_scores):
            cursor.execute("""
                INSERT INTO error_diagnosis (diagnosis_id, answer_id, question_id, student_id, error_type, confidence_score)
                VALUES (?, 'ans_conf', 'q_conf', 'stu_conf', 'careless', ?)
            """, (f'diag_conf_{i}', score))
        
        initialized_db.commit()
        
        cursor.execute("SELECT COUNT(*) FROM error_diagnosis WHERE confidence_score BETWEEN 0 AND 1")
        count = cursor.fetchone()[0]
        
        assert count >= len(valid_scores)
    
    def test_confidence_score_range_invalid(self, initialized_db: sqlite3.Connection):
        """
        测试无效的置信度范围
        
        Given: 基础数据已准备
        When: 插入超出0-1范围的confidence_score
        Then: 应触发约束错误
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_conf2', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
            VALUES ('hw_conf2', 'stu_conf2', '数学', 1, '[\"test.jpg\"]')
        """)
        cursor.execute("INSERT INTO question (question_id, homework_id) VALUES ('q_conf2', 'hw_conf2')")
        cursor.execute("""
            INSERT INTO student_answer (answer_id, question_id, student_id, answer_content)
            VALUES ('ans_conf2', 'q_conf2', 'stu_conf2', 'test')
        """)
        
        invalid_scores = [-0.1, 1.1, 2.0, -1.0]
        
        for score in invalid_scores:
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute("""
                    INSERT INTO error_diagnosis (diagnosis_id, answer_id, question_id, student_id, error_type, confidence_score)
                    VALUES ('diag_conf_inv', 'ans_conf2', 'q_conf2', 'stu_conf2', 'careless', ?)
                """, (score,))
            initialized_db.rollback()
    
    def test_mastery_level_range(self, initialized_db: sqlite3.Connection):
        """
        测试掌握度范围约束
        
        Given: 学生和知识点已存在
        When: 插入超出0-1范围的mastery_level
        Then: 应触发约束错误
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_mast', 'Test', '七年级')")
        cursor.execute("""
            INSERT INTO knowledge_point (knowledge_id, subject, grade_level, knowledge_name)
            VALUES ('k_mast', '数学', '七年级', '测试知识点')
        """)
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO student_knowledge_mastery (mastery_id, student_id, knowledge_id, mastery_level)
                VALUES ('m_inv', 'stu_mast', 'k_mast', 1.5)
            """)
        
        initialized_db.rollback()
    
    def test_dependency_strength_range(self, initialized_db: sqlite3.Connection):
        """
        测试依赖强度范围约束
        
        Given: 知识点已存在
        When: 插入超出0-1范围的dependency_strength
        Then: 应触发约束错误
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("""
            INSERT INTO knowledge_point (knowledge_id, subject, grade_level, knowledge_name)
            VALUES ('k_dep1', '数学', '七年级', '知识点1')
        """)
        cursor.execute("""
            INSERT INTO knowledge_point (knowledge_id, subject, grade_level, knowledge_name)
            VALUES ('k_dep2', '数学', '七年级', '知识点2')
        """)
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO knowledge_dependency (dependency_id, knowledge_id, prerequisite_id, dependency_strength)
                VALUES ('dep_inv', 'k_dep1', 'k_dep2', -0.5)
            """)
        
        initialized_db.rollback()
    
    def test_page_count_positive(self, initialized_db: sqlite3.Connection):
        """
        测试页数必须大于0
        
        Given: 学生已存在
        When: 插入page_count=0
        Then: 应触发约束错误
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("INSERT INTO student (student_id, name, grade) VALUES ('stu_page', 'Test', '七年级')")
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO homework (homework_id, student_id, subject, page_count, image_urls)
                VALUES ('hw_page', 'stu_page', '数学', 0, '[\"test.jpg\"]')
            """)
        
        initialized_db.rollback()
    
    def test_self_dependency_prevented(self, initialized_db: sqlite3.Connection):
        """
        测试禁止自依赖
        
        Given: 知识点已存在
        When: 创建知识点依赖自身
        Then: 应触发约束错误
        """
        cursor = initialized_db.cursor()
        
        cursor.execute("""
            INSERT INTO knowledge_point (knowledge_id, subject, grade_level, knowledge_name)
            VALUES ('k_self', '数学', '七年级', '自测知识点')
        """)
        
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO knowledge_dependency (dependency_id, knowledge_id, prerequisite_id)
                VALUES ('dep_self', 'k_self', 'k_self')
            """)
        
        initialized_db.rollback()
