"""
角色任务查询接口（Sora2 查询角色）
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user_by_apikey, AuthenticatedUser
from services.character_service import CharacterService
from log.logger import get_logger
from utils.response import error_response

router = APIRouter(prefix="/characters_tasks", tags=["角色任务"])
character_service = CharacterService()
logger = get_logger(__name__)


@router.get("/{task_id}")
async def query_character_task(
    task_id: str,
    auth: AuthenticatedUser = Depends(get_current_user_by_apikey),
    db: Session = Depends(get_db),
):
    """
    查询角色任务进度

    将请求转发至上游: GET https://api.apimart.ai/v1/characters_tasks/{task_id}
    需要校验该 task_id 属于当前 API-Key
    """
    try:
        logger.info(f"角色任务查询请求 - 用户: {auth.user.id}, API Key ID: {auth.api_key_id}, task_id: {task_id}")
        return await character_service.query_character_task(
            task_id=task_id,
            api_key_id=auth.api_key_id,
            db=db,
        )
    except Exception as e:
        logger.error(f"角色任务查询请求处理错误: {str(e)}")
        return error_response(40003, f"请求处理错误: {str(e)}")
