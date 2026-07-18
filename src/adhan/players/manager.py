from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from adhan.models import MediaRef, PlayResult
from adhan.players.base import Player


class OutputManager:
    def __init__(self, players: list[Player]):
        self._players = players

    def play_all(self, media: MediaRef, volume: float) -> list[PlayResult]:
        if not self._players:
            return []
        with ThreadPoolExecutor(max_workers=len(self._players)) as pool:
            futures = [pool.submit(p.play, media, volume) for p in self._players]
            return [f.result() for f in futures]
