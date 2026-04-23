"""
模型配置数据访问层
"""

from typing import Optional

from sqlalchemy.orm import Session

from models.model_config import ModelConfig


class ModelConfigRepository:
    """模型配置数据访问层"""

    def get_by_model_name(self, model_name: str, db: Session) -> Optional[ModelConfig]:
        """根据模型名称获取配置"""
        return (
            db.query(ModelConfig)
            .filter(ModelConfig.model_name == model_name)
            .first()
        )

    def get_enabled_models(self, db: Session) -> list[ModelConfig]:
        """获取所有已启用的模型"""
        return db.query(ModelConfig).filter(ModelConfig.is_enabled == 1).all()
