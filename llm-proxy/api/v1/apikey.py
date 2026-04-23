"""
API-Key管理接口
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from models.user import User
from schemas.apikey import CreateApiKeyRequest, UpdateApiKeyRequest, ApiKeyResponse
from services.apikey_service import ApiKeyService
from utils.response import success_response, error_response

router = APIRouter(prefix="/apikey", tags=["API-Key"])
apikey_service = ApiKeyService()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: CreateApiKeyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建API-Key"""
    success, message, api_key = apikey_service.create_api_key(
        user_id=current_user.id,
        key_name=request.name,
        db=db,
    )
    if not success:
        return error_response(400, message, code=20001)

    return success_response(201, "创建成功", {
        "id": api_key.id,
        "name": api_key.key_name,
        "api_key": api_key.api_key,
        "created_at": api_key.created_at.isoformat(),
    })


@router.get("")
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取API-Key列表"""
    keys = apikey_service.list_api_keys(current_user.id, db)
    return success_response(200, "success", keys)


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除API-Key"""
    success = apikey_service.delete_api_key(current_user.id, key_id, db)
    if not success:
        return error_response(404, "API-Key不存在", code=40401)
    return success_response(200, "删除成功")


@router.patch("/{key_id}")
async def update_api_key(
    key_id: int,
    request: UpdateApiKeyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改API-Key备注"""
    success = apikey_service.update_api_key_name(
        current_user.id, key_id, request.name, db
    )
    if not success:
        return error_response(404, "API-Key不存在", code=40401)
    return success_response(200, "修改成功")
