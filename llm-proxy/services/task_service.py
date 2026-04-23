"""
任务查询服务
"""

import json
from typing import Dict, Any, Optional
from fastapi import Request, Response
from sqlalchemy.orm import Session

import httpx

from app.config import settings
from repositories.task_record_repo import TaskRecordRepository
from log.logger import get_logger

logger = get_logger(__name__)


class TaskService:
    """任务查询服务（用于查询图片/视频生成任务进度）"""

    def __init__(self):
        self.task_record_repo = TaskRecordRepository()

    async def query_task(
        self,
        task_id: str,
        api_key_id: int,
        request: Request,
        db: Session,
    ) -> Response:
        """
        查询任务进度

        流程：
        1. 查询 task_records 表，确认该 task_id 属于当前 api_key_id（防止越权查询）
        2. 转发请求到上游 GET https://api.apimart.ai/v1/tasks/{task_id}
        3. 透传上游响应给客户端
        """
        # 1. 权限校验：确认该 task_id 是由当前 API-Key 创建的
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

        # 2. 转发请求到上游
        upstream_url = f"{settings.upstream.base_url}/tasks/{task_id}"
        upstream_headers = {
            "Authorization": f"Bearer {settings.upstream.api_key}",
        }

        # 透传客户端的所有查询参数
        query_params = dict(request.query_params)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                upstream = await client.get(
                    upstream_url,
                    headers=upstream_headers,
                    params=query_params,
                )

            # 3. 原封不动透传上游响应
            return Response(
                content=upstream.content,
                status_code=upstream.status_code,
                media_type=upstream.headers.get("content-type", "application/json"),
            )
        except httpx.TimeoutException:
            logger.error(f"任务查询超时 - task_id: {task_id}")
            return Response(
                content=json.dumps({
                    "error": {
                        "code": 504,
                        "message": "上游服务超时，请稍后重试",
                        "type": "upstream_timeout",
                    }
                }),
                status_code=504,
                media_type="application/json",
            )
        except Exception as e:
            logger.error(f"任务查询上游请求失败 - task_id: {task_id}, error: {str(e)}")
            return Response(
                content=json.dumps({
                    "error": {
                        "code": 502,
                        "message": f"上游服务请求失败: {str(e)}",
                        "type": "upstream_error",
                    }
                }),
                status_code=502,
                media_type="application/json",
            )
