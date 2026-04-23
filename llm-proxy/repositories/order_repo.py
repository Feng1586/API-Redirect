"""
订单数据访问层
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session

from models.order import Order


class OrderRepository:
    """订单数据访问层"""

    def get_by_id(self, order_id: int, db: Session) -> Optional[Order]:
        """根据 ID 获取订单"""
        return db.query(Order).filter(Order.id == order_id).first()

    def get_by_order_no(self, order_no: str, db: Session) -> Optional[Order]:
        """根据订单号获取订单"""
        return db.query(Order).filter(Order.order_no == order_no).first()

    def list_by_user(
        self, user_id: int, page: int, page_size: int, db: Session
    ) -> List[Order]:
        """获取用户的订单列表"""
        offset = (page - 1) * page_size
        return (
            db.query(Order)
            .filter(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

    def count_by_user(self, user_id: int, db: Session) -> int:
        """统计用户的订单数量"""
        return db.query(Order).filter(Order.user_id == user_id).count()

    def create(
        self, user_id: int, order_no: str, amount: float, db: Session
    ) -> Order:
        """创建订单"""
        order = Order(
            user_id=user_id,
            order_no=order_no,
            amount=amount,
            status="pending",
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    def update_status(
        self, order_no: str, status: str, db: Session
    ) -> bool:
        """更新订单状态"""
        order = self.get_by_order_no(order_no, db)
        if not order:
            return False

        order.status = status
        if status == "paid":
            order.paid_at = datetime.utcnow()
        db.commit()
        return True

    def update_external_no(
        self, order_no: str, external_no: str, db: Session
    ) -> bool:
        """更新第三方订单号"""
        order = self.get_by_order_no(order_no, db)
        if not order:
            return False

        order.external_no = external_no
        db.commit()
        return True
