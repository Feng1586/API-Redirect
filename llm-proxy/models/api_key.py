"""
API-Key模型
"""

from datetime import datetime

from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.database import Base


class ApiKey(Base):
    """API-Key表"""
    __tablename__ = "api_keys"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    key_name = Column(String(100), nullable=False)  # API-Key名称
    api_key_hash = Column(String(64), nullable=False, unique=True, index=True)  # API-Key哈希值(SHA-256)
    key_prefix = Column(String(20), nullable=False)  # 仅存储前8后4位（用于展示）
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)

    # 关系
    user = relationship("User", back_populates="api_keys")
    usage_records = relationship("UsageRecord", back_populates="api_key")

    __table_args__ = (
        Index("idx_user_id", "user_id"),
        Index("idx_api_key_hash", "api_key_hash"),
    )
