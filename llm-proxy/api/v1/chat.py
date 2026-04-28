"""
对话转发接口 - OpenAI Chat Completions
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user_by_apikey, AuthenticatedUser
from services.proxy_service import ProxyService
from log.logger import get_logger
from utils.response import openai_error_response

router = APIRouter(prefix="/chat", tags=["OpenAI对话"])
proxy_service = ProxyService()
logger = get_logger(__name__)


@router.post("/completions")
async def chat_completions(
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_user_by_apikey),
    db: Session = Depends(get_db),
):
    """转发 OpenAI Chat Completions 请求"""
    try:
        request_body = await request.body()
        return await proxy_service.proxy_chat_completions(
            request_body=request_body,
            user=auth.user,
            api_key_id=auth.api_key_id,
            db=db,
        )
    except Exception as e:
        logger.error(f"Chat请求处理错误: {str(e)}")
        return openai_error_response(40003, f"请求处理错误: {str(e)}")
