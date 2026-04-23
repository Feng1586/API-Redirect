"""
充值请求/响应模型
"""

from typing import Optional
from pydantic import BaseModel


class CreateRechargeRequest(BaseModel):
    """创建充值订单请求"""
    amount: float
    currency: str = "USD"


class RechargeResponse(BaseModel):
    """充值响应"""
    order_no: str
    amount: float
    paypal_url: str


class OrderStatus(BaseModel):
    """订单状态"""
    order_no: str
    status: str
    amount: float
    created_at: str
    paid_at: Optional[str] = None
