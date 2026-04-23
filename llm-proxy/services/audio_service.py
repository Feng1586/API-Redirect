"""
音频处理服务（语音转文字、文字转语音）
"""

import json
from typing import Dict, Any, Optional
from fastapi import Response
from sqlalchemy.orm import Session

from app.config import settings
from log.logger import get_logger

logger = get_logger(__name__)


class AudioService:
    """音频处理服务"""

    def __init__(self):
        pass

    async def create_transcription(
        self,
        request_body: bytes,
        user_id: int,
        api_key_id: int,
        db: Session,
    ) -> Response:
        """
        语音转文字

        TODO: 实现语音转文字请求转发逻辑
        流程：
        1. 解析请求体（multipart/form-data，包含音频文件）
        2. 检查用户余额
        3. 转发请求到上游 POST https://api.apimart.ai/v1/audio/transcriptions
        4. 记录用量并计费
        5. 透传响应给客户端
        """
        raise NotImplementedError("待实现 - 详见 TODO 注释")

    async def create_speech(
        self,
        request_body: bytes,
        user_id: int,
        api_key_id: int,
        db: Session,
    ) -> Response:
        """
        文字转语音

        TODO: 实现文字转语音请求转发逻辑
        流程：
        1. 解析请求体，获取模型、输入文本和语音参数
        2. 检查用户余额
        3. 转发请求到上游 POST https://api.apimart.ai/v1/audio/speech
        4. 记录用量并计费
        5. 返回音频流给客户端
        """
        raise NotImplementedError("待实现 - 详见 TODO 注释")
