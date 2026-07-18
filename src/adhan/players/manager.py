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
            pairs = [(p, pool.submit(p.play, media, volume)) for p in self._players]
            results: list[PlayResult] = []
            for player, future in pairs:
                try:
                    results.append(future.result())
                except Exception as exc:
                    results.append(PlayResult(player.name, False, error=str(exc)))
            return results
