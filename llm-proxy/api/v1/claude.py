"""
Claude 消息接口
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.dependencies import get_current_user_by_apikey, AuthenticatedUser
from app.database import get_db
from services.proxy_service import ProxyService
from log.logger import get_logger
from utils.response import claude_error_response

router = APIRouter(prefix="/messages", tags=["Claude消息"])
proxy_service = ProxyService()
logger = get_logger(__name__)


@router.post("")
async def claude_messages(
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_user_by_apikey),
    db: Session = Depends(get_db),
):
    """转发 Claude Messages 请求"""
    try:
        # 记录请求信息
        logger.info(f"Claude消息请求 - 用户: {auth.user.id}, API Key ID: {auth.api_key_id}")
        
        request_body = await request.body()
        response = await proxy_service.proxy_claude_messages(
            request_body=request_body,
            user=auth.user,
            api_key_id=auth.api_key_id,
            db=db,
        )
        
        # 记录响应状态
        logger.info(f"Claude消息请求完成 - 状态码: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Claude消息请求处理错误: {str(e)}")
        return claude_error_response(f"请求处理错误: {str(e)}", error_type="api_error")
