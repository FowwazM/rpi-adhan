from __future__ import annotations

import logging

from adhan.media import MediaManager
from adhan.models import Prayer, PlayResult
from adhan.players.manager import OutputManager
from adhan.state import StateStore

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, media: MediaManager, outputs: OutputManager, state: StateStore):
        self._media = media
        self._outputs = outputs
        self._state = state

    def handle_prayer(self, prayer: Prayer) -> None:
        logger.info("adhan triggered", extra={"prayer": prayer.value})
        try:
            media, volume = self._media.resolve(prayer)
        except FileNotFoundError as exc:
            logger.error("media resolve failed", extra={"prayer": prayer.value, "error": str(exc)})
            self._record(prayer, [PlayResult("media", False, error=str(exc))])
            return
        results = self._outputs.play_all(media, volume)
        for r in results:
            level = logging.INFO if r.success else logging.WARNING
            logger.log(
                level,
                "output result",
                extra={"prayer": prayer.value, "player": r.player, "success": r.success},
            )
        if results and not any(r.success for r in results):
            logger.error("adhan failed on all outputs", extra={"prayer": prayer.value})
        self._record(prayer, results)

    def _record(self, prayer: Prayer, results: list[PlayResult]) -> None:
        try:
            self._state.record_result(prayer, results)
        except Exception:
            logger.exception("failed to record state", extra={"prayer": prayer.value})
