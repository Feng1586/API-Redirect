"""
Redis 客户端封装
用于存储 Session、验证码等
"""

import json
from typing import Optional, Any, Dict

import redis

from app.config import settings


class RedisClient:
    """Redis 客户端封装"""

    def __init__(self):
        self.client = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.db,
            password=settings.redis.password or None,
            decode_responses=True,
        )

    # ========== 基础操作 ==========

    def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """
        设置键值对
        """
        if ttl:
            return bool(self.client.setex(key, ttl, value))
        return bool(self.client.set(key, value))

    def get(self, key: str) -> Optional[str]:
        """
        获取值
        """
        return self.client.get(key)

    def delete(self, key: str) -> bool:
        """
        删除键
        """
        return bool(self.client.delete(key))

    def exists(self, key: str) -> bool:
        """
        检查键是否存在
        """
        return bool(self.client.exists(key))

    def expire(self, key: str, ttl: int) -> bool:
        """
        设置过期时间
        """
        return bool(self.client.expire(key, ttl))

    def ttl(self, key: str) -> int:
        """
        获取剩余 TTL
        """
        return self.client.ttl(key)

    # ========== JSON 操作 ==========

    def set_json(self, key: str, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        设置 JSON 数据
        """
        return self.set(key, json.dumps(data), ttl)

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """
        获取 JSON 数据
        """
        value = self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None

    # ========== Session 管理 ==========

    SESSION_PREFIX = "session:"
    SESSION_TTL = 86400  # 1天

    def set_session(self, session_id: str, user_id: int) -> bool:
        """
        存储 Session
        Key: session:{session_id}
        Value: { "user_id": 123, "created_at": "..." }
        """
        key = f"{self.SESSION_PREFIX}{session_id}"
        data = {
            "user_id": user_id,
        }
        return self.set_json(key, data, self.SESSION_TTL)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取 Session
        """
        key = f"{self.SESSION_PREFIX}{session_id}"
        return self.get_json(key)

    def delete_session(self, session_id: str) -> bool:
        """
        删除 Session
        """
        key = f"{self.SESSION_PREFIX}{session_id}"
        return self.delete(key)

    def refresh_session(self, session_id: str) -> bool:
        """
        刷新 Session 有效期 (续期1天)
        """
        key = f"{self.SESSION_PREFIX}{session_id}"
        return self.expire(key, self.SESSION_TTL)

    def delete_user_sessions(self, user_id: int) -> int:
        """
        删除用户的所有 Session
        返回删除的数量
        """
        pattern = f"{self.SESSION_PREFIX}*"
        count = 0
        for key in self.client.scan_iter(pattern):
            data = self.get_json(key)
            if data and data.get("user_id") == user_id:
                self.delete(key)
                count += 1
        return count

    # ========== 验证码管理 ==========

    VERIFY_CODE_PREFIX = "verify_code:"
    VERIFY_CODE_TTL = 300  # 5分钟

    def set_verify_code(self, email: str, code: str) -> bool:
        """
        存储验证码
        Key: verify_code:{email}
        Value: { "code": "123456", "created_at": "...", "attempts": 0 }
        """
        key = f"{self.VERIFY_CODE_PREFIX}{email}"
        data = {
            "code": code,
            "attempts": 0,
        }
        return self.set_json(key, data, self.VERIFY_CODE_TTL)

    def get_verify_code(self, email: str) -> Optional[Dict[str, Any]]:
        """
        获取验证码信息
        """
        key = f"{self.VERIFY_CODE_PREFIX}{email}"
        return self.get_json(key)

    def verify_code(self, email: str, code: str) -> tuple[bool, str]:
        """
        验证验证码
        返回: (is_valid, error_message)
        """
        data = self.get_verify_code(email)
        if not data:
            return False, "验证码已过期"

        if data.get("code") != code:
            return False, "验证码错误"

        return True, "验证成功"

    def delete_verify_code(self, email: str) -> bool:
        """
        删除验证码
        """
        key = f"{self.VERIFY_CODE_PREFIX}{email}"
        return self.delete(key)

    # ========== 限流计数 ==========

    RATE_LIMIT_PREFIX = "rate_limit:verify:"
    RATE_LIMIT_TTL = 60  # 1分钟

    def increment_rate_limit(self, email: str) -> int:
        """
        增加验证码请求频率计数
        """
        key = f"{self.RATE_LIMIT_PREFIX}{email}"
        pipe = self.client.pipeline()
        pipe.incr(key)
        pipe.expire(key, self.RATE_LIMIT_TTL)
        results = pipe.execute()
        return results[0]

    def get_rate_limit(self, email: str) -> int:
        """
        获取验证码请求频率计数
        """
        key = f"{self.RATE_LIMIT_PREFIX}{email}"
        value = self.get(key)
        return int(value) if value else 0

    # ========== 登录错误计数 ==========

    LOGIN_FAIL_PREFIX = "login_fail:"
    LOGIN_FAIL_TTL = 900  # 15分钟

    def increment_login_fail(self, identifier: str) -> int:
        """
        增加登录错误计数
        """
        key = f"{self.LOGIN_FAIL_PREFIX}{identifier}"
        pipe = self.client.pipeline()
        pipe.incr(key)
        pipe.expire(key, self.LOGIN_FAIL_TTL)
        results = pipe.execute()
        return results[0]

    def get_login_fail_count(self, identifier: str) -> int:
        """
        获取登录错误计数
        """
        key = f"{self.LOGIN_FAIL_PREFIX}{identifier}"
        value = self.get(key)
        return int(value) if value else 0

    def reset_login_fail(self, identifier: str) -> bool:
        """
        重置登录错误计数
        """
        key = f"{self.LOGIN_FAIL_PREFIX}{identifier}"
        return self.delete(key)

    # ========== 用量缓存 ==========

    DAILY_USAGE_PREFIX = "daily_usage:"
    DAILY_USAGE_TTL = 86400  # 1天

    def set_daily_usage(self, user_id: int, date: str, tokens: int, cost: float, requests: int) -> bool:
        """
        设置当日用量缓存
        Key: daily_usage:{user_id}:{date}
        """
        key = f"{self.DAILY_USAGE_PREFIX}{user_id}:{date}"
        data = {
            "tokens": tokens,
            "cost": cost,
            "requests": requests,
        }
        return self.set_json(key, data, self.DAILY_USAGE_TTL)

    def get_daily_usage(self, user_id: int, date: str) -> Optional[Dict[str, Any]]:
        """
        获取当日用量缓存
        """
        key = f"{self.DAILY_USAGE_PREFIX}{user_id}:{date}"
        return self.get_json(key)


# 全局单例
redis_client = RedisClient()
