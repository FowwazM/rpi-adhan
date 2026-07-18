from __future__ import annotations

import time
from typing import Callable

from adhan.models import HealthState, HealthStatus, MediaRef, PlayResult

_ACTIVE_STATES = {"PLAYING", "BUFFERING"}


def _default_factory(name: str):
    import pychromecast

    chromecasts, browser = pychromecast.get_listed_chromecasts(friendly_names=[name])
    if not chromecasts:
        raise OSError(f"Cast device not found: {name}")
    cc = chromecasts[0]
    cc.wait(timeout=10)
    return cc


class CastPlayer:
    def __init__(
        self,
        name: str,
        cast_factory: Callable[[str], object] = _default_factory,
        poll_interval: float = 1.0,
        max_wait_seconds: float = 600.0,
        sleep: Callable[[float], None] | None = None,
    ):
        self.name = f"cast:{name}"
        self._device_name = name
        self._factory = cast_factory
        self._poll = poll_interval
        self._max_wait = max_wait_seconds
        self._sleep = sleep or time.sleep

    def health_check(self) -> HealthStatus:
        try:
            self._factory(self._device_name)
            return HealthStatus(self.name, HealthState.OK)
        except Exception as exc:
            return HealthStatus(self.name, HealthState.UNREACHABLE, detail=str(exc))

    def play(self, media: MediaRef, volume: float) -> PlayResult:
        try:
            cc = self._factory(self._device_name)
        except Exception as exc:
            return PlayResult(self.name, False, error=str(exc))
        previous = cc.status.volume_level
        try:
            cc.set_volume(volume)
            mc = cc.media_controller
            mc.play_media(media.url, "audio/mpeg")
            mc.block_until_active(timeout=30)
            self._wait_for_finish(mc)
            return PlayResult(self.name, True)
        except Exception as exc:
            return PlayResult(self.name, False, error=str(exc))
        finally:
            try:
                cc.set_volume(previous)
            except Exception:
                pass

    def _wait_for_finish(self, mc) -> None:
        waited = 0.0
        while mc.status.player_state in _ACTIVE_STATES:
            if self._poll <= 0 or waited >= self._max_wait:
                break
            self._sleep(self._poll)
            waited += self._poll
