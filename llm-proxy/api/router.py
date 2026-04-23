"""
路由聚合
"""

from fastapi import APIRouter

from api.v1 import auth, user, apikey, chat, claude, gemini, responses, recharge
from api.v1 import images, videos, tasks, audio, uploads, characters

api_router = APIRouter(prefix="/v1")

api_router.include_router(auth.router)
api_router.include_router(user.router)
api_router.include_router(apikey.router)
api_router.include_router(chat.router)
api_router.include_router(claude.router)
api_router.include_router(gemini.router)
api_router.include_router(responses.router)
api_router.include_router(recharge.router)
api_router.include_router(images.router)
api_router.include_router(videos.router)
api_router.include_router(tasks.router)
api_router.include_router(audio.router)
api_router.include_router(uploads.router)
api_router.include_router(characters.router)
