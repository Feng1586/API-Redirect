"""
OpenAI 响应接口
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user_by_apikey, AuthenticatedUser
from services.proxy_service import ProxyService
from log.logger import get_logger
from utils.response import openai_error_response

router = APIRouter(prefix="/responses", tags=["OpenAI响应"])
proxy_service = ProxyService()
logger = get_logger(__name__)


@router.post("")
async def openai_responses(
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_user_by_apikey),
    db: Session = Depends(get_db),
):
    """转发 OpenAI Responses 请求"""
    try:
        request_body = await request.body()
        return await proxy_service.proxy_openai_responses(
            request_body=request_body,
            user=auth.user,
            api_key_id=auth.api_key_id,
            db=db,
        )
    except Exception as e:
        logger.error(f"OpenAI Responses请求处理错误: {str(e)}")
        return openai_error_response(40003, f"请求处理错误: {str(e)}")
