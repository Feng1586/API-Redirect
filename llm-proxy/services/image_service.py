"""
图片生成服务
"""

import json
from typing import Dict, Any, Optional
from fastapi import Response
from sqlalchemy.orm import Session

from app.config import settings
from log.logger import get_logger

logger = get_logger(__name__)


class ImageService:
    """图片生成服务"""

    def __init__(self):
        pass

    async def create_image_generation(
        self,
        request_body: bytes,
        user_id: int,
        api_key_id: int,
        db: Session,
    ) -> Response:
        """
        创建图片生成任务

        TODO: 实现图片生成请求转发逻辑
        流程：
        1. 解析请求体，获取模型和参数
        2. 检查用户余额
        3. 检查模型是否启用
        4. 转发请求到上游 POST https://api.apimart.ai/v1/images/generations
        5. 接收上游响应（包含任务ID task_id）
        6. 将 task_id 与 api_key_id 关联存入 task_records 表
        7. 记录用量并计费
        8. 透传响应给客户端
        """
        raise NotImplementedError("待实现 - 详见 TODO 注释")
