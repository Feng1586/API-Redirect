"""
文件上传接口（图片上传）
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user_by_apikey, AuthenticatedUser
from services.upload_service import UploadService
from log.logger import get_logger
from utils.response import error_response

router = APIRouter(prefix="/uploads", tags=["文件上传"])
upload_service = UploadService()
logger = get_logger(__name__)


@router.post("/images")
async def upload_image(
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_user_by_apikey),
    db: Session = Depends(get_db),
):
    """
    上传图片到上游服务器

    将请求转发至上游: POST https://api.apimart.ai/v1/uploads/images

    TODO: 实现图片上传请求的完整转发逻辑
    """
    try:
        request_body = await request.body()
        content_type = request.headers.get("content-type", "")
        logger.info(f"图片上传请求 - 用户: {auth.user.id}")
        return await upload_service.upload_image(
            request_body=request_body,
            content_type=content_type,
            user_id=auth.user.id,
            api_key_id=auth.api_key_id,
            db=db,
        )
    except NotImplementedError:
        return error_response(50001, "图片上传接口尚未实现")
    except Exception as e:
        logger.error(f"图片上传请求处理错误: {str(e)}")
        return error_response(40003, f"请求处理错误: {str(e)}")
