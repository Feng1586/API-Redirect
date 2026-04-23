"""
Token生成工具
"""

import random
import time
import string
from typing import Optional


def generate_verify_code(length: int = 6) -> str:
    """
    生成邮箱验证码 (纯数字)
    """
    return "".join(random.choices(string.digits, k=length))


def generate_api_key() -> str:
    """
    生成API-Key (sk- + 32位随机字符串)
    输出格式: sk-a1b2c3d4e5f6...
    """
    random_part = "".join(random.choices(string.ascii_lowercase + string.digits, k=32))
    return f"sk-{random_part}"


def generate_order_no() -> str:
    """
    生成订单号 (时间戳 + 随机数)
    输出格式: ORD20240115103045123456
    """
    timestamp = time.strftime("%Y%m%d%H%M%S")
    random_part = "".join(random.choices(string.digits, k=6))
    return f"ORD{timestamp}{random_part}"
