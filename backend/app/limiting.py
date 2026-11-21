"""Bounded per-process sliding windows for a single API instance."""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

from .config import settings


class SlidingWindow:
    def __init__(self):
        self.windows = defaultdict(deque)
        self.lock = Lock()

    def check(self, key: str, limit: int, seconds: int, now=None):
        moment = time.monotonic() if now is None else now
        with self.lock:
            queue = self.windows[key]
            while queue and queue[0] <= moment - seconds:
                queue.popleft()
            if len(queue) >= limit:
                raise HTTPException(
                    429, "Too many attempts. Please try again later.", headers={"Retry-After": str(seconds)}
                )
            queue.append(moment)
            if len(self.windows) > 10000:
                self.windows = defaultdict(
                    deque, {k: q for k, q in self.windows.items() if q and q[-1] > moment - 3600}
                )


limiter = SlidingWindow()


def protect(request: Request, action: str, email="", limit=10, seconds=900):
    if settings.rate_limits_enabled:
        ip = request.client.host if request.client else "unknown"
        limiter.check(f"{action}:ip:{ip}", limit * 5, seconds)
        if email:
            limiter.check(f"{action}:account:{email.strip().lower()}", limit, seconds)
