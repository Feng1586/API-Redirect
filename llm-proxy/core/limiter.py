"""
限流模块
"""

import time
from typing import Optional

import redis

from app.config import settings


class RateLimiter:
    """基于 Redis 的限流器"""

    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.db,
            password=settings.redis.password or None,
            decode_responses=True,
        )

    def _get_key(self, prefix: str, identifier: str) -> str:
        return f"rate_limit:{prefix}:{identifier}"

    def check_rate_limit(
        self,
        prefix: str,
        identifier: str,
        max_attempts: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """
        检查限流
        返回: (is_allowed, remaining_attempts)
        """
        key = self._get_key(prefix, identifier)
        current = self.redis_client.get(key)

        if current is None:
            self.redis_client.setex(key, window_seconds, 1)
            return True, max_attempts - 1

        current_attempts = int(current)
        if current_attempts >= max_attempts:
            ttl = self.redis_client.ttl(key)
            return False, 0

        self.redis_client.incr(key)
        return True, max_attempts - current_attempts - 1

    def increment(self, prefix: str, identifier: str, window_seconds: int) -> int:
        """增加计数"""
        key = self._get_key(prefix, identifier)
        pipe = self.redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        results = pipe.execute()
        return results[0]

    def reset(self, prefix: str, identifier: str) -> bool:
        """重置限流计数"""
        key = self._get_key(prefix, identifier)
        return bool(self.redis_client.delete(key))

    def get_ttl(self, prefix: str, identifier: str) -> int:
        """获取剩余 TTL"""
        key = self._get_key(prefix, identifier)
        return self.redis_client.ttl(key)


rate_limiter = RateLimiter()
