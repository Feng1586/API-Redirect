"""
充值请求/响应模型
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CreateRechargeRequest(BaseModel):
    """创建充值订单请求"""
    amount: float = Field(..., gt=0, description="充值金额")
    currency: str = "USD"


class CreatePayPalOrderRequest(BaseModel):
    """创建 PayPal 订单请求"""
    amount: float = Field(..., gt=0, description="充值金额")
    currency: str = "USD"
    return_url: str = ""
    cancel_url: str = ""


class RechargeResponse(BaseModel):
    """充值响应"""
    order_no: str
    amount: float
    paypal_url: str


class CreatePayPalOrderResponse(BaseModel):
    """创建 PayPal 订单响应"""
    order_no: str
    amount: float
    currency: str
    paypal_order_id: str
    approve_url: str
    status: str


class CapturePayPalOrderRequest(BaseModel):
    """捕获 PayPal 订单请求"""
    order_no: str = Field(..., description="本地订单号")


class CapturePayPalOrderResponse(BaseModel):
    """捕获 PayPal 订单响应"""
    order_no: str
    paypal_order_id: str
    capture_id: str
    status: str
    amount: float
    currency: str
    paypal_fee: float
    net_amount: float
    payer_email: Optional[str] = None


class OrderStatus(BaseModel):
    """订单状态"""
    order_no: str
    status: str
    amount: float
    created_at: str
    paid_at: Optional[str] = None
