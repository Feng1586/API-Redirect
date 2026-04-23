"""
用户数据访问层
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from models.user import User


class UserRepository:
    """用户数据访问层"""

    def get_by_id(self, user_id: int, db: Session) -> Optional[User]:
        """根据 ID 获取用户"""
        return db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str, db: Session) -> Optional[User]:
        """根据邮箱获取用户"""
        return db.query(User).filter(User.email == email).first()

    def get_by_username(self, username: str, db: Session) -> Optional[User]:
        """根据用户名获取用户"""
        return db.query(User).filter(User.username == username).first()

    def create(
        self, email: str, username: str, password_hash: str, db: Session
    ) -> User:
        """创建用户"""
        user = User(
            email=email,
            username=username,
            password_hash=password_hash,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def update_balance(
        self, user_id: int, amount: float, db: Session
    ) -> bool:
        """更新余额"""
        user = self.get_by_id(user_id, db)
        if not user:
            return False

        user.balance = amount
        db.commit()
        return True

    def soft_delete(self, user_id: int, db: Session) -> bool:
        """软删除用户"""
        user = self.get_by_id(user_id, db)
        if not user:
            return False

        user.is_active = 0
        user.deleted_at = datetime.utcnow()
        db.commit()
        return True
