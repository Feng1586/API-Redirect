"""
模型配置模型
"""

from datetime import datetime

from sqlalchemy import Column, BigInteger, String, DECIMAL, DateTime

from app.database import Base


class ModelConfig(Base):
    """模型配置表"""
    __tablename__ = "model_configs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_name = Column(String(100), nullable=False, unique=True)  # 模型名称
    price_per_1k_input = Column(DECIMAL(10, 6), nullable=False)  # 每1000 Input Tokens价格
    price_per_1k_output = Column(DECIMAL(10, 6), nullable=False)  # 每1000 Output Tokens价格
    is_enabled = Column(BigInteger, default=1)  # 是否启用
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
