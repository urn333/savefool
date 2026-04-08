#!/usr/bin/env python3
"""使用 OCREngine 测试 Ollama 图片识别."""

import asyncio
import sys
sys.path.insert(0, 'src')

from src.infrastructure.models.ollama_client import OllamaClient
from src.domain.engines.ocr_engine import OCREngine, OCROptions


async def test_ocr():
    """测试OCR识别."""
    import time
    start = time.time()
    
    # 创建Ollama客户端（使用更长的超时）
    client = OllamaClient(
        api_base="http://192.168.3.110:11434",
        model="gemma4:31b-it-q8_0",
        timeout=600.0,  # 10分钟超时
    )
    
    # 创建OCR引擎
    ocr_engine = OCREngine(client)
    
    # 测试图片路径
    image_path = "data/IMG_3421.jpg"
    
    print("=" * 60)
    print(f"测试图片: {image_path}")
    print("=" * 60)
    
    # 执行OCR识别
    print("\n开始识别...")
    print(f"[时间] {time.strftime('%H:%M:%S')}")
    try:
        result = await ocr_engine.recognize(
            image_path=image_path,
            subject_hint="数学",
            options=OCROptions(
                detect_subject=True,
                detect_problem_type=True,
                extract_student_answer=True,
                language_hint="zh",
            ),
        )
        
        elapsed = time.time() - start
        if result.success:
            print(f"\n✅ 识别成功! (耗时: {elapsed:.1f}s)")
            print(f"\n题目内容:\n{result.content}")
            print(f"\n学生答案: {result.student_answer}")
            print(f"学科: {result.subject}")
            print(f"题型: {result.problem_type}")
            print(f"知识点: {result.knowledge_points}")
            print(f"置信度: {result.confidence}")
        else:
            elapsed = time.time() - start
            print(f"\n❌ 识别失败: {result.error} (耗时: {elapsed:.1f}s)")
            
    except Exception as e:
        elapsed = time.time() - start
        print(f"\n❌ 异常 ({elapsed:.1f}s): {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_ocr())
