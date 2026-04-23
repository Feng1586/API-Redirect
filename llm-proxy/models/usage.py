"""
用量记录模型
"""

from datetime import datetime

from sqlalchemy import Column, BigInteger, String, DECIMAL, INT, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.database import Base


class UsageRecord(Base):
    """用量记录表"""
    __tablename__ = "usage_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    api_key_id = Column(BigInteger, ForeignKey("api_keys.id"), nullable=False, index=True)
    model_name = Column(String(100), nullable=False)
    prompt_tokens = Column(INT, nullable=False, default=0)
    completion_tokens = Column(INT, nullable=False, default=0)
    total_tokens = Column(INT, nullable=False, default=0)
    cost = Column(DECIMAL(10, 6), nullable=False)  # 本次消费金额
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    user = relationship("User", back_populates="usage_records")
    api_key = relationship("ApiKey", back_populates="usage_records")

    __table_args__ = (
        Index("idx_user_date", "user_id", "created_at"),
        Index("idx_api_key", "api_key_id"),
    )
