"""
API-Key请求/响应模型
"""

from typing import Optional
from pydantic import BaseModel


class CreateApiKeyRequest(BaseModel):
    """创建API-Key请求"""
    name: str


class UpdateApiKeyRequest(BaseModel):
    """修改API-Key备注请求"""
    name: str


class ApiKeyResponse(BaseModel):
    """API-Key响应"""
    id: int
    name: str
    key: str
    created_at: str
    last_used_at: Optional[str] = None
