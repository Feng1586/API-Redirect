"""
任务查询接口
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user_by_apikey, AuthenticatedUser
from services.task_service import TaskService
from log.logger import get_logger
from utils.response import openai_error_response

router = APIRouter(prefix="/tasks", tags=["任务查询"])
task_service = TaskService()
logger = get_logger(__name__)


@router.get("/{task_id}")
async def query_task(
    request: Request,
    task_id: str,
    auth: AuthenticatedUser = Depends(get_current_user_by_apikey),
    db: Session = Depends(get_db),
):
    """
    查询图片/视频生成任务进度

    将请求转发至上游: GET https://api.apimart.ai/v1/tasks/{task_id}
    任务完成时上游响应中会包含结果URL
    """
    try:
        logger.info(f"任务查询请求 - 用户: {auth.user.id}, 任务ID: {task_id}")
        return await task_service.query_task(
            task_id=task_id,
            api_key_id=auth.api_key_id,
            request=request,
            db=db,
        )
    except Exception as e:
        logger.error(f"任务查询请求处理错误: {str(e)}")
        return openai_error_response(40003, f"请求处理错误: {str(e)}")


@router.post("/{task_id}/refund")
async def refund_task(
    task_id: str,
    auth: AuthenticatedUser = Depends(get_current_user_by_apikey),
    db: Session = Depends(get_db),
):
    """
    任务退款

    当上游任务执行失败时，通过此接口申请退款。
    流程：
    1. 校验该 task_id 属于当前 API-Key
    2. 查询上游任务状态
    3. 如果上游状态为 failed，则将费用退回用户余额
    4. 更新 task_records 状态为 failed
    """
    try:
        logger.info(f"任务退款请求 - 用户: {auth.user.id}, API Key ID: {auth.api_key_id}, 任务ID: {task_id}")
        return await task_service.refund_task(
            task_id=task_id,
            api_key_id=auth.api_key_id,
            db=db,
        )
    except Exception as e:
        logger.error(f"任务退款请求处理错误: {str(e)}")
        return openai_error_response(40003, f"请求处理错误: {str(e)}")
