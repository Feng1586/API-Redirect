"""
计费服务
"""

from typing import Optional, Tuple
from sqlalchemy.orm import Session

from models.user import User
from models.usage import UsageRecord
from models.model_config import ModelConfig
from repositories.usage_repo import UsageRepository
from repositories.model_config_repo import ModelConfigRepository
from app.config import settings
from log.logger import get_logger

logger = get_logger(__name__)


class BillingService:
    """计费服务"""

    def __init__(self):
        self.usage_repo = UsageRepository()
        self.model_config_repo = ModelConfigRepository()

    def calculate_cost(
        self, model_name: str, prompt_tokens: int, completion_tokens: int, db: Session
    ) -> float:
        """
        计算费用
        费用 = prompt_tokens / 1000 * price_per_1k_input
             + completion_tokens / 1000 * price_per_1k_output
        最低消费: 0.01元
        """
        prices = self.get_model_prices(model_name, db)
        if prices is None:
            return 0.0

        price_input, price_output = prices

        # 计算输入费用
        cost_input = (prompt_tokens / 1000) * price_input
        # 计算输出费用
        cost_output = (completion_tokens / 1000) * price_output

        cost = cost_input + cost_output

        # 最低消费
        if cost < settings.billing.min_charge and cost > 0:
            cost = settings.billing.min_charge

        return round(cost, 6)

    def record_usage(
        self,
        user_id: int,
        api_key_id: int,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        db: Session,
    ) -> Tuple[bool, float]:
        """
        记录用量并扣除费用
        返回: (success, cost)
        """
        cost = self.calculate_cost(model, prompt_tokens, completion_tokens, db)

        # 扣除余额
        # TODO: 调用 UserService.deduct_balance

        # 记录用量
        self.usage_repo.create(
            user_id=user_id,
            api_key_id=api_key_id,
            model_name=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost=cost,
            db=db,
        )

        return True, cost

    def get_model_prices(self, model_name: str, db: Session) -> Optional[Tuple[float, float]]:
        """
        获取模型单价 (输入价格, 输出价格)
        返回: (price_input, price_output) or None
        """
        config = self.model_config_repo.get_by_model_name(model_name, db)
        if not config or not config.is_enabled:
            return None

        return float(config.price_per_1k_input), float(config.price_per_1k_output)

    def check_balance(self, user_id: int, db: Session) -> Tuple[bool, float]:
        """
        检查余额是否充足
        返回: (is_sufficient, current_balance)
        """
        from repositories.user_repo import UserRepository

        user_repo = UserRepository()
        user = user_repo.get_by_id(user_id, db)

        if not user:
            return False, 0.0

        return float(user.balance) > 0, float(user.balance)
