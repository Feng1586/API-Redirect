"""
Gemini 原生接口
"""

from fastapi import APIRouter, Depends, Request, Response

from app.dependencies import get_current_user_by_apikey, AuthenticatedUser
from app.database import get_db
from services.proxy_service import ProxyService
from utils.response import error_response

router = APIRouter(prefix="/beta/models", tags=["Gemini"])
proxy_service = ProxyService()


@router.post("/{model}:{method}")
async def gemini_proxy(
    request: Request,
    model: str,
    method: str,
    auth_user: AuthenticatedUser = Depends(get_current_user_by_apikey),
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
            user=auth_user.user,
            api_key_id=auth_user.api_key_id,
            db=db,
        )
    except Exception as e:
        # 创建一个合适的错误响应，使用 FastAPI Response 而不是 error_response 函数
        import json
        from fastapi import Response
        error_data = {"error": {"code": 40003, "message": f"请求处理错误: {str(e)}", "type": "upstream_error"}}
        return Response(
            content=json.dumps(error_data),
            status_code=400,
            media_type="application/json",
        )
