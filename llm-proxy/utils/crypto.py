"""
加密工具
"""

import hashlib
import hmac
import secrets
from typing import Optional


def hash_sha256(data: str) -> str:
    """SHA256 哈希"""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def hmac_sha256(key: str, message: str) -> str:
    """HMAC-SHA256"""
    return hmac.new(
        key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_random_string(length: int = 32) -> str:
    """生成随机字符串"""
    return secrets.token_hex(length)
