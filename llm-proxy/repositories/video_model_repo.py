"""
视频模型配置数据访问层
"""

from typing import Optional

from sqlalchemy.orm import Session, joinedload

from models.video_model_config import VideoModelConfig, VideoResolutionPrice


class VideoModelRepository:
    """视频模型配置数据访问层"""

    def get_by_model_name(
        self, model_name: str, db: Session
    ) -> Optional[VideoModelConfig]:
        """根据模型名称获取配置（含分辨率价格）"""
        return (
            db.query(VideoModelConfig)
            .options(joinedload(VideoModelConfig.resolutions))
            .filter(VideoModelConfig.model_name == model_name)
            .first()
        )

    def get_enabled_models(self, db: Session) -> list[VideoModelConfig]:
        """获取所有已启用的视频模型（含分辨率价格）"""
        return (
            db.query(VideoModelConfig)
            .options(joinedload(VideoModelConfig.resolutions))
            .filter(VideoModelConfig.is_enabled == 1)
            .all()
        )

    def get_resolution_price(
        self, model_id: int, resolution: str, db: Session
    ) -> Optional[VideoResolutionPrice]:
        """获取指定模型和分辨率的价格"""
        return (
            db.query(VideoResolutionPrice)
            .filter(
                VideoResolutionPrice.model_id == model_id,
                VideoResolutionPrice.resolution == resolution,
            )
            .first()
        )

    def get_default_resolution(
        self, model_id: int, db: Session
    ) -> Optional[VideoResolutionPrice]:
        """获取指定模型的默认分辨率价格"""
        return (
            db.query(VideoResolutionPrice)
            .filter(
                VideoResolutionPrice.model_id == model_id,
                VideoResolutionPrice.is_default == 1,
            )
            .first()
        )
