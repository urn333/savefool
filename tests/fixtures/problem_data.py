"""测试题目数据.

提供数学、物理、化学等学科的测试题目数据。
"""

from typing import Any, Dict, List


# =============================================================================
# 数学题目
# =============================================================================

SAMPLE_MATH_PROBLEMS: List[Dict[str, Any]] = [
    {
        "id": "math_001",
        "content": "解方程: 2x + 5 = 15",
        "subject": "math",
        "difficulty": 3,
        "answer": "5",
        "solution_steps": [
            "移项: 2x = 15 - 5",
            "计算: 2x = 10", 
            "解得: x = 5"
        ],
        "knowledge_points": ["kp_linear_eq", "kp_algebra_basic"],
        "question_type": "equation",
    },
    {
        "id": "math_002",
        "content": "一个长方形的长是12厘米，宽是8厘米，求它的面积。",
        "subject": "math",
        "difficulty": 2,
        "answer": "96",
        "solution_steps": [
            "长方形面积公式: 面积 = 长 × 宽",
            "代入数值: 面积 = 12 × 8",
            "计算: 面积 = 96 平方厘米"
        ],
        "knowledge_points": ["kp_rectangle_area", "kp_multiplication"],
        "question_type": "geometry",
    },
    {
        "id": "math_003",
        "content": "已知函数 f(x) = x² - 4x + 3，求其顶点坐标。",
        "subject": "math",
        "difficulty": 6,
        "answer": "(2, -1)",
        "solution_steps": [
            "二次函数顶点公式: x = -b/(2a)",
            "代入: x = 4/(2×1) = 2",
            "计算f(2): f(2) = 4 - 8 + 3 = -1",
            "顶点坐标为 (2, -1)"
        ],
        "knowledge_points": ["kp_quadratic_func", "kp_vertex_form"],
        "question_type": "function",
    },
    {
        "id": "math_004",
        "content": "计算: (3/4) + (1/2) - (1/4)",
        "subject": "math",
        "difficulty": 4,
        "answer": "1",
        "solution_steps": [
            "通分: 1/2 = 2/4",
            "计算: 3/4 + 2/4 - 1/4",
            "结果: 4/4 = 1"
        ],
        "knowledge_points": ["kp_fraction_add", "kp_fraction_calc"],
        "question_type": "fraction",
    },
    {
        "id": "math_005",
        "content": "一个等差数列的首项是3，公差是2，求第10项。",
        "subject": "math",
        "difficulty": 5,
        "answer": "21",
        "solution_steps": [
            "等差数列通项公式: a_n = a_1 + (n-1)d",
            "代入: a_10 = 3 + (10-1)×2",
            "计算: a_10 = 3 + 18 = 21"
        ],
        "knowledge_points": ["kp_arithmetic_seq", "kp_sequence"],
        "question_type": "sequence",
    },
]


# =============================================================================
# 物理题目
# =============================================================================

SAMPLE_PHYSICS_PROBLEMS: List[Dict[str, Any]] = [
    {
        "id": "physics_001",
        "content": "一辆汽车以20m/s的速度匀速行驶，5秒内行驶的距离是多少？",
        "subject": "physics",
        "difficulty": 3,
        "answer": "100m",
        "solution_steps": [
            "匀速运动公式: s = vt",
            "代入数值: s = 20 × 5",
            "计算: s = 100m"
        ],
        "knowledge_points": ["kp_uniform_motion", "kp_distance_calc"],
        "question_type": "mechanics",
    },
    {
        "id": "physics_002",
        "content": "一个物体质量为5kg，受到10N的力作用，求加速度。",
        "subject": "physics",
        "difficulty": 4,
        "answer": "2m/s²",
        "solution_steps": [
            "牛顿第二定律: F = ma",
            "变形: a = F/m",
            "代入: a = 10/5 = 2m/s²"
        ],
        "knowledge_points": ["kp_newton_second", "kp_force_motion"],
        "question_type": "mechanics",
    },
]


# =============================================================================
# 化学题目
# =============================================================================

SAMPLE_CHEMISTRY_PROBLEMS: List[Dict[str, Any]] = [
    {
        "id": "chem_001",
        "content": "计算H₂O的相对分子质量。（H=1, O=16）",
        "subject": "chemistry",
        "difficulty": 2,
        "answer": "18",
        "solution_steps": [
            "H₂O含有2个H原子和1个O原子",
            "计算: 2×1 + 1×16",
            "结果: 18"
        ],
        "knowledge_points": ["kp_molar_mass", "kp_chemical_formula"],
        "question_type": "calculation",
    },
]


# =============================================================================
# 错误答案样本（用于测试诊断）
# =============================================================================

WRONG_ANSWER_SAMPLES: List[Dict[str, Any]] = [
    {
        "problem_id": "math_001",
        "student_answer": "10",
        "error_type": "careless",
        "analysis": "学生在移项时出错，忘记将5变为-5，直接计算2x=15，得到x=10/2=5",
    },
    {
        "problem_id": "math_001",
        "student_answer": "20",
        "error_type": "calculation",
        "analysis": "学生可能将2x+5理解为2(x+5)，导致计算错误",
    },
    {
        "problem_id": "math_002",
        "student_answer": "40",
        "error_type": "concept",
        "analysis": "学生混淆了周长和面积公式，使用了(长+宽)×2",
    },
]


# =============================================================================
# 辅助函数
# =============================================================================

def get_problem_by_id(problem_id: str) -> Dict[str, Any]:
    """根据ID获取题目.
    
    Args:
        problem_id: 题目ID
        
    Returns:
        题目数据，不存在则返回空字典
    """
    all_problems = (
        SAMPLE_MATH_PROBLEMS + 
        SAMPLE_PHYSICS_PROBLEMS + 
        SAMPLE_CHEMISTRY_PROBLEMS
    )
    for problem in all_problems:
        if problem["id"] == problem_id:
            return problem
    return {}


def get_problems_by_subject(subject: str) -> List[Dict[str, Any]]:
    """根据学科获取题目列表.
    
    Args:
        subject: 学科名称
        
    Returns:
        题目列表
    """
    all_problems = (
        SAMPLE_MATH_PROBLEMS + 
        SAMPLE_PHYSICS_PROBLEMS + 
        SAMPLE_CHEMISTRY_PROBLEMS
    )
    return [p for p in all_problems if p["subject"] == subject]


def get_problems_by_difficulty(min_diff: int, max_diff: int) -> List[Dict[str, Any]]:
    """根据难度范围获取题目.
    
    Args:
        min_diff: 最小难度
        max_diff: 最大难度
        
    Returns:
        题目列表
    """
    all_problems = (
        SAMPLE_MATH_PROBLEMS + 
        SAMPLE_PHYSICS_PROBLEMS + 
        SAMPLE_CHEMISTRY_PROBLEMS
    )
    return [p for p in all_problems if min_diff <= p["difficulty"] <= max_diff]
