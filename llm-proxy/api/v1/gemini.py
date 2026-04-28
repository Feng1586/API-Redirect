"""
Gemini 原生接口
"""

from fastapi import APIRouter, Depends, Request

from app.dependencies import get_current_user_by_apikey, AuthenticatedUser
from app.database import get_db
from services.proxy_service import ProxyService
from log.logger import get_logger
from utils.response import openai_error_response

router = APIRouter(prefix="/beta/models", tags=["Gemini"])
proxy_service = ProxyService()
logger = get_logger(__name__)


@router.post("/{model}:{method}")
async def gemini_proxy(
    request: Request,
    model: str,
    method: str,
    auth: AuthenticatedUser = Depends(get_current_user_by_apikey),
    db = Depends(get_db),
):
    """转发 Gemini 请求"""
    try:
        # 读取请求体
        request_body = await request.body()
        
        # 调用代理服务
        return await proxy_service.proxy_gemini(
            model=model,
            method=method,
            request_body=request_body,
            user=auth.user,
            api_key_id=auth.api_key_id,
            db=db,
        )
    except Exception as e:
        logger.error(f"Gemini请求处理错误: {str(e)}")
        return openai_error_response(40003, f"请求处理错误: {str(e)}", error_type="upstream_error")
