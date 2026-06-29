"""Rate limiting for anti-scrape stability."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    min_interval_sec: float = 5
    max_interval_sec: float = 15
    batch_pause_every: int = 10
    batch_pause_min_sec: float = 30
    batch_pause_max_sec: float = 60
    daily_limit: int = 50
    _processed_today: int = field(default=0, init=False)
    _batch_count: int = field(default=0, init=False)

    def before_item(self) -> None:
        if self._processed_today >= self.daily_limit:
            raise RuntimeError(f"Daily limit reached ({self.daily_limit}). Stop or raise daily_limit in config.")
        if self._batch_count > 0:
            delay = random.uniform(self.min_interval_sec, self.max_interval_sec)
            time.sleep(delay)
        if self._batch_count > 0 and self._batch_count % self.batch_pause_every == 0:
            pause = random.uniform(self.batch_pause_min_sec, self.batch_pause_max_sec)
            time.sleep(pause)

    def after_item(self) -> None:
        self._processed_today += 1
        self._batch_count += 1
