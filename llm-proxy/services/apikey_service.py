"""
API-Key服务
"""

from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from sqlalchemy.orm import Session

from models.user import User
from models.api_key import ApiKey
from repositories.apikey_repo import ApiKeyRepository
from utils.token import generate_api_key
from core.security import hash_api_key
from core.limiter import rate_limiter
from app.config import settings
from log.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ValidatedApiKey:
    """验证通过的API-Key结果"""
    user: User
    api_key_id: int


class ApiKeyService:
    """API-Key服务"""

    MAX_API_KEYS_PER_USER = 10

    def __init__(self):
        self.apikey_repo = ApiKeyRepository()

    def create_api_key(
        self, user_id: int, key_name: str, db: Session
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        创建API-Key
        检查: 用户API-Key数量 < 10
        返回: (success, error_message, {"id", "key_name", "api_key", "key_prefix", "created_at"})
              注意: api_key 明文仅在此处返回，数据库中只存储哈希值
        """
        # 检查用户 API-Key 数量
        key_count = self.apikey_repo.count_by_user(user_id, db)
        if key_count >= self.MAX_API_KEYS_PER_USER:
            return False, f"API-Key数量已达上限({self.MAX_API_KEYS_PER_USER}个)", None

        # 生成 API-Key
        api_key = generate_api_key()
        key_prefix = api_key[:8] + "****" + api_key[-4:]

        # 哈希后存储（明文仅在创建时返回给用户，不入库）
        api_key_hash = hash_api_key(api_key)

        # 存储
        new_key = self.apikey_repo.create(
            user_id=user_id,
            key_name=key_name,
            api_key_hash=api_key_hash,
            key_prefix=key_prefix,
            db=db,
        )

        return True, "创建成功", {
            "id": new_key.id,
            "key_name": new_key.key_name,
            "api_key": api_key,
            "key_prefix": new_key.key_prefix,
            "created_at": new_key.created_at.isoformat() if new_key.created_at else None,
        }

    def list_api_keys(self, user_id: int, db: Session) -> List[Dict[str, Any]]:
        """
        获取API-Key列表 (仅显示前8后4位)
        """
        keys = self.apikey_repo.list_by_user(user_id, db)
        return [
            {
                "id": key.id,
                "name": key.key_name,
                "key": key.key_prefix,
                "created_at": key.created_at.isoformat() if key.created_at else None,
                "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
            }
            for key in keys
        ]

    def delete_api_key(self, user_id: int, key_id: int, db: Session) -> bool:
        """
        删除API-Key
        """
        key = self.apikey_repo.get_by_id_and_user(key_id, user_id, db)
        if not key:
            return False

        self.apikey_repo.delete(key_id, db)
        return True

    def update_api_key_name(
        self, user_id: int, key_id: int, new_name: str, db: Session
    ) -> bool:
        """
        修改API-Key备注
        """
        key = self.apikey_repo.get_by_id_and_user(key_id, user_id, db)
        if not key:
            return False

        self.apikey_repo.update_name(key_id, new_name, db)
        return True

    def validate_api_key(self, api_key: str, db: Session) -> Optional[ValidatedApiKey]:
        """
        验证API-Key
        将输入的明文 Key 哈希后与数据库比对
        返回: ValidatedApiKey(user, api_key_id) or None
        """
        api_key_hash = hash_api_key(api_key)
        key = self.apikey_repo.get_by_api_key_hash(api_key_hash, db)
        if not key:
            return None

        # 更新最后使用时间
        self.update_last_used(key.id, db)

        return ValidatedApiKey(user=key.user, api_key_id=key.id)

    def update_last_used(self, api_key_id: int, db: Session) -> bool:
        """
        更新API-Key最后使用时间
        """
        self.apikey_repo.update_last_used(api_key_id, db)
        return True
