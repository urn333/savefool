"""变形题路由.

提供变形题生成、答案提交、结果获取等API接口.
"""

import time
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, status

from src.infrastructure.logging import get_logger
from src.presentation.api.exceptions import (
    BusinessException,
    ErrorCode,
    NotFoundException,
    ValidationException,
)
from src.presentation.api.schemas import (
    BaseResponse,
    CredibilityRating,
    KnowledgeUpdate,
    VariantAnswerItem,
    VariantAnswerRequest,
    VariantFeedback,
    VariantGenerateRequest,
    VariantGenerateResponse,
    VariantInfo,
    VariantResultItem,
    VariantResultResponse,
    VariantValidationResponse,
)
from src.domain.models.base import generate_id

logger = get_logger(__name__)
router = APIRouter()

# 内存存储
_variant_store: dict = {}
_variant_set_store: dict = {}
_variant_answer_store: dict = {}

# 30秒限时（秒）
VARIANT_TIME_LIMIT = 30


def _generate_mock_variants(question_id: str, count: int = 3) -> List[VariantInfo]:
    """生成模拟变形题.
    
    Args:
        question_id: 原题ID
        count: 生成数量
        
    Returns:
        变形题列表
    """
    # 基于原题生成变形题
    base_variants = [
        {
            "content": "4 + 5 = ?",
            "type": "fill_blank",
            "difficulty": "easy",
            "knowledge_point": "加法运算",
            "answer": "9",
        },
        {
            "content": "7 + 2 = ?",
            "type": "fill_blank",
            "difficulty": "easy",
            "knowledge_point": "加法运算",
            "answer": "9",
        },
        {
            "content": "6 + 6 = ?",
            "type": "fill_blank",
            "difficulty": "medium",
            "knowledge_point": "进位加法",
            "answer": "12",
        },
        {
            "content": "8 + 9 = ?",
            "type": "fill_blank",
            "difficulty": "medium",
            "knowledge_point": "进位加法",
            "answer": "17",
        },
        {
            "content": "15 + 27 = ?",
            "type": "fill_blank",
            "difficulty": "hard",
            "knowledge_point": "多位数加法",
            "answer": "42",
        },
    ]
    
    variants = []
    for i in range(min(count, len(base_variants))):
        base = base_variants[i]
        # 生成可信度评分（1-5星）
        stars = 5 - i  # 难度越高，可信度略低
        
        variant = VariantInfo(
            variant_id=generate_id("var"),
            content=base["content"],
            type=base["type"],
            difficulty=base["difficulty"],
            knowledge_point=base["knowledge_point"],
            credibility=CredibilityRating(
                stars=stars,
                score=stars / 5.0,
                confidence="high" if stars >= 4 else "medium" if stars >= 3 else "low",
            ),
        )
        
        # 存储答案用于验证
        _variant_store[variant.variant_id] = {
            **variant.model_dump(),
            "correct_answer": base["answer"],
            "created_at": int(datetime.utcnow().timestamp()),
        }
        variants.append(variant)
    
    return variants


@router.post(
    "",
    response_model=BaseResponse,
    summary="生成变形题",
    description="基于错题生成变形练习题，包含可信度评分",
)
async def generate_variants(request: VariantGenerateRequest) -> BaseResponse:
    """生成变形题.
    
    基于原题生成变形练习题，包含可信度评分（1-5星）。
    
    Args:
        request: 生成请求
        
    Returns:
        变形题组
    """
    logger.info(
        "generate_variants",
        question_id=request.question_id,
        difficulty=request.difficulty.value,
        count=request.count,
    )
    
    # 生成变形题
    variants = _generate_mock_variants(request.question_id, request.count)
    
    # 生成题组ID
    variant_set_id = generate_id("var_set")
    
    # 存储题组
    _variant_set_store[variant_set_id] = {
        "variant_set_id": variant_set_id,
        "question_id": request.question_id,
        "variants": [v.variant_id for v in variants],
        "created_at": int(datetime.utcnow().timestamp()),
        "time_limit": VARIANT_TIME_LIMIT,
    }
    
    logger.info(
        "variants_generated",
        variant_set_id=variant_set_id,
        count=len(variants),
    )
    
    return BaseResponse(
        code=0,
        message="success",
        data=VariantGenerateResponse(
            variant_set_id=variant_set_id,
            variants=variants,
        ).model_dump()
    )


@router.get(
    "/{question_id}",
    response_model=BaseResponse,
    summary="获取变形题（简化接口）",
    description="基于题目ID直接获取变形题",
)
async def get_variant(question_id: str) -> BaseResponse:
    """获取变形题.
    
    Args:
        question_id: 题目ID
        
    Returns:
        变形题
    """
    logger.info("get_variant", question_id=question_id)
    
    # 生成变形题
    variants = _generate_mock_variants(question_id, 1)
    
    if not variants:
        raise BusinessException(
            code=ErrorCode.VARIANT_GENERATION_FAILED,
            message="变形题生成失败",
        )
    
    return BaseResponse(
        code=0,
        message="success",
        data=variants[0].model_dump()
    )


@router.post(
    "/{variant_set_id}/answers",
    response_model=BaseResponse,
    summary="提交变形题答案",
    description="提交变形题答案，30秒限时",
)
async def submit_variant_answers(
    variant_set_id: str,
    request: VariantAnswerRequest,
) -> BaseResponse:
    """提交变形题答案.
    
    提交变形题答案，验证正确性。
    
    Args:
        variant_set_id: 变形题组ID
        request: 答案请求
        
    Returns:
        验证结果
    """
    logger.info(
        "submit_variant_answers",
        variant_set_id=variant_set_id,
        answer_count=len(request.answers),
    )
    
    # 检查题组是否存在
    if variant_set_id not in _variant_set_store:
        raise NotFoundException(resource_type="变形题组", resource_id=variant_set_id)
    
    variant_set = _variant_set_store[variant_set_id]
    
    # 检查是否超时
    created_at = variant_set.get("created_at", 0)
    elapsed = int(datetime.utcnow().timestamp()) - created_at
    
    if elapsed > VARIANT_TIME_LIMIT:
        logger.warning(
            "variant_time_exceeded",
            variant_set_id=variant_set_id,
            elapsed=elapsed,
            limit=VARIANT_TIME_LIMIT,
        )
        # 仍然接受答案，但标记为超时
    
    # 验证答案
    results = []
    correct_count = 0
    
    for answer_item in request.answers:
        variant_id = answer_item.variant_id
        
        if variant_id not in _variant_store:
            raise NotFoundException(
                resource_type="变形题",
                resource_id=variant_id,
            )
        
        variant = _variant_store[variant_id]
        correct_answer = variant.get("correct_answer", "")
        is_correct = answer_item.answer.strip() == correct_answer.strip()
        
        if is_correct:
            correct_count += 1
        
        results.append(VariantResultItem(
            variant_id=variant_id,
            correct=is_correct,
            answer=answer_item.answer,
            correct_answer=correct_answer,
        ))
    
    # 计算得分
    total = len(request.answers)
    score = int(correct_count / total * 100) if total > 0 else 0
    passed = score >= 60  # 60分及格
    
    # 存储答案记录
    answer_record = {
        "variant_set_id": variant_set_id,
        "answers": [a.model_dump() for a in request.answers],
        "results": [r.model_dump() for r in results],
        "score": score,
        "passed": passed,
        "submitted_at": int(datetime.utcnow().timestamp()),
        "elapsed_seconds": elapsed,
    }
    _variant_answer_store[variant_set_id] = answer_record
    
    logger.info(
        "variant_answers_submitted",
        variant_set_id=variant_set_id,
        score=score,
        passed=passed,
    )
    
    return BaseResponse(
        code=0,
        message="success",
        data=VariantValidationResponse(
            validated=True,
            results=results,
            score=score,
            passed=passed,
        ).model_dump()
    )


@router.post(
    "/{variant_id}/answer",
    response_model=BaseResponse,
    summary="提交单个变形题答案（简化接口）",
    description="提交单个变形题答案",
)
async def submit_single_answer(
    variant_id: str,
    answer: str,
) -> BaseResponse:
    """提交单个变形题答案.
    
    Args:
        variant_id: 变形题ID
        answer: 答案
        
    Returns:
        验证结果
    """
    logger.info("submit_single_answer", variant_id=variant_id, answer=answer)
    
    if variant_id not in _variant_store:
        raise NotFoundException(resource_type="变形题", resource_id=variant_id)
    
    variant = _variant_store[variant_id]
    correct_answer = variant.get("correct_answer", "")
    is_correct = answer.strip() == correct_answer.strip()
    
    return BaseResponse(
        code=0,
        message="success",
        data={
            "variant_id": variant_id,
            "correct": is_correct,
            "answer": answer,
            "correct_answer": correct_answer,
        }
    )


@router.get(
    "/{variant_set_id}/result",
    response_model=BaseResponse,
    summary="获取验证结果",
    description="获取变形题验证结果和反馈",
)
async def get_variant_result(variant_set_id: str) -> BaseResponse:
    """获取变形题结果.
    
    Args:
        variant_set_id: 变形题组ID
        
    Returns:
        完整结果和反馈
        
    Raises:
        NotFoundException: 题组或答案不存在
    """
    logger.info("get_variant_result", variant_set_id=variant_set_id)
    
    if variant_set_id not in _variant_set_store:
        raise NotFoundException(resource_type="变形题组", resource_id=variant_set_id)
    
    if variant_set_id not in _variant_answer_store:
        raise NotFoundException(
            resource_type="变形题答案",
            resource_id=variant_set_id,
        )
    
    answer_record = _variant_answer_store[variant_set_id]
    score = answer_record["score"]
    passed = answer_record["passed"]
    
    # 生成反馈
    if score == 100:
        summary = "太棒了！全部答对！"
        encouragement = "你已经完全掌握了这个知识点，继续保持！"
        next_steps = ["尝试更难一点的题目", "学习下一个知识点"]
    elif score >= 80:
        summary = "很好！大部分都答对了！"
        encouragement = "你掌握得不错，再练习一下就能完全掌握了！"
        next_steps = ["复习错题", "再做一组练习"]
    elif score >= 60:
        summary = "及格了，但还需要努力！"
        encouragement = "基本概念掌握了，但需要更多练习。"
        next_steps = ["重点复习错题知识点", "从基础题开始练习"]
    else:
        summary = "需要加强练习！"
        encouragement = "没关系，学习需要过程，我们再试一次！"
        next_steps = ["重新学习相关概念", "从最简单的题目开始"]
    
    feedback = VariantFeedback(
        summary=summary,
        encouragement=encouragement,
        next_steps=next_steps,
    )
    
    # 计算掌握度
    mastery_level = min(1.0, score / 100.0 + 0.1)
    
    knowledge_update = KnowledgeUpdate(
        mastered=passed,
        mastery_level=mastery_level,
    )
    
    result = VariantResultResponse(
        variant_set_id=variant_set_id,
        score=score,
        passed=passed,
        feedback=feedback,
        knowledge_update=knowledge_update,
    )
    
    return BaseResponse(
        code=0,
        message="success",
        data=result.model_dump()
    )
