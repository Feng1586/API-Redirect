"""
用户信息接口
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from models.user import User
from schemas.user import UserProfile, BillResponse
from services.user_service import UserService
from utils.response import success_response

router = APIRouter(prefix="/user", tags=["用户"])
user_service = UserService()


@router.get("/profile")
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取用户信息"""
    profile = user_service.get_profile(current_user.id, db)
    return success_response(200, "success", profile)


@router.get("/bill")
async def get_bill(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取用户账单"""
    bills = user_service.get_bills(current_user.id, page, page_size, db)
    return success_response(200, "success", bills)
