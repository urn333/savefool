#!/usr/bin/env python3
"""真实大模型诊断测试脚本.

使用 data/IMG_3421.jpg 进行测试，输出大模型的分析结果。

用法:
    python3 test_real_diagnosis.py

环境变量:
    KIMI_API_KEY: 从 https://www.kimi.com/code 获取的 API Key
"""

import os
import sys
import base64
import asyncio
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.infrastructure.models import create_model_client
from src.infrastructure.logging import configure_logging, get_logger
from src.domain.engines.ocr_engine import OCREngine, OCROptions
from src.domain.engines.model_schedulers import ModelAScheduler, SchedulerConfig

configure_logging()
logger = get_logger(__name__)


async def test_diagnosis(image_path: str = "data/IMG_3421.jpg"):
    """测试真实的大模型诊断.
    
    Args:
        image_path: 图片路径
    """
    print("=" * 60)
    print("AI助教系统 - 真实大模型诊断测试")
    print("=" * 60)
    print()
    
    # 检查图片是否存在
    if not os.path.exists(image_path):
        print(f"❌ 图片不存在: {image_path}")
        return
    
    print(f"📷 测试图片: {image_path}")
    print(f"   大小: {os.path.getsize(image_path) / 1024:.1f} KB")
    print()
    
    # 检查API Key
    print("🔑 检查API配置...")
    try:
        from src.infrastructure.config import get_settings
        settings = get_settings()
        print(f"   提供商: {settings.active_model_provider}")
        print(f"   API地址: {settings.kimi.api_base}")
        print(f"   模型: {settings.kimi.model}")
        
        client = create_model_client()
        print(f"   ✅ API Key 已配置")
        print()
    except ValueError as e:
        print(f"   ❌ API Key 未配置: {e}")
        print()
        print("请设置环境变量或编辑 .env 文件:")
        print("  export KIMI_API_KEY=sk-kimi-xxxxxxxx")
        return
    except Exception as e:
        print(f"   ❌ 配置错误: {e}")
        return
    
    # 读取图片
    print("📖 读取图片...")
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    print(f"   ✅ 图片已读取 ({len(image_base64)} 字符 base64)")
    print()
    
    # OCR识别
    print("🔍 步骤1: OCR识别 (调用大模型视觉能力)...")
    print("-" * 60)
    
    ocr_engine = OCREngine(client)
    
    try:
        ocr_result = await ocr_engine.recognize(
            image_path=image_path,
            options=OCROptions(
                detect_subject=True,
                detect_problem_type=True,
                extract_student_answer=True,
                language_hint="zh",
            ),
        )
        
        if not ocr_result.success:
            print(f"❌ OCR识别失败: {ocr_result.error}")
            return
        
        print(f"✅ OCR识别成功!")
        print(f"   学科: {ocr_result.subject}")
        print(f"   题型: {ocr_result.problem_type}")
        print(f"   置信度: {ocr_result.confidence:.2%}")
        print()
        print(f"📋 识别内容:")
        print(f"{ocr_result.content}")
        print()
        
        if ocr_result.student_answer:
            print(f"✏️  学生答案: {ocr_result.student_answer}")
            print()
        
        if ocr_result.knowledge_points:
            print(f"📚 知识点: {', '.join(ocr_result.knowledge_points)}")
            print()
        
    except Exception as e:
        print(f"❌ OCR识别异常: {e}")
        logger.exception("ocr_failed")
        return
    
    # 模型诊断
    print("=" * 60)
    print("🧠 步骤2: 模型诊断分析...")
    print("-" * 60)
    
    try:
        scheduler = ModelAScheduler(
            client=client,
            config=SchedulerConfig(
                model_id="model_a",
                model_name=settings.kimi.model,
                temperature=0.3,
                max_tokens=2048,
                timeout=60.0,
                weight=0.4,
            ),
        )
        
        parsed_problem = ocr_result.to_parsed_problem()
        
        model_result = await scheduler.schedule(
            problem=parsed_problem,
            images=[image_base64],
        )
        
        print(f"✅ 诊断完成!")
        print(f"   是否正确: {'✓ 正确' if model_result.is_correct else '✗ 错误'}")
        print(f"   错误类型: {model_result.error_type.value if model_result.error_type else 'N/A'}")
        print(f"   置信度: {model_result.confidence:.2%}")
        print(f"   耗时: {model_result.latency_ms:.0f}ms")
        print()
        
        print("📊 详细诊断:")
        for key, value in model_result.diagnosis.items():
            if key != "raw_response":
                print(f"   {key}: {value}")
        print()
        
        if "explanation" in model_result.diagnosis:
            print("💡 讲解建议:")
            print(f"{model_result.diagnosis['explanation']}")
            print()
        
        print("=" * 60)
        print("✅ 测试完成!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 诊断异常: {e}")
        logger.exception("diagnosis_failed")
        return


if __name__ == "__main__":
    # 检查是否有API Key
    if not os.environ.get("KIMI_API_KEY"):
        # 尝试从.env加载
        from dotenv import load_dotenv
        load_dotenv()
    
    asyncio.run(test_diagnosis())
