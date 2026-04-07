"""诊断路由.

提供错题诊断、分层选择、结果获取等API接口.
"""

from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, status

from src.infrastructure.logging import get_logger
from src.presentation.api.exceptions import (
    BusinessException,
    ErrorCode,
    NotFoundException,
    ValidationException,
)
from src.presentation.api.schemas import (
    BaseResponse,
    DiagnosisDetailResponse,
    DiagnosisOption,
    DiagnosisOptionsResponse,
    DiagnosisSelectRequest,
    ErrorAnalysis,
    ExplanationData,
    ExplanationStep,
)
from src.domain.models.base import generate_id

logger = get_logger(__name__)
router = APIRouter()

# 内存存储
_diagnosis_store: dict = {}
_diagnosis_options_store: dict = {}

# 模拟诊断选项模板
DIAGNOSIS_OPTIONS_TEMPLATE = {
    "careless": [
        DiagnosisOption(
            option_id="opt_1_1",
            level=1,
            label="粗心大意",
            description="计算过程正确，但结果写错",
            icon="careless",
        ),
        DiagnosisOption(
            option_id="opt_1_2",
            level=1,
            label="看错题目",
            description="没有仔细读题，理解有误",
            icon="misread",
        ),
        DiagnosisOption(
            option_id="opt_1_3",
            level=1,
            label="漏写步骤",
            description="跳步导致计算出错",
            icon="skip",
        ),
    ],
    "concept": [
        DiagnosisOption(
            option_id="opt_2_1",
            level=2,
            label="概念模糊",
            description="对进位加法概念理解不透彻",
            icon="concept",
        ),
        DiagnosisOption(
            option_id="opt_2_2",
            level=2,
            label="公式记错",
            description="记错了计算公式或规则",
            icon="formula",
        ),
        DiagnosisOption(
            option_id="opt_2_3",
            level=2,
            label="方法错误",
            description="使用了错误的解题方法",
            icon="method",
        ),
    ],
    "unknown": [
        DiagnosisOption(
            option_id="opt_3_1",
            level=3,
            label="完全不会",
            description="不理解加法运算的基本方法",
            icon="unknown",
        ),
        DiagnosisOption(
            option_id="opt_3_2",
            level=3,
            label="基础薄弱",
            description="基础知识掌握不牢固",
            icon="weak",
        ),
        DiagnosisOption(
            option_id="opt_3_3",
            level=3,
            label="从未学过",
            description="这道题的解题方法还没学过",
            icon="new",
        ),
    ],
}


def _get_or_create_diagnosis_options(question_id: str) -> DiagnosisOptionsResponse:
    """获取或创建诊断选项.
    
    Args:
        question_id: 题目ID
        
    Returns:
        诊断选项响应
    """
    if question_id not in _diagnosis_options_store:
        # 创建新的诊断选项
        options = []
        for category in ["careless", "concept", "unknown"]:
            options.extend(DIAGNOSIS_OPTIONS_TEMPLATE[category])
        
        _diagnosis_options_store[question_id] = DiagnosisOptionsResponse(
            question_id=question_id,
            options=options,
        )
    
    return _diagnosis_options_store[question_id]


@router.get(
    "/{question_id}/options",
    response_model=BaseResponse,
    summary="获取诊断选项",
    description="获取错题的3选项分层诊断（Step1/Step2）",
)
async def get_diagnosis_options(question_id: str) -> BaseResponse:
    """获取诊断选项.
    
    返回3个层级的诊断选项：
    - Level 1: 粗心大意类（看错、漏写等）
    - Level 2: 概念模糊类（理解不透彻）
    - Level 3: 完全不会类（基础知识缺失）
    
    Args:
        question_id: 题目ID
        
    Returns:
        诊断选项列表
    """
    logger.info("get_diagnosis_options", question_id=question_id)
    
    options_response = _get_or_create_diagnosis_options(question_id)
    
    return BaseResponse(
        code=0,
        message="success",
        data=options_response.model_dump()
    )


@router.post(
    "/{question_id}",
    response_model=BaseResponse,
    summary="提交诊断选择",
    description="提交分层诊断选择，Step1/Step2选项",
)
async def submit_diagnosis(
    question_id: str,
    request: DiagnosisSelectRequest,
) -> BaseResponse:
    """提交诊断选择.
    
    Args:
        question_id: 题目ID
        request: 诊断选择请求
        
    Returns:
        诊断结果
    """
    logger.info(
        "submit_diagnosis",
        question_id=question_id,
        level=request.level,
        has_notes=bool(request.notes),
    )
    
    # 验证选项级别
    if request.level not in [1, 2, 3]:
        raise ValidationException(
            message="诊断层级必须是1、2或3",
            errors=[{"field": "level", "message": "必须是1、2或3"}],
        )
    
    # 生成诊断ID
    diagnosis_id = generate_id("dia")
    
    # 根据层级确定诊断结果
    level_mapping = {
        1: ("粗心大意", "建议细心检查，养成验算习惯"),
        2: ("概念模糊", "建议重新学习相关概念，多做类似练习"),
        3: ("完全不会", "建议从基础知识开始系统学习"),
    }
    
    error_type, suggestion = level_mapping[request.level]
    
    # 创建诊断记录
    diagnosis_record = {
        "diagnosis_id": diagnosis_id,
        "question_id": question_id,
        "level": request.level,
        "notes": request.notes,
        "error_type": error_type,
        "suggestion": suggestion,
        "created_at": int(datetime.utcnow().timestamp()),
        "status": "completed",
    }
    
    _diagnosis_store[diagnosis_id] = diagnosis_record
    
    # 返回诊断结果
    result = {
        "diagnosis_id": diagnosis_id,
        "status": "completed",
        "result": {
            "level": request.level,
            "knowledge_gap": f"诊断层级{request.level} - {error_type}",
            "recommendation": suggestion,
        }
    }
    
    logger.info(
        "diagnosis_submitted",
        diagnosis_id=diagnosis_id,
        question_id=question_id,
        level=request.level,
    )
    
    return BaseResponse(
        code=0,
        message="success",
        data=result
    )


@router.get(
    "/{diagnosis_id}",
    response_model=BaseResponse,
    summary="获取诊断结果",
    description="获取完整诊断结果和讲解",
)
async def get_diagnosis_result(diagnosis_id: str) -> BaseResponse:
    """获取诊断结果.
    
    Args:
        diagnosis_id: 诊断ID
        
    Returns:
        诊断详情
        
    Raises:
        NotFoundException: 诊断不存在
    """
    logger.info("get_diagnosis_result", diagnosis_id=diagnosis_id)
    
    if diagnosis_id not in _diagnosis_store:
        raise NotFoundException(resource_type="诊断", resource_id=diagnosis_id)
    
    diagnosis = _diagnosis_store[diagnosis_id]
    
    # 构建分析结果
    analysis = ErrorAnalysis(
        error_type=diagnosis["error_type"],
        root_cause=f"根据分层诊断，学生属于{diagnosis['error_type']}",
        knowledge_points=["进位加法", "加法运算"],
    )
    
    # 构建讲解内容
    steps = [
        ExplanationStep(
            step=1,
            content="先看个位数：3和5",
            highlight="3, 5",
        ),
        ExplanationStep(
            step=2,
            content="个位相加：3 + 5 = 8，不需要进位",
            highlight="8",
        ),
        ExplanationStep(
            step=3,
            content="所以正确答案是8",
            highlight="= 8",
        ),
    ]
    
    explanation = ExplanationData(
        text=f"我们来看这道题：3 + 5 = 8。{diagnosis['suggestion']}",
        steps=steps,
        tips=[
            "记住：相加满10才进位",
            "先算个位，再算十位",
            "做完后记得验算",
        ],
    )
    
    detail = DiagnosisDetailResponse(
        diagnosis_id=diagnosis_id,
        question_id=diagnosis["question_id"],
        level=diagnosis["level"],
        analysis=analysis,
        explanation=explanation,
        variant_ready=True,  # 变形题已就绪
    )
    
    return BaseResponse(
        code=0,
        message="success",
        data=detail.model_dump()
    )


@router.get(
    "/homework/{homework_id}",
    response_model=BaseResponse,
    summary="获取作业诊断结果",
    description="根据作业ID获取所有题目的诊断结果",
)
async def get_homework_diagnosis(homework_id: str) -> BaseResponse:
    """获取作业诊断结果.
    
    Args:
        homework_id: 作业ID
        
    Returns:
        作业诊断结果列表
    """
    logger.info("get_homework_diagnosis", homework_id=homework_id)
    
    # 查找该作业相关的所有诊断
    diagnoses = [
        diag for diag in _diagnosis_store.values()
        if diag.get("homework_id") == homework_id
    ]
    
    return BaseResponse(
        code=0,
        message="success",
        data={
            "homework_id": homework_id,
            "diagnosis_count": len(diagnoses),
            "diagnoses": diagnoses,
        }
    )


@router.post(
    "/{diagnosis_id}/select",
    response_model=BaseResponse,
    summary="提交分层选择（兼容旧版）",
    description="兼容旧版API路径，功能同POST /{question_id}",
)
async def submit_layered_selection(
    diagnosis_id: str,
    request: DiagnosisSelectRequest,
) -> BaseResponse:
    """提交分层选择.
    
    这是兼容性端点，实际会创建新的诊断记录。
    
    Args:
        diagnosis_id: 诊断ID（作为参考）
        request: 选择请求
        
    Returns:
        诊断结果
    """
    logger.info(
        "submit_layered_selection",
        diagnosis_id=diagnosis_id,
        level=request.level,
    )
    
    # 使用诊断ID对应的question_id
    if diagnosis_id in _diagnosis_store:
        question_id = _diagnosis_store[diagnosis_id]["question_id"]
    else:
        # 如果不存在，使用诊断ID作为问题ID
        question_id = diagnosis_id.replace("dia_", "q_")
    
    # 调用主要的诊断提交逻辑
    return await submit_diagnosis(question_id, request)
