"""
限流模块
"""

import time
from typing import Optional

from utils.redis_client import RedisClient


class RateLimiter:
    """基于 Redis 的限流器"""

    def __init__(self):
        self._redis = RedisClient()

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
        current = self._redis.get(key)

        if current is None:
            self._redis.set(key, "1", ttl=window_seconds)
            return True, max_attempts - 1

        current_attempts = int(current)
        if current_attempts >= max_attempts:
            ttl = self._redis.ttl(key)
            return False, 0

        self._redis.client.incr(key)
        return True, max_attempts - current_attempts - 1

    def increment(self, prefix: str, identifier: str, window_seconds: int) -> int:
        """增加计数"""
        key = self._get_key(prefix, identifier)
        pipe = self._redis.client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        results = pipe.execute()
        return results[0]

    def reset(self, prefix: str, identifier: str) -> bool:
        """重置限流计数"""
        key = self._get_key(prefix, identifier)
        return self._redis.delete(key)

    def get_ttl(self, prefix: str, identifier: str) -> int:
        """获取剩余 TTL"""
        key = self._get_key(prefix, identifier)
        return self._redis.ttl(key)


rate_limiter = RateLimiter()
