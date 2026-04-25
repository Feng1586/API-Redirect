"""
视频生成服务
"""

import json
from fastapi import Response
from sqlalchemy.orm import Session

import httpx

from app.config import settings
from services.billing_service import BillingService
from services.user_service import UserService
from repositories.task_record_repo import TaskRecordRepository
from log.logger import get_logger

logger = get_logger(__name__)


class VideoService:
    """视频生成服务"""

    def __init__(self):
        self.billing_service = BillingService()
        self.user_service = UserService()
        self.task_record_repo = TaskRecordRepository()

    async def create_video_generation(
        self,
        request_body: bytes,
        user_id: int,
        api_key_id: int,
        db: Session,
    ) -> Response:
        """
        创建视频生成任务

        流程：
        1. 解析请求体，获取模型名称和 resolution/duration
        2. 检查余额
        3. 查询 video_model_configs 表获取模型配置和分辨率价格，计算费用
        4. 转发请求到上游 POST https://api.apimart.ai/v1/videos/generations
        5. 如果上游返回200，则计费（resolution单价 × duration）
        6. 提取 task_id 存入 task_records 表
        7. 透传响应给客户端
        """
        # 1. 解析请求体
        body_json = json.loads(request_body)
        model = body_json.get("model")

        if not model:
            return Response(
                content=json.dumps({"error": {"code": 40001, "message": "缺少 model 参数", "type": "invalid_request"}}),
                status_code=400,
                media_type="application/json",
            )

        # 2. 检查余额
        is_sufficient, _ = self.billing_service.check_balance(user_id, db)
        if not is_sufficient:
            return Response(
                content=json.dumps({"error": {"code": 402, "message": "账户余额不足，请充值后再试", "type": "insufficient_balance"}}),
                status_code=402,
                media_type="application/json",
            )

        # 3. 检查视频模型配置并计算费用
        resolution = body_json.get("resolution")
        duration = body_json.get("duration")
        cost_result, used_resolution_or_error, used_duration = (
            self.billing_service.calculate_video_cost(model, resolution, duration, db)
        )
        if cost_result is None:
            return Response(
                content=json.dumps({"error": {"code": 40001, "message": used_resolution_or_error, "type": "invalid_request"}}),
                status_code=400,
                media_type="application/json",
            )
        call_cost = cost_result

        # 4. 替换 API-Key 并转发请求到上游
        upstream_url = f"{settings.upstream.base_url}/videos/generations"
        upstream_headers = {
            "Authorization": f"Bearer {settings.upstream.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                upstream = await client.post(
                    upstream_url,
                    headers=upstream_headers,
                    content=request_body,
                )

            # 5. 上游返回200 → 计费
            if upstream.status_code == 200:
                # 扣除余额
                deduct_success = self.user_service.deduct_balance(user_id, call_cost, db)
                if deduct_success:
                    # 记录用量
                    self.billing_service.usage_repo.create(
                        user_id=user_id,
                        api_key_id=api_key_id,
                        model_name=model,
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                        cost=call_cost,
                        db=db,
                    )
                    logger.info(f"视频生成计费成功 - 用户: {user_id}, 模型: {model}, 费用: {call_cost}")
                else:
                    logger.warning(f"视频生成计费失败（余额不足） - 用户: {user_id}, 金额: {call_cost}")

                # 6. 提取 task_id 并存入 task_records 表
                try:
                    response_data = upstream.json()
                    # 上游响应格式: {'code': 200, 'data': [{'status': 'submitted', 'task_id': 'task_xxx'}]}
                    if response_data.get("code") == 200 and response_data.get("data"):
                        task_id = response_data["data"][0].get("task_id")
                        if task_id:
                            self.task_record_repo.create(
                                task_id=str(task_id),
                                api_key_id=api_key_id,
                                db=db,
                            )
                            logger.info(f"视频生成任务记录已保存 - task_id: {task_id}")
                except Exception as parse_err:
                    logger.warning(f"解析上游响应提取 task_id 失败: {str(parse_err)}")

            # 7. 原封不动透传上游响应
            return Response(
                content=upstream.content,
                status_code=upstream.status_code,
                media_type=upstream.headers.get("content-type", "application/json"),
            )

        except httpx.TimeoutException:
            logger.error(f"视频生成上游请求超时 - 用户: {user_id}")
            return Response(
                content=json.dumps({"error": {"code": 504, "message": "上游服务超时，请稍后重试", "type": "upstream_timeout"}}),
                status_code=504,
                media_type="application/json",
            )
        except Exception as e:
            logger.error(f"视频生成上游请求失败 - 用户: {user_id}, error: {str(e)}")
            return Response(
                content=json.dumps({"error": {"code": 502, "message": f"上游服务请求失败: {str(e)}", "type": "upstream_error"}}),
                status_code=502,
                media_type="application/json",
            )

    async def remix_video_generation(
        self,
        task_id: str,
        request_body: bytes,
        user_id: int,
        api_key_id: int,
        db: Session,
    ) -> Response:
        """
        视频续写（Remix）

        流程：
        1. 校验 task_id 所有权
        2. 解析请求体，获取模型名称和 resolution/duration
        3. 检查余额
        4. 查询 video_model_configs 表获取模型配置和分辨率价格，计算费用
        5. 转发请求到上游 POST https://api.apimart.ai/v1/videos/{task_id}/remix
        6. 如果上游返回200，则计费（resolution单价 × duration）
        7. 提取新 task_id 存入 task_records 表
        8. 透传响应给客户端
        """
        # 1. 校验 task_id 所有权
        record = self.task_record_repo.get_by_task_id_and_apikey(
            task_id, api_key_id, db
        )
        if not record:
            return Response(
                content=json.dumps({"error": {"code": 404, "message": "任务不存在或无权限访问", "type": "not_found"}}),
                status_code=404,
                media_type="application/json",
            )

        # 2. 解析请求体
        body_json = json.loads(request_body)
        model = body_json.get("model")

        if not model:
            return Response(
                content=json.dumps({"error": {"code": 40001, "message": "缺少 model 参数", "type": "invalid_request"}}),
                status_code=400,
                media_type="application/json",
            )

        # 3. 检查余额
        is_sufficient, _ = self.billing_service.check_balance(user_id, db)
        if not is_sufficient:
            return Response(
                content=json.dumps({"error": {"code": 402, "message": "账户余额不足，请充值后再试", "type": "insufficient_balance"}}),
                status_code=402,
                media_type="application/json",
            )

        # 4. 检查视频模型配置并计算费用
        resolution = body_json.get("resolution")
        duration = body_json.get("duration")
        cost_result, used_resolution_or_error, used_duration = (
            self.billing_service.calculate_video_cost(model, resolution, duration, db)
        )
        if cost_result is None:
            return Response(
                content=json.dumps({"error": {"code": 40001, "message": used_resolution_or_error, "type": "invalid_request"}}),
                status_code=400,
                media_type="application/json",
            )
        call_cost = cost_result

        # 5. 替换 API-Key 并转发请求到上游
        upstream_url = f"{settings.upstream.base_url}/videos/{task_id}/remix"
        upstream_headers = {
            "Authorization": f"Bearer {settings.upstream.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                upstream = await client.post(
                    upstream_url,
                    headers=upstream_headers,
                    content=request_body,
                )

            # 6. 上游返回200 → 计费
            if upstream.status_code == 200:
                # 扣除余额
                deduct_success = self.user_service.deduct_balance(user_id, call_cost, db)
                if deduct_success:
                    # 记录用量
                    self.billing_service.usage_repo.create(
                        user_id=user_id,
                        api_key_id=api_key_id,
                        model_name=model,
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                        cost=call_cost,
                        db=db,
                    )
                    logger.info(f"视频续写计费成功 - 用户: {user_id}, 模型: {model}, 费用: {call_cost}")
                else:
                    logger.warning(f"视频续写计费失败（余额不足） - 用户: {user_id}, 金额: {call_cost}")

                # 7. 提取新 task_id 并存入 task_records 表
                try:
                    response_data = upstream.json()
                    if response_data.get("code") == 200 and response_data.get("data"):
                        new_task_id = response_data["data"][0].get("task_id")
                        if new_task_id:
                            self.task_record_repo.create(
                                task_id=str(new_task_id),
                                api_key_id=api_key_id,
                                db=db,
                            )
                            logger.info(f"视频续写任务记录已保存 - task_id: {new_task_id}")
                except Exception as parse_err:
                    logger.warning(f"解析上游响应提取 task_id 失败: {str(parse_err)}")

            # 8. 原封不动透传上游响应
            return Response(
                content=upstream.content,
                status_code=upstream.status_code,
                media_type=upstream.headers.get("content-type", "application/json"),
            )

        except httpx.TimeoutException:
            logger.error(f"视频续写上游请求超时 - 用户: {user_id}")
            return Response(
                content=json.dumps({"error": {"code": 504, "message": "上游服务超时，请稍后重试", "type": "upstream_timeout"}}),
                status_code=504,
                media_type="application/json",
            )
        except Exception as e:
            logger.error(f"视频续写上游请求失败 - 用户: {user_id}, error: {str(e)}")
            return Response(
                content=json.dumps({"error": {"code": 502, "message": f"上游服务请求失败: {str(e)}", "type": "upstream_error"}}),
                status_code=502,
                media_type="application/json",
            )
