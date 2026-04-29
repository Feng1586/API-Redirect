"""
安全模块（密码、加密）
"""

import hashlib
import hmac
import secrets
import uuid
from typing import Optional

import bcrypt
from itsdangerous import URLSafeTimedSerializer

from app.config import settings


def hash_password(password: str) -> str:
    """
    使用bcrypt对密码进行哈希
    输入: plaintext_password
    输出: hashed_password
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plaintext: str, hashed: str) -> bool:
    """
    验证密码
    输入: plaintext_password, hashed_password
    输出: bool
    """
    return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("utf-8"))


def create_session_id() -> str:
    """
    生成安全的Session ID (UUID4 + 随机字符串)
    输出: session_id
    """
    return f"{uuid.uuid4().hex}{secrets.token_hex(16)}"


def sign_cookie(value: str, secret: Optional[str] = None) -> str:
    """
    对Cookie值进行签名
    输入: value, secret_key
    输出: signed_value
    """
    secret = secret or settings.app.secret_key
    serializer = URLSafeTimedSerializer(secret)
    return serializer.dumps(value)


def hash_api_key(api_key: str) -> str:
    """
    对 API Key 进行哈希（SHA-256 + 盐）
    用于数据库存储，防止明文泄露
    输入: 明文 API Key (sk-xxx)
    输出: 哈希值
    """
    salt = settings.app.secret_key or "default-salt"
    return hmac.new(
        salt.encode("utf-8"),
        api_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_api_key(plaintext: str, hashed: str) -> bool:
    """
    验证 API Key
    输入: 明文 API Key, 数据库中的哈希值
    输出: bool
    """
    return hmac.compare_digest(hash_api_key(plaintext), hashed)


def verify_cookie_signature(value: str, signature: str, secret: Optional[str] = None) -> bool:
    """
    验证Cookie签名
    输入: value, signature, secret_key
    输出: bool
    """
    secret = secret or settings.app.secret_key
    serializer = URLSafeTimedSerializer(secret)
    try:
        return serializer.loads(signature) == value
    except Exception:
        return False
