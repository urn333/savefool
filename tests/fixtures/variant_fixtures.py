"""变形题测试Fixtures.

提供各类数学题目和预期变形结果。
"""

from typing import Any, Dict, List

from src.domain.models.diagnosis import ErrorType
from src.domain.models.variant import (
    GenerationStrategy,
    VariantGenerationRequest,
    VariantProblem,
)


# =============================================================================
# 数学题目数据
# =============================================================================

SAMPLE_EQUATION_PROBLEMS: List[Dict[str, Any]] = [
    {
        "id": "eq_001",
        "content": "解方程: 2x + 5 = 15",
        "answer": "5",
        "difficulty": 3,
        "error_type": ErrorType.CALCULATION_ERROR,
        "knowledge_points": ["一元一次方程", "移项运算"],
    },
    {
        "id": "eq_002",
        "content": "3x - 7 = 14，求x",
        "answer": "7",
        "difficulty": 4,
        "error_type": ErrorType.CONCEPT_MISUNDERSTANDING,
        "knowledge_points": ["一元一次方程", "负数运算"],
    },
    {
        "id": "eq_003",
        "content": "解方程: 5x + 3 = 2x + 12",
        "answer": "3",
        "difficulty": 5,
        "error_type": ErrorType.LOGICAL_FLAW,
        "knowledge_points": ["一元一次方程", "合并同类项"],
    },
]

SAMPLE_GEOMETRY_PROBLEMS: List[Dict[str, Any]] = [
    {
        "id": "geo_001",
        "content": "一个长方形的长是12厘米，宽是8厘米，求它的面积。",
        "answer": "96",
        "difficulty": 2,
        "error_type": ErrorType.CARELESS_MISTAKE,
        "knowledge_points": ["长方形面积", "乘法运算"],
    },
    {
        "id": "geo_002",
        "content": "正方形周长是36厘米，求边长。",
        "answer": "9",
        "difficulty": 3,
        "error_type": ErrorType.CONCEPT_MISUNDERSTANDING,
        "knowledge_points": ["正方形周长", "除法运算"],
    },
]

SAMPLE_FRACTION_PROBLEMS: List[Dict[str, Any]] = [
    {
        "id": "frac_001",
        "content": "计算: (3/4) + (1/2)",
        "answer": "5/4",
        "difficulty": 4,
        "error_type": ErrorType.CALCULATION_ERROR,
        "knowledge_points": ["分数加法", "通分"],
    },
    {
        "id": "frac_002",
        "content": "1/2 - 1/4 = ?",
        "answer": "1/4",
        "difficulty": 3,
        "error_type": ErrorType.CARELESS_MISTAKE,
        "knowledge_points": ["分数减法"],
    },
]

SAMPLE_APPLICATION_PROBLEMS: List[Dict[str, Any]] = [
    {
        "id": "app_001",
        "content": "小明有5个苹果，给了小红2个，还剩几个？",
        "answer": "3",
        "difficulty": 2,
        "error_type": ErrorType.READING_ERROR,
        "knowledge_points": ["减法应用", "题意理解"],
    },
    {
        "id": "app_002",
        "content": "商店里一支铅笔2元，小明买了3支，一共花了多少钱？",
        "answer": "6",
        "difficulty": 2,
        "error_type": ErrorType.CALCULATION_ERROR,
        "knowledge_points": ["乘法应用", "价格计算"],
    },
]

# =============================================================================
# 学生水平配置
# =============================================================================

STUDENT_LEVELS: Dict[str, Dict[str, Any]] = {
    "beginner": {
        "level": "beginner",
        "typical_difficulty": (1, 4),
        "common_errors": [ErrorType.CARELESS_MISTAKE, ErrorType.CALCULATION_ERROR],
    },
    "average": {
        "level": "average",
        "typical_difficulty": (3, 7),
        "common_errors": [ErrorType.CONCEPT_MISUNDERSTANDING, ErrorType.LOGICAL_FLAW],
    },
    "advanced": {
        "level": "advanced",
        "typical_difficulty": (6, 10),
        "common_errors": [ErrorType.KNOWLEDGE_GAP],
    },
}

# =============================================================================
# 预期变形结果
# =============================================================================

EXPECTED_NUMERIC_TRANSFORMS: List[Dict[str, Any]] = [
    {
        "original": "2x + 5 = 15",
        "expected_patterns": [
            r"\d+/\d+x",  # 分数系数
            r"\d+\.\d+",   # 小数
        ],
        "answer_preserved": True,
    },
    {
        "original": "(3/4) + (1/2)",
        "expected_patterns": [
            r"\d+/\d+",  # 分数形式
        ],
        "answer_preserved": True,
    },
]

EXPECTED_INVERSE_TRANSFORMS: List[Dict[str, Any]] = [
    {
        "original": "2x + 5 = 15，求x",
        "expected_keywords": ["验证", "解为", "求", "已知"],
        "has_answer_change": True,
    },
]

EXPECTED_CONTEXT_TRANSFORMS: List[Dict[str, Any]] = [
    {
        "original": "小明有5个苹果，给了小红2个，还剩几个？",
        "expected_replacements": ["橘子", "香蕉", "书本", "铅笔"],
        "structure_preserved": True,
    },
]


# =============================================================================
# 辅助函数
# =============================================================================

def create_variant_request(
    student_id: str = "stu_test",
    problem_id: str = "prob_test",
    error_type: ErrorType = ErrorType.CARELESS_MISTAKE,
    difficulty: str = "same",
    count: int = 3,
    strategies: List[GenerationStrategy] = None,
) -> VariantGenerationRequest:
    """创建变形题生成请求.
    
    Args:
        student_id: 学生ID
        problem_id: 题目ID
        error_type: 错误类型
        difficulty: 难度调整
        count: 生成数量
        strategies: 指定策略
        
    Returns:
        生成请求
    """
    return VariantGenerationRequest(
        student_id=student_id,
        original_problem_id=problem_id,
        error_type=error_type,
        difficulty=difficulty,
        count=count,
        strategies=strategies,
    )


def create_sample_variant(
    content: str = "2x + 6 = 16",
    answer: str = "5",
    difficulty: int = 3,
    error_type: ErrorType = ErrorType.CALCULATION_ERROR,
    strategy: GenerationStrategy = GenerationStrategy.VALUE_SUBSTITUTION,
) -> VariantProblem:
    """创建示例变形题.
    
    Args:
        content: 题目内容
        answer: 答案
        difficulty: 难度
        error_type: 错误类型
        strategy: 生成策略
        
    Returns:
        变形题
    """
    return VariantProblem(
        original_problem_id="orig_test",
        content=content,
        difficulty=difficulty,
        target_concept="test_concept",
        error_type=error_type,
        strategy=strategy,
        answer=answer,
    )


def get_problem_by_id(problem_id: str) -> Dict[str, Any]:
    """根据ID获取题目.
    
    Args:
        problem_id: 题目ID
        
    Returns:
        题目数据
    """
    all_problems = (
        SAMPLE_EQUATION_PROBLEMS +
        SAMPLE_GEOMETRY_PROBLEMS +
        SAMPLE_FRACTION_PROBLEMS +
        SAMPLE_APPLICATION_PROBLEMS
    )
    for problem in all_problems:
        if problem["id"] == problem_id:
            return problem
    return {}


def get_problems_by_error_type(error_type: ErrorType) -> List[Dict[str, Any]]:
    """根据错误类型获取题目.
    
    Args:
        error_type: 错误类型
        
    Returns:
        题目列表
    """
    all_problems = (
        SAMPLE_EQUATION_PROBLEMS +
        SAMPLE_GEOMETRY_PROBLEMS +
        SAMPLE_FRACTION_PROBLEMS +
        SAMPLE_APPLICATION_PROBLEMS
    )
    return [p for p in all_problems if p["error_type"] == error_type]


# =============================================================================
# 可信度评分测试数据
# =============================================================================

CREDIBILITY_TEST_CASES: List[Dict[str, Any]] = [
    # 5星 - 优秀
    {
        "name": "5_star_excellent",
        "factors": {
            "semantic_similarity": 0.95,
            "difficulty_match": 0.90,
            "solvability": 1.0,
            "validity": 1.0,
            "student_level_match": 0.95,
            "structure_preservation": 0.90,
        },
        "expected_stars": 5,
        "expected_score_range": (0.90, 1.0),
    },
    # 4星 - 良好
    {
        "name": "4_star_good",
        "factors": {
            "semantic_similarity": 0.85,
            "difficulty_match": 0.80,
            "solvability": 1.0,
            "validity": 0.95,
            "student_level_match": 0.75,
            "structure_preservation": 0.80,
        },
        "expected_stars": 4,
        "expected_score_range": (0.75, 0.90),
    },
    # 3星 - 一般
    {
        "name": "3_star_fair",
        "factors": {
            "semantic_similarity": 0.70,
            "difficulty_match": 0.65,
            "solvability": 0.90,
            "validity": 0.85,
            "student_level_match": 0.60,
            "structure_preservation": 0.70,
        },
        "expected_stars": 3,
        "expected_score_range": (0.60, 0.75),
    },
    # 2星 - 较差
    {
        "name": "2_star_poor",
        "factors": {
            "semantic_similarity": 0.50,
            "difficulty_match": 0.45,
            "solvability": 0.70,
            "validity": 0.60,
            "student_level_match": 0.40,
            "structure_preservation": 0.50,
        },
        "expected_stars": 2,
        "expected_score_range": (0.40, 0.60),
    },
    # 1星 - 无法使用
    {
        "name": "1_star_unusable",
        "factors": {
            "semantic_similarity": 0.30,
            "difficulty_match": 0.20,
            "solvability": 0.0,
            "validity": 0.30,
            "student_level_match": 0.20,
            "structure_preservation": 0.20,
        },
        "expected_stars": 1,
        "expected_score_range": (0.0, 0.40),
    },
]

# 边界情况测试
CREDIBILITY_EDGE_CASES: List[Dict[str, Any]] = [
    # 除零保护
    {
        "name": "zero_solvability",
        "factors": {
            "solvability": 0.0,
            "validity": 0.0,
        },
        "expected_stars": 1,
    },
    # 全满分
    {
        "name": "perfect_score",
        "factors": {
            "semantic_similarity": 1.0,
            "difficulty_match": 1.0,
            "solvability": 1.0,
            "validity": 1.0,
            "student_level_match": 1.0,
            "structure_preservation": 1.0,
        },
        "expected_stars": 5,
    },
    # 负数处理
    {
        "name": "negative_values",
        "factors": {
            "semantic_similarity": -0.5,
            "solvability": -1.0,
        },
        "expected_clamped": True,
        "expected_stars": 1,
    },
]
