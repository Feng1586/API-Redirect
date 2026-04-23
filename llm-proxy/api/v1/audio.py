"""
音频处理接口（语音转文字、文字转语音）
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user_by_apikey, AuthenticatedUser
from services.audio_service import AudioService
from log.logger import get_logger
from utils.response import error_response

router = APIRouter(prefix="/audio", tags=["音频处理"])
audio_service = AudioService()
logger = get_logger(__name__)


@router.post("/transcriptions")
async def create_transcription(
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_user_by_apikey),
    db: Session = Depends(get_db),
):
    """
    语音转文字

    将请求转发至上游: POST https://api.apimart.ai/v1/audio/transcriptions

    TODO: 实现语音转文字请求的完整转发逻辑
    """
    try:
        request_body = await request.body()
        logger.info(f"语音转文字请求 - 用户: {auth.user.id}")
        return await audio_service.create_transcription(
            request_body=request_body,
            user_id=auth.user.id,
            api_key_id=auth.api_key_id,
            db=db,
        )
    except NotImplementedError:
        return error_response(50001, "语音转文字接口尚未实现")
    except Exception as e:
        logger.error(f"语音转文字请求处理错误: {str(e)}")
        return error_response(40003, f"请求处理错误: {str(e)}")


@router.post("/speech")
async def create_speech(
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_user_by_apikey),
    db: Session = Depends(get_db),
):
    """
    文字转语音

    将请求转发至上游: POST https://api.apimart.ai/v1/audio/speech

    TODO: 实现文字转语音请求的完整转发逻辑
    """
    try:
        request_body = await request.body()
        logger.info(f"文字转语音请求 - 用户: {auth.user.id}")
        return await audio_service.create_speech(
            request_body=request_body,
            user_id=auth.user.id,
            api_key_id=auth.api_key_id,
            db=db,
        )
    except NotImplementedError:
        return error_response(50001, "文字转语音接口尚未实现")
    except Exception as e:
        logger.error(f"文字转语音请求处理错误: {str(e)}")
        return error_response(40003, f"请求处理错误: {str(e)}")
