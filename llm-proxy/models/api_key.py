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
    api_key = Column(String(50), nullable=False, unique=True, index=True)  # 实际API-Key
    key_prefix = Column(String(20), nullable=False)  # 仅存储前8后4位
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)

    # 关系
    user = relationship("User", back_populates="api_keys")
    usage_records = relationship("UsageRecord", back_populates="api_key")

    __table_args__ = (
        Index("idx_user_id", "user_id"),
        Index("idx_api_key", "api_key"),
    )
