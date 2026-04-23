"""
视频生成接口
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user_by_apikey, AuthenticatedUser
from services.video_service import VideoService
from log.logger import get_logger
from utils.response import error_response

router = APIRouter(prefix="/videos", tags=["视频生成"])
video_service = VideoService()
logger = get_logger(__name__)


@router.post("/generations")
async def create_video_generation(
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_user_by_apikey),
    db: Session = Depends(get_db),
):
    """
    创建视频生成任务

    将请求转发至上游: POST https://api.apimart.ai/v1/videos/generations
    上游返回任务ID，用户可通过 /v1/tasks/{task_id} 查询进度
    """
    try:
        request_body = await request.body()
        logger.info(f"视频生成请求 - 用户: {auth.user.id}, API Key ID: {auth.api_key_id}")
        return await video_service.create_video_generation(
            request_body=request_body,
            user_id=auth.user.id,
            api_key_id=auth.api_key_id,
            db=db,
        )
    except Exception as e:
        logger.error(f"视频生成请求处理错误: {str(e)}")
        return error_response(40003, f"请求处理错误: {str(e)}")


@router.post("/{task_id}/remix")
async def remix_video_generation(
    task_id: str,
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_user_by_apikey),
    db: Session = Depends(get_db),
):
    """
    视频续写（Remix）

    将请求转发至上游: POST https://api.apimart.ai/v1/videos/{task_id}/remix
    需要校验该 task_id 属于当前 API-Key
    """
    try:
        request_body = await request.body()
        logger.info(f"视频续写请求 - 用户: {auth.user.id}, API Key ID: {auth.api_key_id}, task_id: {task_id}")
        return await video_service.remix_video_generation(
            task_id=task_id,
            request_body=request_body,
            user_id=auth.user.id,
            api_key_id=auth.api_key_id,
            db=db,
        )
    except Exception as e:
        logger.error(f"视频续写请求处理错误: {str(e)}")
        return error_response(40003, f"请求处理错误: {str(e)}")
