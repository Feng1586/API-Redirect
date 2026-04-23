"""
文件上传服务（图片上传）
"""

import json
from typing import Dict, Any, Optional
from fastapi import Response
from sqlalchemy.orm import Session

from app.config import settings
from log.logger import get_logger

logger = get_logger(__name__)


class UploadService:
    """文件上传服务"""

    def __init__(self):
        pass

    async def upload_image(
        self,
        request_body: bytes,
        content_type: str,
        user_id: int,
        api_key_id: int,
        db: Session,
    ) -> Response:
        """
        上传图片到上游服务器

        TODO: 实现图片上传请求转发逻辑
        流程：
        1. 解析请求体（multipart/form-data，包含图片文件）
        2. 检查用户余额
        3. 转发请求到上游 POST https://api.apimart.ai/v1/uploads/images
        4. 接收上游响应（包含图片URL或ID）
        5. 记录用量并计费
        6. 透传响应给客户端
        """
        raise NotImplementedError("待实现 - 详见 TODO 注释")
