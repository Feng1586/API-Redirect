"""
视频模型配置模型

用于存储视频生成模型的计费配置：
- 主表 video_model_configs: 模型名称、默认生成时长等通用信息
- 子表 video_resolution_prices: 各分辨率对应的每秒单价
"""

from datetime import datetime

from sqlalchemy import Column, BigInteger, String, DECIMAL, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class VideoModelConfig(Base):
    """视频模型配置表"""
    __tablename__ = "video_model_configs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_name = Column(String(100), nullable=False, unique=True)  # 模型名称
    is_enabled = Column(BigInteger, default=1)  # 是否启用
    default_duration = Column(BigInteger, default=5, nullable=False)  # 默认生成秒数
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联的分辨率价格配置（一对多）
    resolutions = relationship(
        "VideoResolutionPrice",
        back_populates="model",
        cascade="all, delete-orphan",
    )


class VideoResolutionPrice(Base):
    """视频模型分辨率价格表"""
    __tablename__ = "video_resolution_prices"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_id = Column(BigInteger, ForeignKey("video_model_configs.id"), nullable=False)
    resolution = Column(String(20), nullable=False)  # 如 "720p", "1080p", "4k"
    price_per_second = Column(DECIMAL(10, 6), nullable=False)  # 每秒单价（元）
    is_default = Column(BigInteger, default=0)  # 是否为默认分辨率, 0=否, 1=是

    model = relationship("VideoModelConfig", back_populates="resolutions")

    __table_args__ = (
        UniqueConstraint("model_id", "resolution", name="uq_model_resolution"),
    )
