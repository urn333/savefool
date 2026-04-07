"""API服务启动脚本.

用于启动FastAPI开发服务器。
"""

import uvicorn

from src.infrastructure.config import get_settings

settings = get_settings()

if __name__ == "__main__":
    uvicorn.run(
        "src.presentation.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
        workers=1 if settings.is_development else settings.api_workers,
    )
