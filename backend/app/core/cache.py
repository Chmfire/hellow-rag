# -*- coding: utf-8 -*-
"""
Redis 缓存模块
参考 SuperMew/cache.py 实现
"""
import json
from typing import Any, Optional
from app.core.config import settings

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RedisCache:
    def __init__(self):
        self.redis_url = settings.redis_url
        self.key_prefix = settings.redis_key_prefix
        self.default_ttl = settings.redis_cache_ttl_seconds
        self._client = None

    def _get_client(self):
        if not REDIS_AVAILABLE:
            return None
        if self._client is None:
            try:
                self._client = redis.Redis.from_url(self.redis_url, decode_responses=True)
            except Exception:
                self._client = None
        return self._client

    def _key(self, key: str) -> str:
        return f"{self.key_prefix}:{key}"

    def get_json(self, key: str) -> Optional[Any]:
        try:
            client = self._get_client()
            if not client:
                return None
            value = client.get(self._key(key))
            if not value:
                return None
            return json.loads(value)
        except Exception:
            return None

    def set_json(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        try:
            client = self._get_client()
            if not client:
                return
            payload = json.dumps(value, ensure_ascii=False)
            client.setex(self._key(key), ttl or self.default_ttl, payload)
        except Exception:
            return

    def delete(self, key: str) -> None:
        try:
            client = self._get_client()
            if not client:
                return
            client.delete(self._key(key))
        except Exception:
            return

    def delete_pattern(self, pattern: str) -> None:
        try:
            client = self._get_client()
            if not client:
                return
            full_pattern = self._key(pattern)
            keys = client.keys(full_pattern)
            if keys:
                client.delete(*keys)
        except Exception:
            return


cache = RedisCache()
