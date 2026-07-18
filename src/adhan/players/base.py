from __future__ import annotations

from typing import Protocol

from adhan.models import HealthStatus, MediaRef, PlayResult


class Player(Protocol):
    name: str

    def health_check(self) -> HealthStatus: ...
    def play(self, media: MediaRef, volume: float) -> PlayResult: ...
