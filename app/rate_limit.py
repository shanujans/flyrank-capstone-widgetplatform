"""
A small in-memory, sliding-window rate limiter.

LIMITATION (documented honestly, see README): this state lives in a single
process's memory. It resets on restart and does not share state across
multiple worker processes. For this capstone's scope (localhost, single
uvicorn worker) that's the right trade-off — a real multi-instance deployment
would back this with Redis (INCR + EXPIRE) instead. The interface below is
deliberately small so swapping the backend later doesn't touch call sites.
"""
import threading
import time
from collections import deque


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        """
        Returns (allowed, retry_after_seconds).
        """
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] < cutoff:
                hits.popleft()

            if len(hits) >= limit:
                retry_after = int(hits[0] + window_seconds - now) + 1
                return False, max(retry_after, 1)

            hits.append(now)
            return True, 0

    def reset(self) -> None:
        """Test helper — clears all counters."""
        with self._lock:
            self._hits.clear()


# Single process-wide instance shared by the submission endpoint.
limiter = RateLimiter()
