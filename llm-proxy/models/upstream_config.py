"""
上游配置模型
"""

from datetime import datetime

from sqlalchemy import Column, BigInteger, String, DateTime

from app.database import Base


class UpstreamConfig(Base):
    """上游配置表"""
    __tablename__ = "upstream_config"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    config_key = Column(String(100), nullable=False, unique=True)
    config_value = Column(String(255), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
