"""
订单模型
"""

from datetime import datetime

from sqlalchemy import Column, BigInteger, String, DECIMAL, Enum, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.database import Base


class Order(Base):
    """订单表"""
    __tablename__ = "orders"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_no = Column(String(50), nullable=False, unique=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(DECIMAL(10, 4), nullable=False)  # 充值金额
    status = Column(Enum("pending", "paid", "failed", "refunded"), default="pending")
    payment_method = Column(String(50), default="paypal")  # 支付方式
    external_no = Column(String(255), nullable=True)  # 第三方订单号
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)

    # 关系
    user = relationship("User", back_populates="orders")

    __table_args__ = (
        Index("idx_user_id", "user_id"),
        Index("idx_order_no", "order_no"),
    )
