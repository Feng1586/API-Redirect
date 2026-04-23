"""
上游配置数据访问层
"""

from typing import Optional

from sqlalchemy.orm import Session

from models.upstream_config import UpstreamConfig


class UpstreamConfigRepository:
    """上游配置数据访问层"""

    def get_by_key(self, config_key: str, db: Session) -> Optional[UpstreamConfig]:
        """根据配置键获取配置"""
        return (
            db.query(UpstreamConfig)
            .filter(UpstreamConfig.config_key == config_key)
            .first()
        )

    def update_value(
        self, config_key: str, config_value: str, db: Session
    ) -> bool:
        """更新配置值"""
        config = self.get_by_key(config_key, db)
        if not config:
            config = UpstreamConfig(config_key=config_key, config_value=config_value)
            db.add(config)
        else:
            config.config_value = config_value

        db.commit()
        return True
