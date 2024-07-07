import asyncio
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, Tuple

from async_lru import alru_cache


class StaleWhileRevalidateCache:
    def __init__(self, func, ttl: int, use_stale_ttl: int):
        self.func = func
        self.ttl = ttl
        self.use_stale_ttl = use_stale_ttl
        self.cache: Dict[Tuple, Any] = {}
        self.cache_time: Dict[Tuple, datetime] = {}
        self.lock = asyncio.Lock()
        self.pending_updates: Dict[Tuple, asyncio.Task] = {}

    def __call__(self, *args, **kwargs):
        return self._call(*args, **kwargs)

    async def _call(self, *args, **kwargs):
        key = (args, tuple(sorted(kwargs.items())))
        async with self.lock:
            if key in self.cache:
                cache_age = datetime.now() - self.cache_time[key]
                if cache_age < timedelta(seconds=self.ttl):
                    # Return cached value if not stale
                    return self.cache[key]
                elif cache_age < timedelta(seconds=self.use_stale_ttl):
                    # Return cached value and revalidate in the background if within use_stale_ttl
                    result = self.cache[key]
                    if key not in self.pending_updates:
                        self.pending_updates[key] = asyncio.create_task(
                            self._update_cache(key, *args, **kwargs)
                        )
                    return result

            # Compute and cache the result if not present or stale beyond use_stale_ttl
            result = await self.func(*args, **kwargs)
            self.cache[key] = result
            self.cache_time[key] = datetime.now()
            return result

    async def _update_cache(self, key, *args, **kwargs):
        try:
            result = await self.func(*args, **kwargs)
            async with self.lock:
                self.cache[key] = result
                self.cache_time[key] = datetime.now()
        finally:
            async with self.lock:
                if key in self.pending_updates:
                    del self.pending_updates[key]


def stale_while_revalidate_cache(ttl: int, use_stale_ttl: int):
    def decorator(func):
        return StaleWhileRevalidateCache(func, ttl, use_stale_ttl)

    return decorator
