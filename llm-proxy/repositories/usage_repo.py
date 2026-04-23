"""
用量数据访问层
"""

from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.usage import UsageRecord


class UsageRepository:
    """用量数据访问层"""

    def get_by_id(self, record_id: int, db: Session) -> UsageRecord:
        """根据 ID 获取用量记录"""
        return db.query(UsageRecord).filter(UsageRecord.id == record_id).first()

    def list_by_user(
        self, user_id: int, days: int, db: Session
    ) -> List[UsageRecord]:
        """获取用户的用量记录"""
        from datetime import timedelta

        start_date = datetime.utcnow() - timedelta(days=days)
        return (
            db.query(UsageRecord)
            .filter(
                UsageRecord.user_id == user_id,
                UsageRecord.created_at >= start_date,
            )
            .all()
        )

    def get_monthly_spending(self, user_id: int, db: Session) -> float:
        """获取本月消费"""
        now = datetime.utcnow()
        start_of_month = datetime(now.year, now.month, 1)

        result = (
            db.query(func.coalesce(func.sum(UsageRecord.cost), 0))
            .filter(
                UsageRecord.user_id == user_id,
                UsageRecord.created_at >= start_of_month,
            )
            .scalar()
        )
        return float(result)

    def get_daily_stats(
        self, user_id: int, days: int, db: Session
    ) -> List[Dict[str, Any]]:
        """获取每日统计数据"""
        from datetime import timedelta

        start_date = datetime.utcnow() - timedelta(days=days)

        # 按日期分组统计
        results = (
            db.query(
                func.date(UsageRecord.created_at).label("date"),
                func.count(UsageRecord.id).label("requests"),
                func.coalesce(func.sum(UsageRecord.total_tokens), 0).label("tokens"),
                func.coalesce(func.sum(UsageRecord.cost), 0).label("spending"),
            )
            .filter(
                UsageRecord.user_id == user_id,
                UsageRecord.created_at >= start_date,
            )
            .group_by(func.date(UsageRecord.created_at))
            .order_by(func.date(UsageRecord.created_at))
            .all()
        )

        return [
            {
                "date": str(r.date),
                "requests": r.requests,
                "tokens": int(r.tokens),
                "spending": float(r.spending),
            }
            for r in results
        ]

    def create(
        self,
        user_id: int,
        api_key_id: int,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost: float,
        db: Session,
    ) -> UsageRecord:
        """创建用量记录"""
        record = UsageRecord(
            user_id=user_id,
            api_key_id=api_key_id,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
