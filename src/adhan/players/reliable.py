from __future__ import annotations

import logging
from typing import Callable

from adhan.models import MediaRef, PlayResult
from adhan.players.base import Player

logger = logging.getLogger(__name__)


class ReliablePlayer:
    def __init__(
        self,
        inner: Player,
        attempts: int,
        backoff_seconds: float,
        sleep: Callable[[float], None] | None = None,
    ):
        self._inner = inner
        self._attempts = max(1, attempts)
        self._backoff = backoff_seconds
        import time

        self._sleep = sleep or time.sleep

    @property
    def name(self) -> str:
        return self._inner.name

    def health_check(self):
        return self._inner.health_check()

    def play(self, media: MediaRef, volume: float) -> PlayResult:
        health = self._inner.health_check()
        logger.info(
            "pre-play health", extra={"player": self.name, "health": health.state.value}
        )
        last_error = "unknown error"
        for attempt in range(1, self._attempts + 1):
            try:
                result = self._inner.play(media, volume)
                if result.success:
                    return PlayResult(self.name, True, attempts=attempt)
                last_error = result.error or "play returned failure"
            except Exception as exc:  # hardware calls can raise
                last_error = str(exc)
            if attempt < self._attempts:
                self._sleep(self._backoff * attempt)
        logger.warning(
            "play failed", extra={"player": self.name, "error": last_error, "attempts": self._attempts}
        )
        return PlayResult(self.name, False, error=last_error, attempts=self._attempts)
