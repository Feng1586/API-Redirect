"""
任务记录模型
"""

from sqlalchemy import Column, BigInteger, String, ForeignKey, Index, UniqueConstraint

from app.database import Base


class TaskRecord(Base):
    """任务记录表 - 记录图片/视频生成任务与API-Key的关联"""
    __tablename__ = "task_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(String(100), nullable=False)  # 上游返回的任务ID
    api_key_id = Column(BigInteger, ForeignKey("api_keys.id"), nullable=False)  # 创建该任务的API-Key

    __table_args__ = (
        UniqueConstraint("task_id", name="uq_task_id"),
        Index("idx_api_key_id", "api_key_id"),
    )
