"""
用户认证接口
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from models.user import User
from schemas.user import RegisterRequest, LoginRequest, DeleteAccountRequest, SendCodeRequest
from services.auth_service import AuthService
from utils.response import success_response, error_response

router = APIRouter(prefix="/auth", tags=["认证"])
auth_service = AuthService()


@router.post("/send-code")
async def send_code(
    request: SendCodeRequest,
    db: Session = Depends(get_db),
):
    """发送注册验证码"""
    success, message = auth_service.send_register_code(request.email, db)
    if not success:
        return error_response(400, message)
    return success_response(200, message)


@router.post("/register")
async def register(
    request: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """用户注册"""
    success, message, data = auth_service.register(
        email=request.email,
        code=request.code,
        username=request.username,
        password=request.password,
        db=db,
    )
    if not success:
        return error_response(400, message)

    response.set_cookie(
        key="llm_session",
        value=data["session_id"],
        max_age=86400,
        httponly=True,
        samesite="lax",
    )
    return success_response(201, "注册成功", {"user_id": data["user_id"]})


@router.post("/login")
async def login(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """用户登录"""
    success, message, user = auth_service.login(
        identifier=request.identifier,
        password=request.password,
        db=db,
    )
    if not success:
        if "锁定" in message:
            return error_response(429, message)
        return error_response(401, message, code=40101)

    response.set_cookie(
        key="llm_session",
        value=user.session_id,
        max_age=86400,
        httponly=True,
        samesite="lax",
    )
    return success_response(200, "登录成功", {"user_id": user.id})


@router.post("/logout")
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
):
    """退出登录"""
    auth_service.logout(current_user.session_id)
    response.delete_cookie(key="llm_session")
    return success_response(200, "退出登录成功")


@router.delete("/account")
async def delete_account(
    request: DeleteAccountRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """注销账户"""
    success, message = auth_service.delete_account(
        user_id=current_user.id,
        email=current_user.email,
        code=request.code,
        password=request.password,
        db=db,
    )
    if not success:
        return error_response(400, message)

    response.delete_cookie(key="llm_session")
    return success_response(200, "账户已注销")
