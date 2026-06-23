"""Shared async rate limiting for scraping workers."""

from __future__ import annotations

import asyncio
import random
import time

try:
    from .logging_utils import configure_logging, get_logger
except ImportError:
    from logging_utils import configure_logging, get_logger

demo_logger = get_logger("rate_limiter")


class AsyncRateLimiter:
    """Serialize access to a global minimum request spacing."""

    def __init__(self, max_requests_per_minute: float, jitter_ratio: float = 0.15) -> None:
        """Create a limiter for the given aggregate request ceiling."""
        if max_requests_per_minute <= 0:
            raise ValueError("max_requests_per_minute must be greater than 0")
        if jitter_ratio < 0:
            raise ValueError("jitter_ratio must be greater than or equal to 0")

        self._base_spacing_seconds = 60.0 / max_requests_per_minute
        self._jitter_ratio = jitter_ratio
        self._next_allowed_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until the next globally allowed request slot."""
        async with self._lock:
            now = time.monotonic()
            reserved_time = max(now, self._next_allowed_time)
            wait_seconds = reserved_time - now
            spacing_seconds = self._base_spacing_seconds * random.uniform(
                1.0 - self._jitter_ratio,
                1.0 + self._jitter_ratio,
            )
            self._next_allowed_time = reserved_time + spacing_seconds

        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)


async def _demo() -> None:
    configure_logging("INFO")
    limiter = AsyncRateLimiter(max_requests_per_minute=25.0)
    previous = time.monotonic()
    for request_number in range(1, 7):
        await limiter.acquire()
        now = time.monotonic()
        demo_logger.info(
            "Rate limiter slot acquired",
            context={"request": request_number, "delta_seconds": f"{now - previous:.2f}"},
        )
        previous = now


if __name__ == "__main__":
    asyncio.run(_demo())
