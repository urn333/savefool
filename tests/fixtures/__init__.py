"""测试数据Fixtures.

提供测试所需的模拟数据和辅助函数。
"""

from tests.fixtures.problem_data import (
    SAMPLE_MATH_PROBLEMS,
    SAMPLE_PHYSICS_PROBLEMS,
    SAMPLE_CHEMISTRY_PROBLEMS,
)
from tests.fixtures.model_results import (
    MODEL_A_RESULTS,
    MODEL_B_RESULTS,
    MODEL_C_RESULTS,
    MOCK_MODEL_RESPONSES,
)
from tests.fixtures.memory_data import (
    SAMPLE_STUDENT_PROFILE,
    SAMPLE_LEARNING_EPISODES,
    SAMPLE_SEMANTIC_KNOWLEDGE,
    SAMPLE_COGNITIVE_GAPS,
)

__all__ = [
    # 题目数据
    "SAMPLE_MATH_PROBLEMS",
    "SAMPLE_PHYSICS_PROBLEMS", 
    "SAMPLE_CHEMISTRY_PROBLEMS",
    # 模型结果数据
    "MODEL_A_RESULTS",
    "MODEL_B_RESULTS",
    "MODEL_C_RESULTS",
    "MOCK_MODEL_RESPONSES",
    # 记忆系统数据
    "SAMPLE_STUDENT_PROFILE",
    "SAMPLE_LEARNING_EPISODES",
    "SAMPLE_SEMANTIC_KNOWLEDGE",
    "SAMPLE_COGNITIVE_GAPS",
]
