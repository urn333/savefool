"""记忆系统测试数据.

提供学生画像、学习事件、语义知识等测试数据。
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List


# =============================================================================
# 学生认知画像样本
# =============================================================================

SAMPLE_STUDENT_PROFILE: Dict[str, Any] = {
    "student_id": "stu_test_001",
    "version": 5,
    "cognitive_level": {
        "overall": 6.5,
        "comprehension": 7.0,
        "application": 6.0,
        "analysis": 6.5,
        "synthesis": 5.5,
        "evaluation": 6.0,
    },
    "learning_style": {
        "visual": 0.45,
        "auditory": 0.30,
        "kinesthetic": 0.25,
    },
    "weak_concepts": [
        {
            "concept_id": "kp_fraction_calc",
            "concept_name": "分数计算",
            "mastery_level": 0.45,
            "attempt_count": 12,
            "success_count": 5,
            "success_rate": 0.42,
            "last_attempt_at": (datetime.now() - timedelta(days=3)).isoformat(),
        },
        {
            "concept_id": "kp_equation_solving",
            "concept_name": "方程求解",
            "mastery_level": 0.55,
            "attempt_count": 15,
            "success_count": 8,
            "success_rate": 0.53,
            "last_attempt_at": (datetime.now() - timedelta(days=1)).isoformat(),
        },
    ],
    "strong_concepts": [
        {
            "concept_id": "kp_basic_arithmetic",
            "concept_name": "基础运算",
            "mastery_level": 0.92,
            "attempt_count": 50,
            "success_count": 46,
            "success_rate": 0.92,
            "last_attempt_at": (datetime.now() - timedelta(days=2)).isoformat(),
        },
        {
            "concept_id": "kp_number_sense",
            "concept_name": "数感",
            "mastery_level": 0.88,
            "attempt_count": 30,
            "success_count": 26,
            "success_rate": 0.87,
            "last_attempt_at": (datetime.now() - timedelta(days=5)).isoformat(),
        },
    ],
    "recent_mistakes": [
        {
            "error_type": "calculation_error",
            "occurrence_count": 8,
            "related_concepts": ["kp_fraction_calc", "kp_decimal_calc"],
            "first_occurred_at": (datetime.now() - timedelta(days=30)).isoformat(),
            "last_occurred_at": (datetime.now() - timedelta(days=3)).isoformat(),
        },
        {
            "error_type": "concept_misunderstanding",
            "occurrence_count": 5,
            "related_concepts": ["kp_equation_solving"],
            "first_occurred_at": (datetime.now() - timedelta(days=20)).isoformat(),
            "last_occurred_at": (datetime.now() - timedelta(days=1)).isoformat(),
        },
    ],
    "last_updated": datetime.now().isoformat(),
}


# =============================================================================
# 学习事件样本
# =============================================================================

SAMPLE_LEARNING_EPISODES: List[Dict[str, Any]] = [
    {
        "episode_id": "ep_001",
        "student_id": "stu_test_001",
        "timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
        "event_type": "attempt",
        "homework_id": "hw_001",
        "problem_id": "math_001",
        "subject": "math",
        "difficulty": 3,
        "concept_ids": ["kp_equation_solving", "kp_algebra_basic"],
        "time_spent": 180,
        "attempts": 2,
        "hints_used": 1,
        "final_result": "correct",
        "error_type": None,
        "confidence": 0.75,
        "metadata": {"source": "homework", "help_requested": True},
    },
    {
        "episode_id": "ep_002",
        "student_id": "stu_test_001",
        "timestamp": (datetime.now() - timedelta(days=2)).isoformat(),
        "event_type": "attempt",
        "homework_id": "hw_001",
        "problem_id": "math_002",
        "subject": "math",
        "difficulty": 2,
        "concept_ids": ["kp_rectangle_area", "kp_multiplication"],
        "time_spent": 120,
        "attempts": 1,
        "hints_used": 0,
        "final_result": "correct",
        "error_type": None,
        "confidence": 0.90,
        "metadata": {"source": "homework", "help_requested": False},
    },
    {
        "episode_id": "ep_003",
        "student_id": "stu_test_001",
        "timestamp": (datetime.now() - timedelta(days=3)).isoformat(),
        "event_type": "attempt",
        "homework_id": "hw_002",
        "problem_id": "math_004",
        "subject": "math",
        "difficulty": 4,
        "concept_ids": ["kp_fraction_calc", "kp_fraction_add"],
        "time_spent": 300,
        "attempts": 3,
        "hints_used": 2,
        "final_result": "incorrect",
        "error_type": "calculation_error",
        "confidence": 0.50,
        "metadata": {"source": "homework", "error_step": "通分"},
    },
    {
        "episode_id": "ep_004",
        "student_id": "stu_test_001",
        "timestamp": (datetime.now() - timedelta(days=5)).isoformat(),
        "event_type": "variant",
        "homework_id": None,
        "problem_id": "variant_001",
        "subject": "math",
        "difficulty": 4,
        "concept_ids": ["kp_fraction_calc"],
        "time_spent": 240,
        "attempts": 2,
        "hints_used": 1,
        "final_result": "correct",
        "error_type": None,
        "confidence": 0.70,
        "metadata": {"source": "variant_practice", "original_problem": "math_004"},
    },
    {
        "episode_id": "ep_005",
        "student_id": "stu_test_001",
        "timestamp": (datetime.now() - timedelta(hours=12)).isoformat(),
        "event_type": "hint",
        "homework_id": "hw_003",
        "problem_id": "math_003",
        "subject": "math",
        "difficulty": 6,
        "concept_ids": ["kp_quadratic_func", "kp_vertex_form"],
        "time_spent": 60,
        "attempts": 1,
        "hints_used": 1,
        "final_result": "unknown",
        "error_type": None,
        "confidence": 0.40,
        "metadata": {"hint_type": "concept_explanation"},
    },
]


# =============================================================================
# 语义知识样本
# =============================================================================

SAMPLE_SEMANTIC_KNOWLEDGE: Dict[str, Any] = {
    "student_id": "stu_test_001",
    "concept_mastery": [
        {
            "concept_id": "kp_linear_eq",
            "concept_name": "一元一次方程",
            "mastery_level": 0.75,
            "confidence": 0.85,
            "evidence": ["ep_001", "ep_010", "ep_015"],
            "related_concepts": ["kp_algebra_basic", "kp_equation_solving"],
            "last_updated": (datetime.now() - timedelta(days=1)).isoformat(),
        },
        {
            "concept_id": "kp_fraction_calc",
            "concept_name": "分数计算",
            "mastery_level": 0.45,
            "confidence": 0.90,
            "evidence": ["ep_003", "ep_004", "ep_008"],
            "related_concepts": ["kp_fraction_add", "kp_fraction_sub"],
            "last_updated": (datetime.now() - timedelta(days=3)).isoformat(),
        },
        {
            "concept_id": "kp_geometry_basic",
            "concept_name": "基础几何",
            "mastery_level": 0.82,
            "confidence": 0.88,
            "evidence": ["ep_002", "ep_012"],
            "related_concepts": ["kp_rectangle_area", "kp_triangle_area"],
            "last_updated": (datetime.now() - timedelta(days=2)).isoformat(),
        },
    ],
    "knowledge_paths": [
        {
            "from_concept": "kp_basic_arithmetic",
            "to_concept": "kp_fraction_calc",
            "transfer_strength": 0.70,
            "evidence_count": 15,
        },
        {
            "from_concept": "kp_fraction_calc",
            "to_concept": "kp_equation_solving",
            "transfer_strength": 0.55,
            "evidence_count": 10,
        },
        {
            "from_concept": "kp_algebra_basic",
            "to_concept": "kp_quadratic_func",
            "transfer_strength": 0.60,
            "evidence_count": 8,
        },
    ],
    "weak_points": [
        {
            "concept_id": "kp_fraction_calc",
            "severity": 0.75,
            "occurrence_count": 8,
            "last_occurrence": (datetime.now() - timedelta(days=3)).isoformat(),
            "related_errors": ["calculation_error", "careless_mistake"],
        },
        {
            "concept_id": "kp_quadratic_func",
            "severity": 0.60,
            "occurrence_count": 5,
            "last_occurrence": (datetime.now() - timedelta(days=7)).isoformat(),
            "related_errors": ["concept_misunderstanding"],
        },
    ],
    "last_updated": datetime.now().isoformat(),
}


# =============================================================================
# 认知缺口样本
# =============================================================================

SAMPLE_COGNITIVE_GAPS: List[Dict[str, Any]] = [
    {
        "gap_id": "gap_001",
        "student_id": "stu_test_001",
        "gap_type": "concept_gap",
        "status": "crystallized",
        "related_knowledge": ["kp_fraction_calc", "kp_fraction_add"],
        "discovered_at": (datetime.now() - timedelta(days=30)).isoformat(),
        "crystallized_at": (datetime.now() - timedelta(days=7)).isoformat(),
        "occurrence_count": 8,
        "updated_at": (datetime.now() - timedelta(days=3)).isoformat(),
    },
    {
        "gap_id": "gap_002",
        "student_id": "stu_test_001",
        "gap_type": "calculation_weakness",
        "status": "pending",
        "related_knowledge": ["kp_decimal_calc"],
        "discovered_at": (datetime.now() - timedelta(days=10)).isoformat(),
        "crystallized_at": None,
        "occurrence_count": 3,
        "updated_at": (datetime.now() - timedelta(days=3)).isoformat(),
    },
    {
        "gap_id": "gap_003",
        "student_id": "stu_test_001",
        "gap_type": "concept_gap",
        "status": "dismissed",
        "related_knowledge": ["kp_algebra_basic"],
        "discovered_at": (datetime.now() - timedelta(days=20)).isoformat(),
        "crystallized_at": None,
        "occurrence_count": 2,
        "updated_at": (datetime.now() - timedelta(days=15)).isoformat(),
    },
]


# =============================================================================
# 辅助函数
# =============================================================================

def get_episodes_by_type(event_type: str) -> List[Dict[str, Any]]:
    """根据事件类型获取学习事件.
    
    Args:
        event_type: 事件类型
        
    Returns:
        事件列表
    """
    return [ep for ep in SAMPLE_LEARNING_EPISODES if ep["event_type"] == event_type]


def get_episodes_by_concept(concept_id: str) -> List[Dict[str, Any]]:
    """根据概念ID获取相关学习事件.
    
    Args:
        concept_id: 概念ID
        
    Returns:
        事件列表
    """
    return [
        ep for ep in SAMPLE_LEARNING_EPISODES 
        if concept_id in ep.get("concept_ids", [])
    ]


def get_gaps_by_status(status: str) -> List[Dict[str, Any]]:
    """根据状态获取认知缺口.
    
    Args:
        status: 状态 (pending/crystallized/dismissed)
        
    Returns:
        缺口列表
    """
    return [gap for gap in SAMPLE_COGNITIVE_GAPS if gap["status"] == status]
