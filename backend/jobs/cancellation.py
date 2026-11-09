import time
import redis
from django.conf import settings


class RedisCancelFlag:
    def __init__(self, job_id: str):
        self.key = f"cancel:{job_id}"
        self._redis = redis.from_url(getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6379/0"))
        self._cache = False
        self._checked_at = 0

    def set(self):
        self._redis.set(self.key, "1", ex=3600)
        self._cache = True

    def is_set(self) -> bool:
        now = time.time()
        if now - self._checked_at < 5:
            return self._cache
        self._checked_at = now
        try:
            self._cache = bool(self._redis.get(self.key))
        except Exception:
            pass
        return self._cache

    def clear(self):
        self._redis.delete(self.key)
        self._cache = False
