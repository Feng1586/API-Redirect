"""
文件上传服务（图片上传）
"""

import json
from fastapi import Response
from sqlalchemy.orm import Session

import httpx

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

        流程：
        1. 将请求体原封不动转发至上游 POST https://api.apimart.ai/v1/uploads/images
        2. 透传响应给客户端（免费接口，不计费）
        """
        upstream_url = f"{settings.upstream.base_url}/uploads/images"
        upstream_headers = {
            "Authorization": f"Bearer {settings.upstream.api_key}",
            "Content-Type": content_type,  # 保留原始 multipart boundary
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                upstream = await client.post(
                    upstream_url,
                    headers=upstream_headers,
                    content=request_body,
                )

            logger.info(f"图片上传成功 - 用户: {user_id}, 上游状态码: {upstream.status_code}")

            # 原封不动透传上游响应
            return Response(
                content=upstream.content,
                status_code=upstream.status_code,
                media_type=upstream.headers.get("content-type", "application/json"),
            )

        except httpx.TimeoutException:
            logger.error(f"图片上传上游请求超时 - 用户: {user_id}")
            return Response(
                content=json.dumps({"error": {"code": 504, "message": "上游服务超时，请稍后重试", "type": "upstream_timeout"}}),
                status_code=504,
                media_type="application/json",
            )
        except Exception as e:
            logger.error(f"图片上传上游请求失败 - 用户: {user_id}, error: {str(e)}")
            return Response(
                content=json.dumps({"error": {"code": 502, "message": f"上游服务请求失败: {str(e)}", "type": "upstream_error"}}),
                status_code=502,
                media_type="application/json",
            )
