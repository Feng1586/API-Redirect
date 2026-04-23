"""
Session中间件
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from services.auth_service import AuthService

auth_service = AuthService()


class SessionMiddleware(BaseHTTPMiddleware):
    """Session 中间件"""

    async def dispatch(self, request: Request, call_next):
        # 从 Cookie 获取 session_id
        session_id = request.cookies.get("llm_session")

        # 如果有 session_id，验证并刷新
        if session_id:
            # TODO: 验证 session 有效性并续期
            pass

        response = await call_next(request)
        return response
