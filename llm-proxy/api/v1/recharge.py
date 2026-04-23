"""
充值接口（预留）
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from models.user import User
from schemas.recharge import CreateRechargeRequest, RechargeResponse
from services.recharge_service import RechargeService
from utils.response import success_response, error_response

router = APIRouter(prefix="/recharge", tags=["充值"])
recharge_service = RechargeService()


@router.post("/create", status_code=201)
async def create_recharge_order(
    request: CreateRechargeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建充值订单"""
    success, message, order = recharge_service.create_order(
        user_id=current_user.id,
        amount=request.amount,
        db=db,
    )
    if not success:
        return error_response(400, message)

    return success_response(201, "订单创建成功", {
        "order_no": order.order_no,
        "amount": float(order.amount),
        "paypal_url": f"https://www.paypal.com/pay?order={order.order_no}",
    })


@router.post("/callback")
async def recharge_callback():
    """支付回调"""
    # PayPal 回调处理
    pass


@router.get("/{order_no}")
async def get_order_status(
    order_no: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询订单状态"""
    order = recharge_service.get_order(order_no, db)
    if not order:
        return error_response(404, "订单不存在", code=40400)

    return success_response(200, "success", {
        "order_no": order.order_no,
        "status": order.status,
        "amount": float(order.amount),
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
    })
