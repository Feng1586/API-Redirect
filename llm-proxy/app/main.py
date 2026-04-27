"""
FastAPI 应用入口
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.router import api_router
from app.config import settings
from app.database import engine
from log.logger import get_logger
from middleware.session import SessionMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan 事件处理器：替代已弃用的 on_event"""
    # 应用启动时执行
    logger.info("Application startup")
    yield
    # 应用关闭时执行
    logger.info("Application shutdown")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用"""
    app = FastAPI(
        title="LLM Proxy API",
        description="大模型 API 中转站",
        version="1.0.0",
        docs_url="/docs" if settings.app.debug else None,
        redoc_url="/redoc" if settings.app.debug else None,
        lifespan=lifespan,  # 使用 lifespan 替代 on_event
    )

    # Session 中间件：自动验证、续期、清理无效 Cookie
    app.add_middleware(SessionMiddleware)

    # 注册路由
    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
