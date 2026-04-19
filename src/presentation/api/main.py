"""FastAPI应用主入口.

提供RESTful API服务，实现90秒闭环诊断流程.
"""

import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.infrastructure.config import get_settings
from src.infrastructure.logging import get_logger, configure_logging
from src.infrastructure.storage.database import db_manager
from src.presentation.api.exceptions import register_exception_handlers
from src.presentation.api.schemas import BaseResponse, HealthCheckResponse
from src.presentation.api.routes import homework, diagnosis, variant, statistics

logger = get_logger(__name__)
settings = get_settings()


# ========== 生命周期管理 ==========

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理.
    
    处理启动和关闭事件。
    """
    # 启动事件
    logger.info("api_startup", version=settings.VERSION)
    
    # 记录配置信息（脱敏）
    logger.info(
        "api_config",
        env=settings.env.value,
        debug=settings.debug,
        api_prefix=settings.api_prefix,
    )
    
    # 初始化数据库表
    try:
        await db_manager.create_tables()
        logger.info("database_tables_created")
    except Exception as e:
        logger.error("database_tables_creation_failed", error=str(e))
        raise
    
    yield
    
    # 关闭事件
    logger.info("api_shutdown")


def create_app() -> FastAPI:
    """创建FastAPI应用实例.
    
    Returns:
        FastAPI应用实例
    """
    # 设置日志
    configure_logging()
    
    # 创建应用
    app = FastAPI(
        title="AI助教系统 API",
        description="AI助教系统RESTful API - 实现90秒闭环诊断",
        version=settings.VERSION,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )
    
    # 注册中间件
    _register_middlewares(app)
    
    # 注册异常处理器
    register_exception_handlers(app)
    
    # 注册路由
    _register_routes(app)
    
    # 注册静态文件和模板
    _register_static_files(app)
    
    return app


def _register_middlewares(app: FastAPI) -> None:
    """注册中间件.
    
    Args:
        app: FastAPI应用实例
    """
    # CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # GZip压缩中间件
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # 请求日志中间件
    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        """请求日志中间件."""
        start_time = time.time()
        request_id = request.headers.get("X-Request-ID", "")
        
        # 记录请求
        logger.info(
            "request_start",
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else None,
            request_id=request_id,
        )
        
        try:
            response = await call_next(request)
            
            # 计算处理时间
            process_time = time.time() - start_time
            
            # 记录响应
            logger.info(
                "request_complete",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                process_time=round(process_time * 1000, 2),  # 毫秒
                request_id=request_id,
            )
            
            # 添加响应头
            response.headers["X-Process-Time"] = str(round(process_time, 4))
            if request_id:
                response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.exception(
                "request_error",
                method=request.method,
                path=request.url.path,
                process_time=round(process_time * 1000, 2),
                error=str(e),
                request_id=request_id,
            )
            raise
    
    # 超时控制中间件
    @app.middleware("http")
    async def timeout_middleware(request: Request, call_next):
        """超时控制中间件."""
        # 设置请求超时（90秒）
        from asyncio import wait_for, TimeoutError as AsyncTimeoutError
        
        try:
            # 对于诊断相关的请求，使用较长的超时
            if "/diagnosis" in request.url.path or "/homework" in request.url.path:
                return await wait_for(call_next(request), timeout=95.0)
            else:
                return await wait_for(call_next(request), timeout=30.0)
        except AsyncTimeoutError:
            logger.error(
                "request_timeout",
                method=request.method,
                path=request.url.path,
            )
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=504,
                content={
                    "code": 3,
                    "message": "请求超时",
                    "data": None,
                    "timestamp": int(time.time()),
                }
            )


def _register_routes(app: FastAPI) -> None:
    """注册路由.
    
    Args:
        app: FastAPI应用实例
    """
    api_prefix = settings.API_PREFIX or "/api/v1"
    
    # 健康检查端点
    @app.get("/health", response_model=BaseResponse)
    async def health_check():
        """健康检查端点."""
        return BaseResponse(
            code=0,
            message="success",
            data=HealthCheckResponse(
                status="healthy",
                version=settings.VERSION,
                timestamp=int(time.time()),
            ).model_dump()
        )
    
    # API路由
    app.include_router(
        homework.router,
        prefix=f"{api_prefix}/homework",
        tags=["作业管理"],
    )
    app.include_router(
        diagnosis.router,
        prefix=f"{api_prefix}/diagnosis",
        tags=["诊断"],
    )
    app.include_router(
        variant.router,
        prefix=f"{api_prefix}/variant",
        tags=["变形题"],
    )
    app.include_router(
        statistics.router,
        prefix=f"{api_prefix}/statistics",
        tags=["统计"],
    )
    
    # 根路径重定向到Web界面
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """根路径重定向到上传页面."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>AI助教系统</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background: #f5f5f5;
                }
                .container {
                    background: white;
                    padding: 30px;
                    border-radius: 12px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                }
                h1 { color: #333; text-align: center; }
                .nav { display: flex; justify-content: center; gap: 20px; margin-top: 30px; }
                .nav a {
                    padding: 12px 24px;
                    background: #4CAF50;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    transition: background 0.3s;
                }
                .nav a:hover { background: #45a049; }
                .api-link {
                    text-align: center;
                    margin-top: 30px;
                }
                .api-link a { color: #666; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎓 AI助教系统</h1>
                <p style="text-align: center; color: #666;">
                    智能作业诊断，90秒闭环反馈
                </p>
                <div class="nav">
                    <a href="/web/upload">📤 上传作业</a>
                    <a href="/web/history">📋 作业记录</a>
                    <a href="/web/statistics">📊 学习统计</a>
                </div>
                <div class="api-link">
                    <a href="/docs">API文档 (Swagger)</a> |
                    <a href="/health">健康检查</a>
                </div>
            </div>
        </body>
        </html>
        """


def _register_static_files(app: FastAPI) -> None:
    """注册静态文件和模板.
    
    Args:
        app: FastAPI应用实例
    """
    import os
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    
    # 静态文件目录
    static_dir = os.path.join(
        os.path.dirname(__file__), "..", "web", "static"
    )
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    # 上传文件目录（用于访问上传的作业图片）
    upload_dir = settings.UPLOAD_DIR or "./uploads"
    if os.path.exists(upload_dir):
        app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")
    
    # 模板目录 - 使用裸 Jinja2 API
    templates_dir = os.path.join(
        os.path.dirname(__file__), "..", "web", "templates"
    )
    
    if os.path.exists(templates_dir):
        # 使用裸 Jinja2，禁用缓存避免 dict 问题
        jinja_env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(['html', 'xml']),
            cache_size=0,  # 禁用缓存
        )
        
        def render_template(template_name: str, context: dict) -> str:
            """渲染模板."""
            template = jinja_env.get_template(template_name)
            return template.render(**context)
        
        @app.get("/web/upload", response_class=HTMLResponse)
        async def upload_page(request: Request):
            """上传页面."""
            html = render_template("upload.html", {"active_page": "upload"})
            return HTMLResponse(html)
        
        @app.get("/web/result/{homework_id}", response_class=HTMLResponse)
        async def result_page(request: Request, homework_id: str):
            """结果页面."""
            html = render_template("result.html", {
                "homework_id": homework_id,
                "active_page": "result"
            })
            return HTMLResponse(html)
        
        @app.get("/web/statistics", response_class=HTMLResponse)
        async def statistics_page(request: Request):
            """统计页面."""
            html = render_template("statistics.html", {"active_page": "statistics"})
            return HTMLResponse(html)
        
        @app.get("/web/history", response_class=HTMLResponse)
        async def history_page(request: Request):
            """作业记录页面."""
            html = render_template("history.html", {"active_page": "history"})
            return HTMLResponse(html)


# 创建应用实例
app = create_app()
