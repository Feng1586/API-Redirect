"""
计费服务
"""

from typing import Optional, Tuple
from sqlalchemy.orm import Session

from models.user import User
from models.usage import UsageRecord
from models.model_config import ModelConfig
from models.video_model_config import VideoModelConfig, VideoResolutionPrice
from models.image_model_config import ImageModelConfig, ImageResolutionPrice
from repositories.usage_repo import UsageRepository
from repositories.model_config_repo import ModelConfigRepository
from repositories.video_model_repo import VideoModelRepository
from repositories.image_model_repo import ImageModelRepository
from app.config import settings
from log.logger import get_logger

logger = get_logger(__name__)


class BillingService:
    """计费服务"""

    def __init__(self):
        self.usage_repo = UsageRepository()
        self.model_config_repo = ModelConfigRepository()
        self.video_model_repo = VideoModelRepository()
        self.image_model_repo = ImageModelRepository()

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

    def get_video_model_config(
        self, model_name: str, db: Session
    ) -> Optional[VideoModelConfig]:
        """
        获取视频模型配置（含分辨率价格）
        返回: VideoModelConfig object or None
        """
        config = self.video_model_repo.get_by_model_name(model_name, db)
        if not config or not config.is_enabled:
            return None
        return config

    def calculate_video_cost(
        self, model_name: str, resolution: Optional[str], duration: Optional[int], db: Session
    ) -> Tuple[Optional[float], Optional[str], Optional[int]]:
        """
        计算视频生成费用

        参数:
            model_name: 视频模型名称
            resolution: 分辨率，None 则使用默认分辨率
            duration: 视频秒数，None 则使用模型默认时长

        返回:
            (cost, used_resolution, used_duration) or (None, error_msg, None)
            cost为None时表示出错，返回的字符串为错误信息
        """
        config = self.get_video_model_config(model_name, db)
        if config is None:
            return None, "模型未启用或不存在", None

        # 确定分辨率价格
        resolution_price = None
        if resolution:
            resolution_price = self.video_model_repo.get_resolution_price(
                config.id, resolution, db
            )
            if resolution_price is None:
                return None, f"不支持的分辨率: {resolution}", None

        # 使用默认分辨率
        if resolution_price is None:
            resolution_price = self.video_model_repo.get_default_resolution(config.id, db)
            if resolution_price is None:
                return None, "模型未配置默认分辨率", None
            used_resolution = resolution_price.resolution
        else:
            used_resolution = resolution

        # 确定时长
        used_duration = duration if duration else config.default_duration

        # 计算费用
        cost = float(resolution_price.price_per_second) * used_duration

        return round(cost, 6), used_resolution, used_duration

    def get_image_model_config(
        self, model_name: str, db: Session
    ) -> Optional[ImageModelConfig]:
        """
        获取图片模型配置（含分辨率价格）
        返回: ImageModelConfig object or None
        """
        config = self.image_model_repo.get_by_model_name(model_name, db)
        if not config or not config.is_enabled:
            return None
        return config

    def calculate_image_cost(
        self, model_name: str, resolution: Optional[str], n: Optional[int], db: Session
    ) -> tuple[Optional[float], Optional[str], Optional[int]]:
        """
        计算图片生成费用

        参数:
            model_name: 图片模型名称
            resolution: 分辨率，None 则使用默认分辨率
            n: 生成张数，None 则默认为 1

        返回:
            (cost, used_resolution, used_n) or (None, error_msg, None)
            cost为None时表示出错，返回的字符串为错误信息
        """
        config = self.get_image_model_config(model_name, db)
        if config is None:
            return None, "模型未启用或不存在", None

        # 确定分辨率价格
        resolution_price = None
        if resolution:
            resolution_price = self.image_model_repo.get_resolution_price(
                config.id, resolution, db
            )
            if resolution_price is None:
                return None, f"不支持的分辨率: {resolution}", None

        # 使用默认分辨率
        if resolution_price is None:
            resolution_price = self.image_model_repo.get_default_resolution(
                config.id, db
            )
            if resolution_price is None:
                return None, "模型未配置默认分辨率", None
            used_resolution = resolution_price.resolution
        else:
            used_resolution = resolution

        # 确定张数
        used_n = n if n else 1

        # 计算费用
        cost = float(resolution_price.price_per_image) * used_n

        return round(cost, 6), used_resolution, used_n

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
