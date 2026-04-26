"""
Session中间件

职责：
1. 验证 Cookie 中的 Session 是否在 Redis 中有效
2. 有效时自动续期（滑动过期），更新响应 Cookie
3. 无效时主动清除客户端 Cookie，避免重复发送过期凭证
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from utils.redis_client import RedisClient
from app.config import settings
from log.logger import get_logger

logger = get_logger(__name__)
redis_client = RedisClient()


class SessionMiddleware(BaseHTTPMiddleware):
    """Session 中间件：自动验证 + 续期 + 清理无效 Cookie"""

    async def dispatch(self, request: Request, call_next):
        # 从 Cookie 获取 session_id
        session_id = request.cookies.get(settings.session.cookie_name)

        # 先执行下游逻辑（路由处理 / 依赖注入）
        response = await call_next(request)

        # 无 Cookie 则跳过
        if not session_id:
            return response

        # 验证 Session 在 Redis 中是否仍然有效
        session_data = redis_client.get_session(session_id)

        if session_data:
            # ✅ 有效：续期 Redis TTL + 更新响应 Cookie 过期时间
            redis_client.refresh_session(session_id)
            response.set_cookie(
                key=settings.session.cookie_name,
                value=session_id,
                max_age=settings.session.ttl,
                httponly=settings.session.cookie_httponly,
                samesite=settings.session.cookie_samesite,
                secure=settings.session.cookie_secure,
            )
        else:
            # ❌ 已过期/不存在：清理客户端 Cookie
            response.delete_cookie(
                key=settings.session.cookie_name,
                samesite=settings.session.cookie_samesite,
                secure=settings.session.cookie_secure,
            )

        return response
