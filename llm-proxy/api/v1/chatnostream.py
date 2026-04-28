"""
对话转发接口 - OpenAI Chat Completions（默认非流式）
"""

import json
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user_by_apikey, AuthenticatedUser
from services.proxy_service import ProxyService
from log.logger import get_logger
from utils.response import openai_error_response

router = APIRouter(prefix="/nostream/chat", tags=["OpenAI对话（非流式）"])
proxy_service = ProxyService()
logger = get_logger(__name__)


@router.post("/completions")
async def chat_completions(
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_user_by_apikey),
    db: Session = Depends(get_db),
):
    """转发 OpenAI Chat Completions 请求（默认非流式）"""
    try:
        body = await request.body()
        body_json = json.loads(body)

        # 默认非流式：只有客户端明确传 stream=true 时才走流式
        if body_json.get("stream") is not True:
            body_json["stream"] = False

        request_body = json.dumps(body_json).encode("utf-8")
        return await proxy_service.proxy_chat_completions(
            request_body=request_body,
            user=auth.user,
            api_key_id=auth.api_key_id,
            db=db,
        )
    except Exception as e:
        logger.error(f"Chat(非流式)请求处理错误: {str(e)}")
        return openai_error_response(40003, f"请求处理错误: {str(e)}")
