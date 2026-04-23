"""
充值接口
集成 PayPal 支付流程：创建订单 → 用户支付 → 捕获资金
"""

import hashlib
import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from models.user import User
from schemas.recharge import (
    CreatePayPalOrderRequest,
    CapturePayPalOrderRequest,
    CapturePayPalOrderResponse,
)
from services.recharge_service import RechargeService
from utils.response import success_response, error_response
from log.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/recharge", tags=["充值"])
recharge_service = RechargeService()


@router.post("/paypal/create", status_code=201)
async def create_paypal_order(
    request: CreatePayPalOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 1: 创建 PayPal 订单

    流程:
    - 生成本地订单号
    - 调用 PayPal API 创建订单（intent=CAPTURE，直接扣款）
    - 返回 approve_url，前端重定向用户到该 URL 完成支付

    测试说明:
    - 使用 Postman 调用此接口
    - 返回的 approve_url 复制到浏览器中打开
    - 使用沙箱买家账号登录完成支付
    - 然后将返回的 order_no 传给 Step 2 的捕获接口
    """
    success, message, data = await recharge_service.create_order(
        user_id=current_user.id,
        amount=request.amount,
        currency=request.currency,
        return_url=request.return_url,
        cancel_url=request.cancel_url,
        db=db,
    )
    if not success:
        return error_response(400, message)

    return success_response(201, "订单创建成功", data)


@router.post("/paypal/capture")
async def capture_paypal_order(
    request: CapturePayPalOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 2: 捕获 PayPal 订单（确认扣款）

    流程:
    - 用户在 PayPal 页面完成支付后，调用此接口
    - 调用 PayPal API 捕获资金
    - 更新订单状态为 paid
    - 为用户增加余额

    测试说明:
    - 使用 Step 1 返回的 order_no 作为参数
    - 成功后会返回捕获详情（含手续费信息）
    """
    # 验证订单属于当前用户
    order = recharge_service.get_order(request.order_no, db)
    if not order:
        return error_response(404, "订单不存在")
    if order.user_id != current_user.id:
        return error_response(403, "无权操作该订单")

    success, message, data = await recharge_service.capture_order(
        order_no=request.order_no,
        db=db,
    )
    if not success:
        return error_response(400, message)

    return success_response(200, "充值成功", data)


@router.post("/paypal/webhook")
async def paypal_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Step 3 (可选/生产): PayPal Webhook 回调

    PayPal 在支付成功后会异步通知此接口。
    生产环境建议同时实现此接口防止掉单。

    安全验证:
    - 验证 PayPal 签名
    - 需要先在 PayPal Developer Dashboard 配置 Webhook URL
    """
    # 获取原始请求体（用于签名验证）
    body = await request.body()
    event_body = json.loads(body.decode("utf-8"))

    # 获取 PayPal 签名头
    webhook_headers = {
        "PAYPAL-AUTH-ALGO": request.headers.get("paypal-auth-algo", ""),
        "PAYPAL-CERT-URL": request.headers.get("paypal-cert-url", ""),
        "PAYPAL-TRANSMISSION-ID": request.headers.get("paypal-transmission-id", ""),
        "PAYPAL-TRANSMISSION-SIG": request.headers.get("paypal-transmission-sig", ""),
        "PAYPAL-TRANSMISSION-TIME": request.headers.get("paypal-transmission-time", ""),
    }

    # 获取 Webhook ID（需要从配置或环境变量中读取）
    # webhook_id = settings.paypal.webhook_id  # 需要在 config.yaml 中添加

    # 处理 Webhook 事件
    # TODO: 配置 Webhook ID 后取消注释
    # success, message = await recharge_service.handle_paypal_webhook(
    #     event_body=event_body,
    #     webhook_headers=webhook_headers,
    #     webhook_id=webhook_id,
    #     db=db,
    # )
    # if not success:
    #     return error_response(400, message)

    logger.info(f"收到 PayPal Webhook: {event_body.get('event_type', '')}")
    return success_response(200, "received")


@router.get("/{order_no}")
async def get_order_status(
    order_no: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询订单状态"""
    order = recharge_service.get_order(order_no, db)
    if not order:
        return error_response(404, "订单不存在")

    if order.user_id != current_user.id:
        return error_response(403, "无权查看该订单")

    return success_response(200, "success", {
        "order_no": order.order_no,
        "status": order.status,
        "amount": float(order.amount),
        "external_no": order.external_no,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
    })
