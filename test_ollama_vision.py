#!/usr/bin/env python3
"""测试 Ollama 图片识别能力."""

import asyncio
import sys
sys.path.insert(0, 'src')

from src.infrastructure.models.ollama_client import OllamaClient
from src.infrastructure.models.base import Message


async def test_vision():
    """测试图片识别."""
    client = OllamaClient(
        api_base="http://192.168.3.110:11434",
        model="gemma4:31b-it-q8_0",
        timeout=300.0,  # 31B模型需要更长时间
    )

    # 读取压缩后的图片
    with open("/tmp/test_image_base64.txt", "r") as f:
        base64_image = f.read().strip()

    print(f"图片大小: {len(base64_image)} 字符")
    print("=" * 50)

    # 测试1: 识别题目
    print("\n[测试1] 识别图片中的数学题目...")
    messages = [
        Message.system("你是一个数学题目识别专家。"),
        Message.user("请识别图片中的数学题目，提取完整的题目内容。"),
    ]
    
    try:
        resp = await client.complete_with_vision(messages, [base64_image])
        print(f"\n识别结果:\n{resp.content}")
    except Exception as e:
        print(f"错误: {e}")

    # 测试2: 检查错题
    print("\n" + "=" * 50)
    print("\n[测试2] 检查题目是否有错误...")
    messages = [
        Message.system("你是一个数学作业批改助手。"),
        Message.user("请检查图片中的数学题目是否有错误，如果有请指出。"),
    ]
    
    try:
        resp = await client.complete_with_vision(messages, [base64_image])
        print(f"\n批改结果:\n{resp.content}")
    except Exception as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    asyncio.run(test_vision())
