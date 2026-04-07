"""模拟模型返回结果数据.

提供三模型（A、B、C）的模拟输出数据，用于测试仲裁引擎。
"""

from typing import Any, Dict, List


# =============================================================================
# 模型A输出（通用大模型 - 考点分类）
# =============================================================================

MODEL_A_RESULTS: Dict[str, Dict[str, Any]] = {
    "math_001": {
        "model_id": "model_a",
        "question_type": "linear_equation",
        "knowledge_tags": ["一元一次方程", "等式性质", "移项法则"],
        "difficulty_assessment": 3,
        "concepts_involved": ["方程", "未知数", "解的概念"],
        "deconstruction": {
            "known": ["方程形式: 2x + 5 = 15", "目标: 求x的值"],
            "unknown": ["x的具体数值"],
            "operations": ["移项", "合并同类项", "系数化为1"]
        },
        "confidence": 0.92,
    },
    "math_002": {
        "model_id": "model_a",
        "question_type": "geometry_area",
        "knowledge_tags": ["长方形", "面积计算", "乘法运算"],
        "difficulty_assessment": 2,
        "concepts_involved": ["长方形", "面积", "长宽"],
        "deconstruction": {
            "known": ["长=12cm", "宽=8cm", "形状: 长方形"],
            "unknown": ["面积值"],
            "operations": ["长×宽"]
        },
        "confidence": 0.95,
    },
    "math_003": {
        "model_id": "model_a",
        "question_type": "quadratic_function",
        "knowledge_tags": ["二次函数", "顶点坐标", "配方法"],
        "difficulty_assessment": 6,
        "concepts_involved": ["函数", "抛物线", "顶点", "对称轴"],
        "deconstruction": {
            "known": ["函数表达式: f(x)=x²-4x+3", "形式: 二次函数"],
            "unknown": ["顶点坐标"],
            "operations": ["配方", "顶点公式"]
        },
        "confidence": 0.88,
    },
}


# =============================================================================
# 模型B输出（理科专用模型 - 步骤验证）
# =============================================================================

MODEL_B_RESULTS: Dict[str, Dict[str, Any]] = {
    "math_001": {
        "model_id": "model_b",
        "is_correct": True,
        "error_type": None,
        "step_analysis": [
            {"step": 1, "content": "2x = 15 - 5", "valid": True, "reason": "移项正确"},
            {"step": 2, "content": "2x = 10", "valid": True, "reason": "计算正确"},
            {"step": 3, "content": "x = 5", "valid": True, "reason": "系数化为1正确"}
        ],
        "logic_check": {
            "premises_valid": True,
            "reasoning_valid": True,
            "conclusion_valid": True
        },
        "confidence": 0.94,
    },
    "math_002": {
        "model_id": "model_b",
        "is_correct": True,
        "error_type": None,
        "step_analysis": [
            {"step": 1, "content": "面积 = 长 × 宽", "valid": True, "reason": "公式正确"},
            {"step": 2, "content": "面积 = 12 × 8", "valid": True, "reason": "代入正确"},
            {"step": 3, "content": "面积 = 96", "valid": True, "reason": "计算正确"}
        ],
        "logic_check": {
            "premises_valid": True,
            "reasoning_valid": True,
            "conclusion_valid": True
        },
        "confidence": 0.96,
    },
    "math_003": {
        "model_id": "model_b",
        "is_correct": True,
        "error_type": None,
        "step_analysis": [
            {"step": 1, "content": "x = -(-4)/(2×1) = 2", "valid": True, "reason": "顶点公式正确"},
            {"step": 2, "content": "f(2) = 4 - 8 + 3 = -1", "valid": True, "reason": "函数值计算正确"},
            {"step": 3, "content": "顶点为(2, -1)", "valid": True, "reason": "结论正确"}
        ],
        "logic_check": {
            "premises_valid": True,
            "reasoning_valid": True,
            "conclusion_valid": True
        },
        "confidence": 0.91,
    },
}


# =============================================================================
# 模型C输出（概念归因模型 - 概念映射）
# =============================================================================

MODEL_C_RESULTS: Dict[str, Dict[str, Any]] = {
    "math_001": {
        "model_id": "model_c",
        "concept_mapping": {
            "equation_solving": 0.95,
            "algebraic_manipulation": 0.88,
            "number_sense": 0.75
        },
        "prerequisite_concepts": ["整数运算", "等式性质", "代数思维"],
        "potential_misconceptions": [
            "移项时忘记变号",
            "合并同类项错误",
            "系数化1时计算错误"
        ],
        "attribution_analysis": {
            "skill_based": 0.7,
            "concept_based": 0.3
        },
        "confidence": 0.87,
    },
    "math_002": {
        "model_id": "model_c",
        "concept_mapping": {
            "geometric_understanding": 0.92,
            "multiplication_skill": 0.88,
            "unit_awareness": 0.70
        },
        "prerequisite_concepts": ["长方形定义", "乘法表", "面积概念"],
        "potential_misconceptions": [
            "混淆面积和周长",
            "忘记单位",
            "乘法计算错误"
        ],
        "attribution_analysis": {
            "skill_based": 0.5,
            "concept_based": 0.5
        },
        "confidence": 0.89,
    },
    "math_003": {
        "model_id": "model_c",
        "concept_mapping": {
            "function_understanding": 0.90,
            "completing_square": 0.85,
            "coordinate_geometry": 0.78
        },
        "prerequisite_concepts": ["函数概念", "完全平方公式", "坐标系"],
        "potential_misconceptions": [
            "混淆顶点和零点",
            "配方计算错误",
            "符号错误"
        ],
        "attribution_analysis": {
            "skill_based": 0.4,
            "concept_based": 0.6
        },
        "confidence": 0.85,
    },
}


# =============================================================================
# 错误诊断场景的三模型输出
# =============================================================================

WRONG_ANSWER_MODEL_RESULTS: Dict[str, Dict[str, Any]] = {
    # 场景1: 三模型一致（高置信度）
    "consensus_all_agree": {
        "model_a": {
            "model_id": "model_a",
            "is_correct": False,
            "error_type": "calculation_error",
            "confidence": 0.91,
        },
        "model_b": {
            "model_id": "model_b",
            "is_correct": False,
            "error_type": "calculation_error",
            "confidence": 0.93,
        },
        "model_c": {
            "model_id": "model_c",
            "is_correct": False,
            "error_type": "calculation_error",
            "confidence": 0.88,
        },
    },
    # 场景2: 两模型一致（多数决）
    "consensus_two_agree": {
        "model_a": {
            "model_id": "model_a",
            "is_correct": False,
            "error_type": "concept_misunderstanding",
            "confidence": 0.85,
        },
        "model_b": {
            "model_id": "model_b",
            "is_correct": False,
            "error_type": "concept_misunderstanding",
            "confidence": 0.90,
        },
        "model_c": {
            "model_id": "model_c",
            "is_correct": False,
            "error_type": "calculation_error",
            "confidence": 0.75,
        },
    },
    # 场景3: 全部分歧（待验证）
    "consensus_all_different": {
        "model_a": {
            "model_id": "model_a",
            "is_correct": False,
            "error_type": "concept_misunderstanding",
            "confidence": 0.80,
        },
        "model_b": {
            "model_id": "model_b",
            "is_correct": False,
            "error_type": "calculation_error",
            "confidence": 0.85,
        },
        "model_c": {
            "model_id": "model_c",
            "is_correct": True,
            "error_type": None,
            "confidence": 0.70,
        },
    },
    # 场景4: 单模型失败
    "single_model_failure": {
        "model_a": {
            "model_id": "model_a",
            "is_correct": False,
            "error_type": "careless_mistake",
            "confidence": 0.88,
        },
        "model_b": {
            "model_id": "model_b",
            "error": "timeout",
            "confidence": 0.0,
        },
        "model_c": {
            "model_id": "model_c",
            "is_correct": False,
            "error_type": "careless_mistake",
            "confidence": 0.82,
        },
    },
    # 场景5: 全部失败
    "all_models_failure": {
        "model_a": {
            "model_id": "model_a",
            "error": "api_error",
            "confidence": 0.0,
        },
        "model_b": {
            "model_id": "model_b",
            "error": "timeout",
            "confidence": 0.0,
        },
        "model_c": {
            "model_id": "model_c",
            "error": "parse_error",
            "confidence": 0.0,
        },
    },
}


# =============================================================================
# Mock模型客户端响应
# =============================================================================

MOCK_MODEL_RESPONSES: Dict[str, Any] = {
    "model_a_success": {
        "content": '{"question_type": "linear_equation", "knowledge_tags": ["一元一次方程"], "confidence": 0.92}',
        "model": "model-a-v1",
        "usage": {"prompt_tokens": 150, "completion_tokens": 50, "total_tokens": 200},
        "finish_reason": "stop",
    },
    "model_b_success": {
        "content": '{"is_correct": true, "error_type": null, "confidence": 0.94}',
        "model": "model-b-v1",
        "usage": {"prompt_tokens": 180, "completion_tokens": 30, "total_tokens": 210},
        "finish_reason": "stop",
    },
    "model_c_success": {
        "content": '{"concept_mapping": {"equation": 0.95}, "confidence": 0.87}',
        "model": "model-c-v1",
        "usage": {"prompt_tokens": 160, "completion_tokens": 40, "total_tokens": 200},
        "finish_reason": "stop",
    },
    "model_timeout": {
        "error": "Request timeout after 30 seconds",
        "model": "model-x-v1",
        "usage": {"prompt_tokens": 150, "completion_tokens": 0, "total_tokens": 150},
        "finish_reason": "timeout",
    },
    "model_error": {
        "error": "API rate limit exceeded",
        "model": "model-x-v1",
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "finish_reason": "error",
    },
}


# =============================================================================
# 辅助函数
# =============================================================================

def get_model_result(model_id: str, problem_id: str) -> Dict[str, Any]:
    """获取指定模型对指定题目的结果.
    
    Args:
        model_id: 模型ID (model_a/model_b/model_c)
        problem_id: 题目ID
        
    Returns:
        模型结果数据
    """
    result_map = {
        "model_a": MODEL_A_RESULTS,
        "model_b": MODEL_B_RESULTS,
        "model_c": MODEL_C_RESULTS,
    }
    model_results = result_map.get(model_id, {})
    return model_results.get(problem_id, {})


def get_consensus_scenario(scenario_name: str) -> Dict[str, Any]:
    """获取指定共识场景的模型结果.
    
    Args:
        scenario_name: 场景名称
        
    Returns:
        场景数据
    """
    return WRONG_ANSWER_MODEL_RESULTS.get(scenario_name, {})
