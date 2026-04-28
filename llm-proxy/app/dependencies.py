"""
依赖注入（认证、权限）
"""

from typing import Optional
from dataclasses import dataclass

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from models.user import User
from repositories.user_repo import UserRepository
from services.auth_service import AuthService
from services.apikey_service import ApiKeyService
from log.logger import get_logger

logger = get_logger(__name__)
auth_service = AuthService()
apikey_service = ApiKeyService()
user_repo = UserRepository()


@dataclass
class AuthenticatedUser:
    """认证用户（包含用户信息和API-Key ID）"""
    user: User
    api_key_id: int


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """获取当前登录用户（基于 Session）

    复用 SessionMiddleware 已验证的 request.state.session_data，
    避免重复查询 Redis。仅需查库获取用户信息。
    """
    session_data = getattr(request.state, "session_data", None)
    session_id = getattr(request.state, "session_id", None)

    if not session_id or not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 40102, "message": "未登录"},
        )

    user_id = session_data.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 40102, "message": "Session无效"},
        )

    user = user_repo.get_by_id(user_id, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 40102, "message": "用户不存在"},
        )

    user.session_id = session_id
    return user


async def get_current_user_by_apikey(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_goog_api_key: Optional[str] = Header(None, alias="x-goog-api-key"),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    """获取当前用户（基于 API-Key）"""
    api_key = None

    # 支持多种API Key头部格式（按优先级）
    # 1. x-goog-api-key (Gemini原生格式)
    if x_goog_api_key:
        api_key = x_goog_api_key
    # 2. Authorization: Bearer (标准格式)
    elif authorization and authorization.startswith("Bearer "):
        api_key = authorization[7:]
    # 3. x-api-key (备用格式)
    elif x_api_key:
        api_key = x_api_key

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 40103, "message": "缺少API-Key"},
        )

    result = apikey_service.validate_api_key(api_key, db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 40103, "message": "API-Key无效"},
        )

    return result
