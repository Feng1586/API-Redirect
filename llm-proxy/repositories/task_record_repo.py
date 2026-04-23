"""
任务记录数据访问层
"""

from typing import Optional
from sqlalchemy.orm import Session

from models.task_record import TaskRecord


class TaskRecordRepository:
    """任务记录仓库"""

    def __init__(self):
        pass

    def create(
        self,
        task_id: str,
        api_key_id: int,
        db: Session,
    ) -> TaskRecord:
        """创建任务记录"""
        record = TaskRecord(
            task_id=task_id,
            api_key_id=api_key_id,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def get_by_task_id(self, task_id: str, db: Session) -> Optional[TaskRecord]:
        """按任务ID查询"""
        return db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()

    def get_by_task_id_and_apikey(
        self, task_id: str, api_key_id: int, db: Session
    ) -> Optional[TaskRecord]:
        """按任务ID和API-Key ID查询（用于权限校验）"""
        return db.query(TaskRecord).filter(
            TaskRecord.task_id == task_id,
            TaskRecord.api_key_id == api_key_id,
        ).first()
