"""
图片生成接口
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user_by_apikey, AuthenticatedUser
from services.image_service import ImageService
from log.logger import get_logger
from utils.response import error_response

router = APIRouter(prefix="/images", tags=["图片生成"])
image_service = ImageService()
logger = get_logger(__name__)


@router.post("/generations")
async def create_image_generation(
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_user_by_apikey),
    db: Session = Depends(get_db),
):
    """
    创建图片生成任务

    将请求转发至上游: POST https://api.apimart.ai/v1/images/generations
    上游返回任务ID，用户可通过 /v1/tasks/{task_id} 查询进度
    """
    try:
        request_body = await request.body()
        logger.info(f"图片生成请求 - 用户: {auth.user.id}, API Key ID: {auth.api_key_id}")
        return await image_service.create_image_generation(
            request_body=request_body,
            user_id=auth.user.id,
            api_key_id=auth.api_key_id,
            db=db,
        )
    except Exception as e:
        logger.error(f"图片生成请求处理错误: {str(e)}")
        return error_response(40003, f"请求处理错误: {str(e)}")
