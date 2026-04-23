"""
角色任务查询服务（Sora2 查询角色）
"""

import json
from fastapi import Response
from sqlalchemy.orm import Session

import httpx

from app.config import settings
from repositories.task_record_repo import TaskRecordRepository
from log.logger import get_logger

logger = get_logger(__name__)


class CharacterService:
    """角色任务查询服务"""

    def __init__(self):
        self.task_record_repo = TaskRecordRepository()

    async def query_character_task(
        self,
        task_id: str,
        api_key_id: int,
        db: Session,
    ) -> Response:
        """
        查询角色任务进度

        流程：
        1. 校验 task_id 所有权
        2. 转发请求到上游 GET https://api.apimart.ai/v1/characters_tasks/{task_id}
        3. 透传上游响应给客户端
        """
        # 1. 校验 task_id 所有权
        record = self.task_record_repo.get_by_task_id_and_apikey(
            task_id, api_key_id, db
        )
        if not record:
            return Response(
                content=json.dumps({
                    "error": {
                        "code": 404,
                        "message": "任务不存在或无权限访问",
                        "type": "not_found",
                    }
                }),
                status_code=404,
                media_type="application/json",
            )

        # 2. 替换 API-Key 并转发请求到上游
        upstream_url = f"{settings.upstream.base_url}/characters_tasks/{task_id}"
        upstream_headers = {
            "Authorization": f"Bearer {settings.upstream.api_key}",
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                upstream = await client.get(
                    upstream_url,
                    headers=upstream_headers,
                )

            logger.info(f"角色任务查询成功 - task_id: {task_id}, 上游状态码: {upstream.status_code}")

            # 3. 原封不动透传上游响应
            return Response(
                content=upstream.content,
                status_code=upstream.status_code,
                media_type=upstream.headers.get("content-type", "application/json"),
            )

        except httpx.TimeoutException:
            logger.error(f"角色任务查询上游请求超时 - task_id: {task_id}")
            return Response(
                content=json.dumps({"error": {"code": 504, "message": "上游服务超时，请稍后重试", "type": "upstream_timeout"}}),
                status_code=504,
                media_type="application/json",
            )
        except Exception as e:
            logger.error(f"角色任务查询上游请求失败 - task_id: {task_id}, error: {str(e)}")
            return Response(
                content=json.dumps({"error": {"code": 502, "message": f"上游服务请求失败: {str(e)}", "type": "upstream_error"}}),
                status_code=502,
                media_type="application/json",
            )
