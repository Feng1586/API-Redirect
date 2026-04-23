"""
充值服务（预留）
"""

from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.orm import Session

from models.order import Order
from repositories.order_repo import OrderRepository
from utils.token import generate_order_no


class RechargeService:
    """充值服务"""

    def __init__(self):
        self.order_repo = OrderRepository()

    def create_order(
        self, user_id: int, amount: float, db: Session
    ) -> Tuple[bool, str, Optional[Order]]:
        """
        创建充值订单
        """
        if amount <= 0:
            return False, "充值金额必须大于0", None

        order_no = generate_order_no()
        order = self.order_repo.create(
            user_id=user_id,
            order_no=order_no,
            amount=amount,
            db=db,
        )

        return True, "订单创建成功", order

    def get_order(self, order_no: str, db: Session) -> Optional[Order]:
        """
        查询订单
        """
        return self.order_repo.get_by_order_no(order_no, db)

    def handle_paypal_callback(
        self, callback_data: Dict[str, Any], db: Session
    ) -> Tuple[bool, str]:
        """
        处理PayPal回调
        1. 验证签名
        2. 更新订单状态
        3. 增加用户余额
        """
        # TODO: 验证签名
        # TODO: 更新订单状态
        # TODO: 增加用户余额
        pass

    def get_user_orders(
        self, user_id: int, page: int, page_size: int, db: Session
    ) -> List[Order]:
        """
        获取用户订单列表
        """
        return self.order_repo.list_by_user(user_id, page, page_size, db)
