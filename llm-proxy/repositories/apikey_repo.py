"""
API-Key数据访问层
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session

from models.api_key import ApiKey


class ApiKeyRepository:
    """API-Key数据访问层"""

    def get_by_id(self, key_id: int, db: Session) -> Optional[ApiKey]:
        """根据 ID 获取 API-Key"""
        return db.query(ApiKey).filter(ApiKey.id == key_id).first()

    def get_by_id_and_user(
        self, key_id: int, user_id: int, db: Session
    ) -> Optional[ApiKey]:
        """根据 ID 和用户 ID 获取 API-Key"""
        return (
            db.query(ApiKey)
            .filter(ApiKey.id == key_id, ApiKey.user_id == user_id)
            .first()
        )

    def get_by_api_key(self, api_key: str, db: Session) -> Optional[ApiKey]:
        """根据实际 API-Key 获取"""
        return db.query(ApiKey).filter(ApiKey.api_key == api_key).first()

    def count_by_user(self, user_id: int, db: Session) -> int:
        """统计用户的 API-Key 数量"""
        return db.query(ApiKey).filter(ApiKey.user_id == user_id).count()

    def list_by_user(self, user_id: int, db: Session) -> List[ApiKey]:
        """获取用户的所有 API-Key"""
        return db.query(ApiKey).filter(ApiKey.user_id == user_id).all()

    def create(
        self,
        user_id: int,
        key_name: str,
        api_key: str,
        key_prefix: str,
        db: Session,
    ) -> ApiKey:
        """创建 API-Key"""
        key = ApiKey(
            user_id=user_id,
            key_name=key_name,
            api_key=api_key,
            key_prefix=key_prefix,
        )
        db.add(key)
        db.commit()
        db.refresh(key)
        return key

    def update_name(
        self, key_id: int, new_name: str, db: Session
    ) -> bool:
        """更新 API-Key 名称"""
        key = self.get_by_id(key_id, db)
        if not key:
            return False

        key.key_name = new_name
        db.commit()
        return True

    def update_last_used(self, key_id: int, db: Session) -> bool:
        """更新最后使用时间"""
        key = self.get_by_id(key_id, db)
        if not key:
            return False

        key.last_used_at = datetime.utcnow()
        db.commit()
        return True

    def delete(self, key_id: int, db: Session) -> bool:
        """删除 API-Key"""
        key = self.get_by_id(key_id, db)
        if not key:
            return False

        db.delete(key)
        db.commit()
        return True
