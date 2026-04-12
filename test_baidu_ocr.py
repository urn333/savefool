#!/usr/bin/env python3
"""测试百度OCR功能.

使用前需要:
1. 访问 https://cloud.baidu.com/product/ocr 申请API Key
2. 在 .env 文件中配置:
   BAIDU_OCR_ENABLED=true
   BAIDU_OCR_API_KEY=your_api_key
   BAIDU_OCR_SECRET_KEY=your_secret_key
"""

import asyncio
import base64
import sys
from pathlib import Path

sys.path.insert(0, 'src')


def encode_image(image_path: str) -> str:
    """将图片转为base64."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


async def test_baidu_ocr():
    """测试百度OCR."""
    from src.infrastructure.models import create_ocr_client
    from src.infrastructure.config import get_settings
    
    # 检查配置
    settings = get_settings()
    baidu_config = settings.baidu_ocr
    
    print("=" * 60)
    print("百度OCR测试")
    print("=" * 60)
    
    if not baidu_config.enabled:
        print("\n⚠️  百度OCR未启用")
        print("请在 .env 文件中设置:")
        print("  BAIDU_OCR_ENABLED=true")
        print("  BAIDU_OCR_API_KEY=your_api_key")
        print("  BAIDU_OCR_SECRET_KEY=your_secret_key")
        print("\n申请地址: https://cloud.baidu.com/product/ocr")
        return False
    
    if not baidu_config.api_key or not baidu_config.secret_key:
        print("\n⚠️  百度OCR API Key 或 Secret Key 未配置")
        return False
    
    # 准备测试图片
    image_path = Path("data/IMG_3421.jpg")
    if not image_path.exists():
        print(f"\n✗ 测试图片不存在: {image_path}")
        return False
    
    print(f"\n测试图片: {image_path}")
    print(f"API Key: {baidu_config.api_key[:8]}...")
    
    try:
        # 创建OCR客户端
        client = create_ocr_client("baidu_ocr")
        print("\n✓ OCR客户端创建成功")
        
        # 编码图片
        image_base64 = encode_image(str(image_path))
        print(f"✓ 图片编码完成 ({len(image_base64)} 字符)")
        
        # 调用OCR识别
        print("\n开始识别...")
        from src.infrastructure.models.base import Message
        
        response = await client.complete_with_vision(
            messages=[Message.user("识别图片中的数学题目")],
            images=[image_base64],
            ocr_type="general",  # general, handwriting, formula
        )
        
        print("\n" + "=" * 60)
        print("识别结果:")
        print("=" * 60)
        print(response.content)
        print("=" * 60)
        print(f"\nToken使用: {response.usage}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ 识别失败: {type(e).__name__}: {e}")
        return False


async def test_ocr_comparison():
    """对比不同OCR提供商的效果."""
    from src.infrastructure.models import create_ocr_client
    from src.infrastructure.config import get_settings
    
    settings = get_settings()
    image_path = Path("data/IMG_3421.jpg")
    
    if not image_path.exists():
        print(f"✗ 测试图片不存在: {image_path}")
        return
    
    print("\n" + "=" * 60)
    print("OCR提供商对比测试")
    print("=" * 60)
    
    image_base64 = encode_image(str(image_path))
    from src.infrastructure.models.base import Message
    
    # 测试百度OCR
    if settings.baidu_ocr.enabled:
        print("\n【百度OCR】")
        try:
            client = create_ocr_client("baidu_ocr")
            response = await client.complete_with_vision(
                messages=[Message.user("识别")],
                images=[image_base64],
            )
            print(f"识别结果（前200字）:\n{response.content[:200]}...")
        except Exception as e:
            print(f"失败: {e}")
    else:
        print("\n【百度OCR】未启用")
    
    # 测试Ollama
    print("\n【Ollama】")
    try:
        client = create_ocr_client("ollama")
        response = await client.complete_with_vision(
            messages=[Message.user("识别图片中的文字")],
            images=[image_base64],
        )
        print(f"识别结果（前200字）:\n{response.content[:200]}...")
    except Exception as e:
        print(f"失败: {e}")


def show_help():
    """显示帮助信息."""
    print("""
百度OCR 免费额度说明:
========================

1. 通用文字识别（高精度版）: 每月 50,000 次免费
2. 手写文字识别: 每月 50,000 次免费
3. 公式识别: 每月 10,000 次免费

申请步骤:
1. 访问 https://cloud.baidu.com/product/ocr
2. 注册/登录百度账号
3. 创建应用，获取 API Key 和 Secret Key
4. 在 .env 文件中配置:
   BAIDU_OCR_ENABLED=true
   BAIDU_OCR_API_KEY=your_api_key
   BAIDU_OCR_SECRET_KEY=your_secret_key

使用方法:
    python test_baidu_ocr.py        # 测试百度OCR
    python test_baidu_ocr.py --help # 显示此帮助
""")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h", "help"):
        show_help()
        sys.exit(0)
    
    # 运行测试
    result = asyncio.run(test_baidu_ocr())
    
    # 如果百度OCR可用，也进行对比测试
    if result:
        asyncio.run(test_ocr_comparison())
    
    sys.exit(0 if result else 1)
