"""
OpenAI 响应接口
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user_by_apikey, AuthenticatedUser
from services.proxy_service import ProxyService

router = APIRouter(prefix="/responses", tags=["OpenAI响应"])
proxy_service = ProxyService()


@router.post("")
async def openai_responses(
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_user_by_apikey),
    db: Session = Depends(get_db),
):
    """转发 OpenAI Responses 请求"""
    request_body = await request.body()
    return await proxy_service.proxy_openai_responses(
        request_body=request_body,
        user=auth.user,
        api_key_id=auth.api_key_id,
        db=db,
    )
