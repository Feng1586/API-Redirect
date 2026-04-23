"""
FastAPI 应用入口
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import api_router
from app.config import settings
from app.database import engine
from log.logger import get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用"""
    app = FastAPI(
        title="LLM Proxy API",
        description="大模型 API 中转站",
        version="1.0.0",
        docs_url="/docs" if settings.app.debug else None,
        redoc_url="/redoc" if settings.app.debug else None,
    )

    # CORS 配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(api_router, prefix="/api")

    @app.on_event("startup")
    async def startup_event():
        logger.info("Application startup")

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Application shutdown")

    return app


app = create_app()
