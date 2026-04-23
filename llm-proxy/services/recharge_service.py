"""
充值服务
集成 PayPal 支付：创建订单 → 用户支付 → 捕获资金 → 更新余额
"""

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from models.order import Order
from models.user import User
from repositories.order_repo import OrderRepository
from repositories.user_repo import UserRepository
from services.paypal_service import PayPalService
from utils.token import generate_order_no
from log.logger import get_logger

logger = get_logger(__name__)


class RechargeService:
    """充值服务"""

    def __init__(self):
        self.order_repo = OrderRepository()
        self.user_repo = UserRepository()
        self.paypal_service = PayPalService()

    async def create_order(
        self,
        user_id: int,
        amount: float,
        currency: str = "USD",
        return_url: str = "",
        cancel_url: str = "",
        db: Session = None,
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        创建充值订单（同步：生成本地订单 + 异步：调用 PayPal 创建订单）

        流程:
        1. 生成本地订单号
        2. 调用 PayPal API 创建订单（intent=CAPTURE）
        3. 保存订单信息到数据库
        4. 返回 PayPal approve URL 给前端跳转
        """
        if amount <= 0:
            return False, "充值金额必须大于0", None

        # 1. 生成本地订单号
        order_no = generate_order_no()

        # 2. 调用 PayPal 创建订单
        amount_str = f"{amount:.2f}"
        success, message, paypal_data = await self.paypal_service.create_order(
            amount=amount_str,
            currency=currency,
            custom_id=order_no,
            return_url=return_url,
            cancel_url=cancel_url,
            description=f"AI API 账户充值 - {amount} {currency}",
        )

        if not success:
            return False, message, None

        # 3. 保存订单到数据库
        paypal_order_id = paypal_data.get("paypal_order_id", "")
        order = self.order_repo.create(
            user_id=user_id,
            order_no=order_no,
            amount=amount,
            db=db,
        )
        # 保存 PayPal 订单号
        if paypal_order_id:
            self.order_repo.update_external_no(order_no, paypal_order_id, db)

        # 4. 返回结果
        result = {
            "order_no": order_no,
            "paypal_order_id": paypal_order_id,
            "amount": amount,
            "currency": currency,
            "approve_url": paypal_data.get("approve_url", ""),
            "status": paypal_data.get("status", ""),
        }
        return True, "订单创建成功", result

    async def capture_order(
        self, order_no: str, db: Session
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        捕获订单（用户支付后调用此接口完成扣款）

        流程:
        1. 查询本地订单
        2. 调用 PayPal API 捕获资金
        3. 更新本地订单状态为 paid
        4. 为用户增加余额
        """
        # 1. 查询本地订单
        order = self.order_repo.get_by_order_no(order_no, db)
        if not order:
            return False, "订单不存在", None

        if order.status == "paid":
            return False, "该订单已支付", None

        if order.status != "pending":
            return False, f"订单状态异常: {order.status}", None

        paypal_order_id = order.external_no
        if not paypal_order_id:
            return False, "订单缺少 PayPal 订单号", None

        # 2. 调用 PayPal API 捕获资金
        success, message, capture_data = await self.paypal_service.capture_order(paypal_order_id)
        if not success:
            return False, message, None

        # 3. 检查捕获状态
        capture_status = capture_data.get("status", "")
        if capture_status != "COMPLETED":
            return False, f"PayPal 捕获状态异常: {capture_status}", None

        # 提取捕获信息
        captures = capture_data.get("captures", [])
        first_capture = captures[0] if captures else {}
        capture_id = first_capture.get("capture_id", "")
        # 获取 PayPal 手续费
        breakdown = first_capture.get("seller_receivable_breakdown", {})
        paypal_fee = float(breakdown.get("paypal_fee", {}).get("value", 0))
        net_amount = float(breakdown.get("net_amount", {}).get("value", 0))
        gross_amount = float(first_capture.get("amount", 0))
        payer_info = capture_data.get("payer", {})

        # 4. 更新订单状态为 paid
        self.order_repo.update_status(order_no, "paid", db)

        # 5. 为用户增加余额（使用订单金额，非扣除手续费后的净额）
        user = self.user_repo.get_by_id(order.user_id, db)
        if user:
            new_balance = float(user.balance) + gross_amount
            self.user_repo.update_balance(order.user_id, new_balance, db)

        db.commit()

        logger.info(
            f"充值成功: order_no={order_no}, amount={gross_amount}, "
            f"fee={paypal_fee}, net={net_amount}, user_id={order.user_id}"
        )

        result = {
            "order_no": order_no,
            "paypal_order_id": paypal_order_id,
            "capture_id": capture_id,
            "status": "paid",
            "amount": gross_amount,
            "currency": first_capture.get("currency", "USD"),
            "paypal_fee": paypal_fee,
            "net_amount": net_amount,
            "payer_email": payer_info.get("email_address", ""),
        }
        return True, "充值成功", result

    async def handle_paypal_webhook(
        self,
        event_body: Dict[str, Any],
        webhook_headers: Dict[str, str],
        webhook_id: str,
        db: Session,
    ) -> Tuple[bool, str]:
        """
        处理 PayPal Webhook 通知

        流程:
        1. 验证 Webhook 签名
        2. 根据事件类型处理
        3. 如果是 PAYMENT.CAPTURE.COMPLETED，更新订单并增加余额
        """
        # 1. 验证签名
        paypal_service = PayPalService()
        verified, msg = await paypal_service.verify_webhook_signature(
            webhook_id=webhook_id,
            event_body=event_body,
            headers=webhook_headers,
        )
        if not verified:
            logger.warning(f"Webhook 签名验证失败: {msg}")
            return False, msg

        # 2. 处理事件
        event_type = event_body.get("event_type", "")
        resource = event_body.get("resource", {})

        if event_type == "CHECKOUT.ORDER.APPROVED":
            # 订单已批准，等待捕获（可做日志记录）
            logger.info(f"订单已批准: {resource.get('id', '')}")
            return True, "订单已批准"

        elif event_type == "PAYMENT.CAPTURE.COMPLETED":
            # 支付捕获完成
            capture_id = resource.get("id", "")
            custom_id = resource.get("custom_id", "")
            status = resource.get("status", "")

            logger.info(f"捕获完成: capture_id={capture_id}, custom_id={custom_id}")

            if status == "COMPLETED" and custom_id:
                # 查询订单
                order = self.order_repo.get_by_order_no(custom_id, db)
                if not order:
                    return False, f"订单不存在: {custom_id}"

                if order.status == "paid":
                    return True, "订单已处理"

                # 更新订单状态
                self.order_repo.update_status(custom_id, "paid", db)

                # 增加余额
                amount = float(resource.get("amount", {}).get("value", 0))
                user = self.user_repo.get_by_id(order.user_id, db)
                if user:
                    new_balance = float(user.balance) + amount
                    self.user_repo.update_balance(order.user_id, new_balance, db)

                db.commit()
                logger.info(f"Webhook 充值成功: order_no={custom_id}, amount={amount}")
                return True, "处理成功"

            return True, "无需处理"

        elif event_type == "PAYMENT.CAPTURE.DENIED":
            capture_id = resource.get("id", "")
            custom_id = resource.get("custom_id", "")
            if custom_id:
                self.order_repo.update_status(custom_id, "failed", db)
                db.commit()
            logger.warning(f"捕获被拒绝: capture_id={capture_id}, custom_id={custom_id}")
            return True, "已记录拒绝状态"

        else:
            logger.info(f"未处理的事件类型: {event_type}")
            return True, "事件类型无需处理"

    def get_order(self, order_no: str, db: Session) -> Optional[Order]:
        """查询订单"""
        return self.order_repo.get_by_order_no(order_no, db)

    def get_user_orders(
        self, user_id: int, page: int, page_size: int, db: Session
    ) -> List[Order]:
        """获取用户订单列表"""
        return self.order_repo.list_by_user(user_id, page, page_size, db)
