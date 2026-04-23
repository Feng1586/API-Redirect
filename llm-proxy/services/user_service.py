"""
用户服务
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.user import User
from models.api_key import ApiKey
from models.order import Order
from repositories.user_repo import UserRepository
from repositories.apikey_repo import ApiKeyRepository
from repositories.order_repo import OrderRepository
from repositories.usage_repo import UsageRepository


class UserService:
    """用户服务"""

    def __init__(self):
        self.user_repo = UserRepository()
        self.apikey_repo = ApiKeyRepository()
        self.order_repo = OrderRepository()
        self.usage_repo = UsageRepository()

    def get_profile(self, user_id: int, db: Session) -> Dict[str, Any]:
        """
        获取用户信息
        返回:
        {
            "balance": 100.00,
            "monthly_spending": 50.00,
            "daily_spending_30d": [...],
            "daily_requests_30d": [...],
            "daily_tokens_30d": [...],
            "api_keys": [...]
        }
        """
        # 获取用户基本信息
        user = self.user_repo.get_by_id(user_id, db)
        if not user:
            return {}

        # 获取月度消费
        monthly_spending = self.usage_repo.get_monthly_spending(user_id, db)

        # 获取每日统计 (30天)
        daily_stats = self.usage_repo.get_daily_stats(user_id, 30, db)

        # 分离每日数据
        daily_spending_30d = [d["spending"] for d in daily_stats]
        daily_requests_30d = [d["requests"] for d in daily_stats]
        daily_tokens_30d = [d["tokens"] for d in daily_stats]

        # 获取 API-Key 列表
        api_keys = self.apikey_repo.list_by_user(user_id, db)
        api_keys_data = [
            {
                "id": key.id,
                "name": key.key_name,
                "key": key.key_prefix,
                "created_at": key.created_at.isoformat() if key.created_at else None,
                "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
            }
            for key in api_keys
        ]

        return {
            "balance": float(user.balance) if user.balance else 0.0,
            "monthly_spending": monthly_spending,
            "daily_spending_30d": daily_spending_30d,
            "daily_requests_30d": daily_requests_30d,
            "daily_tokens_30d": daily_tokens_30d,
            "api_keys": api_keys_data,
        }

    def get_bills(self, user_id: int, page: int, page_size: int, db: Session) -> Dict[str, Any]:
        """
        获取用户账单
        """
        # 获取订单列表
        orders = self.order_repo.list_by_user(user_id, page, page_size, db)
        total = self.order_repo.count_by_user(user_id, db)

        items = [
            {
                "order_no": order.order_no,
                "status": order.status,
                "amount": float(order.amount),
                "created_at": order.created_at.isoformat() if order.created_at else None,
            }
            for order in orders
        ]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    def get_daily_stats(self, user_id: int, days: int = 30, db: Session = None) -> Dict[str, Any]:
        """
        获取每日统计数据
        """
        # 如果没有传入 db，从 usage_repo 获取（这里只是为了兼容）
        daily_stats = self.usage_repo.get_daily_stats(user_id, days, db)

        return {
            "days": days,
            "data": daily_stats,
        }

    def deduct_balance(self, user_id: int, amount: float, db: Session) -> bool:
        """
        扣除余额 (原子操作)
        使用 SELECT FOR UPDATE 锁定用户记录
        """
        # 锁定用户记录并检查余额
        user = db.query(User).filter(User.id == user_id).with_for_update().first()
        if not user:
            return False

        current_balance = float(user.balance) if user.balance else 0.0
        if current_balance < amount:
            return False

        # 扣除余额
        user.balance = current_balance - amount
        db.commit()
        return True

    def add_balance(self, user_id: int, amount: float, db: Session) -> bool:
        """
        增加余额
        """
        user = db.query(User).filter(User.id == user_id).with_for_update().first()
        if not user:
            return False

        current_balance = float(user.balance) if user.balance else 0.0
        user.balance = current_balance + amount
        db.commit()
        return True
