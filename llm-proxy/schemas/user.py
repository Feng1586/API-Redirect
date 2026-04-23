"""
用户请求/响应模型
"""

from typing import Optional
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    """注册请求"""
    email: EmailStr
    code: str
    username: str
    password: str


class LoginRequest(BaseModel):
    """登录请求"""
    identifier: str  # 邮箱或用户名
    password: str


class SendCodeRequest(BaseModel):
    """发送验证码请求"""
    email: EmailStr


class DeleteAccountRequest(BaseModel):
    """注销账户请求"""
    code: str
    password: str


class UserProfile(BaseModel):
    """用户信息"""
    balance: float
    monthly_spending: float
    api_keys: list[dict]


class BillItem(BaseModel):
    """账单项"""
    order_no: str
    status: str
    amount: float
    created_at: str


class BillResponse(BaseModel):
    """账单响应"""
    total: int
    page: int
    page_size: int
    items: list[BillItem]
