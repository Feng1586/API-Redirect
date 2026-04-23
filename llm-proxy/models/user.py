"""
用户模型
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, BigInteger, String, Enum, DECIMAL, DateTime, Index
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    balance = Column(DECIMAL(10, 4), default=0.0000)
    role = Column(Enum("user", "admin"), default="user")
    is_active = Column(BigInteger, default=1)  # 软删除标记
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    # 关系
    api_keys = relationship("ApiKey", back_populates="user")
    orders = relationship("Order", back_populates="user")
    usage_records = relationship("UsageRecord", back_populates="user")

    __table_args__ = (
        Index("idx_email", "email"),
        Index("idx_username", "username"),
    )
