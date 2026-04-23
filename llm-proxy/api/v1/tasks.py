"""
任务查询接口
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user_by_apikey, AuthenticatedUser
from services.task_service import TaskService
from log.logger import get_logger
from utils.response import error_response

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

    TODO: 实现任务查询请求的完整转发逻辑
    """
    try:
        logger.info(f"任务查询请求 - 用户: {auth.user.id}, 任务ID: {task_id}")
        return await task_service.query_task(
            task_id=task_id,
            user_id=auth.user.id,
            api_key_id=auth.api_key_id,
            db=db,
        )
    except NotImplementedError:
        return error_response(50001, "任务查询接口尚未实现")
    except Exception as e:
        logger.error(f"任务查询请求处理错误: {str(e)}")
        return error_response(40003, f"请求处理错误: {str(e)}")
