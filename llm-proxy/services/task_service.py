"""
任务查询服务
"""

import json
from typing import Dict, Any, Optional
from fastapi import Response
from sqlalchemy.orm import Session

from app.config import settings
from log.logger import get_logger

logger = get_logger(__name__)


class TaskService:
    """任务查询服务（用于查询图片/视频生成任务进度）"""

    def __init__(self):
        pass

    async def query_task(
        self,
        task_id: str,
        user_id: int,
        api_key_id: int,
        db: Session,
    ) -> Response:
        """
        查询任务进度

        TODO: 实现任务查询请求转发逻辑
        流程：
        1. 校验 task_id 是否有效
        2. 查询 task_records 表，确认该 task_id 属于当前 api_key_id（防止越权查询）
        3. 转发请求到上游 GET https://api.apimart.ai/v1/tasks/{task_id}
        4. 接收上游响应（任务状态、进度、完成后带有URL）
        5. 透传响应给客户端
        """
        raise NotImplementedError("待实现 - 详见 TODO 注释")
