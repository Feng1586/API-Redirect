"""
图片模型配置数据访问层
"""

from typing import Optional

from sqlalchemy.orm import Session, joinedload

from models.image_model_config import ImageModelConfig, ImageResolutionPrice


class ImageModelRepository:
    """图片模型配置数据访问层"""

    def get_by_model_name(
        self, model_name: str, db: Session
    ) -> Optional[ImageModelConfig]:
        """根据模型名称获取配置（含分辨率价格）"""
        return (
            db.query(ImageModelConfig)
            .options(joinedload(ImageModelConfig.resolutions))
            .filter(ImageModelConfig.model_name == model_name)
            .first()
        )

    def get_enabled_models(self, db: Session) -> list[ImageModelConfig]:
        """获取所有已启用的图片模型（含分辨率价格）"""
        return (
            db.query(ImageModelConfig)
            .options(joinedload(ImageModelConfig.resolutions))
            .filter(ImageModelConfig.is_enabled == 1)
            .all()
        )

    def get_resolution_price(
        self, model_id: int, resolution: str, db: Session
    ) -> Optional[ImageResolutionPrice]:
        """获取指定模型和分辨率的价格"""
        return (
            db.query(ImageResolutionPrice)
            .filter(
                ImageResolutionPrice.model_id == model_id,
                ImageResolutionPrice.resolution == resolution,
            )
            .first()
        )

    def get_default_resolution(
        self, model_id: int, db: Session
    ) -> Optional[ImageResolutionPrice]:
        """获取指定模型的默认分辨率价格"""
        return (
            db.query(ImageResolutionPrice)
            .filter(
                ImageResolutionPrice.model_id == model_id,
                ImageResolutionPrice.is_default == 1,
            )
            .first()
        )
