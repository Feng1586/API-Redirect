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
from services.user_service import UserService
from log.logger import get_logger

logger = get_logger(__name__)


class TaskService:
    """任务查询服务（用于查询图片/视频生成任务进度）"""

    def __init__(self):
        self.task_record_repo = TaskRecordRepository()
        self.user_service = UserService()

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

    async def refund_task(
        self,
        task_id: str,
        api_key_id: int,
        db: Session,
    ) -> Response:
        """
        任务退款

        流程：
        1. 查询 task_records 表，确认该 task_id 属于当前 api_key_id（权限校验）
        2. 获取该任务的 cost 和当前 status（仅 completed 状态可退款）
        3. 向上游发起任务查询 GET https://api.apimart.ai/v1/tasks/{task_id}
        4. 如果上游响应中 data.status 为 "failed"，则执行退款操作
        5. 将花费金额加回用户余额，并将 task_records.status 设为 "failed"
        6. 透传上游响应给客户端（非 failed 状态直接透传）
        """
        # 1. 权限校验
        record = self.task_record_repo.get_by_task_id_and_apikey(
            task_id, api_key_id, db
        )
        if not record:
            return Response(
                content=json.dumps({
                    "error": {"code": 404, "message": "任务不存在或无权限访问", "type": "not_found"},
                }),
                status_code=404,
                media_type="application/json",
            )

        # 2. 只有 completed 状态可退款
        if record.status != "completed":
            return Response(
                content=json.dumps({
                    "error": {"code": 40001, "message": "该任务状态不允许退款", "type": "invalid_request"},
                }),
                status_code=400,
                media_type="application/json",
            )

        refund_cost = float(record.cost) if record.cost else 0.0

        # 3. 向上游查询任务状态
        upstream_url = f"{settings.upstream.base_url}/tasks/{task_id}"
        upstream_headers = {
            "Authorization": f"Bearer {settings.upstream.api_key}",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                upstream = await client.get(upstream_url, headers=upstream_headers)

            response_data = upstream.json()

            # 4. 判断上游任务状态是否 failed
            # 上游响应: {"code": 200, "data": {"status": "failed", ...}}
            upstream_status = (
                response_data.get("data", {}).get("status") if upstream.status_code == 200 else None
            )

            if upstream_status != "failed":
                # 非 failed 状态，直接透传上游响应
                return Response(
                    content=upstream.content,
                    status_code=upstream.status_code,
                    media_type=upstream.headers.get("content-type", "application/json"),
                )

            # 5. 执行退款：加回余额 + 更新状态
            if refund_cost > 0:
                # 通过 api_key_id 找到所属用户
                from repositories.apikey_repo import ApiKeyRepository
                apikey_repo = ApiKeyRepository()
                api_key_obj = apikey_repo.get_by_id(record.api_key_id, db)
                if api_key_obj:
                    refund_success = self.user_service.add_balance(
                        api_key_obj.user_id, refund_cost, db
                    )
                    if refund_success:
                        logger.info(f"任务退款成功 - task_id: {task_id}, 退款金额: {refund_cost}")
                    else:
                        logger.warning(f"任务退款失败 - task_id: {task_id}, 金额: {refund_cost}")
                else:
                    logger.warning(f"任务退款失败 - 未找到 API-Key 记录: {record.api_key_id}")
            else:
                logger.info(f"任务退款跳过（费用为0） - task_id: {task_id}")

            # 更新任务状态为 failed
            self.task_record_repo.update_status(task_id, "failed", db)

            # 返回退款成功响应
            return Response(
                content=json.dumps({
                    "code": 200,
                    "message": "退款成功",
                    "data": {
                        "task_id": task_id,
                        "refund_amount": refund_cost,
                        "status": "failed",
                    },
                }),
                status_code=200,
                media_type="application/json",
            )

        except httpx.TimeoutException:
            logger.error(f"任务退款查询超时 - task_id: {task_id}")
            return Response(
                content=json.dumps({
                    "error": {"code": 504, "message": "上游服务超时，请稍后重试", "type": "upstream_timeout"},
                }),
                status_code=504,
                media_type="application/json",
            )
        except Exception as e:
            logger.error(f"任务退款上游请求失败 - task_id: {task_id}, error: {str(e)}")
            return Response(
                content=json.dumps({
                    "error": {"code": 502, "message": f"上游服务请求失败: {str(e)}", "type": "upstream_error"},
                }),
                status_code=502,
                media_type="application/json",
            )
