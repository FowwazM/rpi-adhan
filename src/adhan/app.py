from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from adhan.config import Config, OutputsConfig, ReliabilityConfig
from adhan.logging_setup import configure_logging
from adhan.media import MediaHTTPServer, MediaManager
from adhan.models import Prayer
from adhan.netutil import get_lan_ip
from adhan.orchestrator import Orchestrator
from adhan.players.base import Player
from adhan.players.bluetooth import BluetoothPlayer
from adhan.players.cast import CastPlayer
from adhan.players.manager import OutputManager
from adhan.players.reliable import ReliablePlayer
from adhan.scheduler import AdhanScheduler
from adhan.state import StateStore
from adhan.times.adjuster import ScheduleAdjuster
from adhan.times.offline import OfflineProvider

logger = logging.getLogger(__name__)

DEFAULT_COMBINED_SINK = "adhan_combined"


def build_players(
    outputs: OutputsConfig, reliability: ReliabilityConfig, combined_sink: str
) -> list[Player]:
    raw: list[Player] = [CastPlayer(c.name) for c in outputs.cast]
    if outputs.bluetooth.speakers:
        raw.append(BluetoothPlayer(combined_sink))
    return [
        ReliablePlayer(p, attempts=reliability.retry_attempts, backoff_seconds=reliability.retry_backoff_seconds)
        for p in raw
    ]


class App:
    def __init__(
        self,
        config: Config,
        media_dir: Path,
        state_path: Path,
        http_port: int | None = None,
    ):
        self._config = config
        self._media_dir = Path(media_dir)
        self._state_path = Path(state_path)
        # None -> use the configured port; 0 -> an ephemeral port. test-play uses 0
        # so it never collides with a running `adhan run` holding the real port.
        self._http_port = http_port
        self._http: MediaHTTPServer | None = None
        self._orchestrator: Orchestrator | None = None
        self._host: str | None = None

    def _resolve_host(self) -> str:
        if self._host is None:
            cfg = self._config
            self._host = get_lan_ip() if cfg.network.http_host == "auto" else cfg.network.http_host
        return self._host

    def _base_url(self) -> str:
        # After build(), use the actually-bound port (matters when it's ephemeral).
        port = self._http.port if self._http is not None else self._config.network.http_port
        return f"http://{self._resolve_host()}:{port}"

    def build(self) -> AdhanScheduler:
        # pactl/paplay (Bluetooth output) need the user runtime dir to find the
        # PipeWire socket. Ensure it's set even when launched without it (e.g. a
        # manual `sudo -u adhan ... test-play`); the systemd unit also sets it.
        os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        cfg = self._config
        host = self._resolve_host()
        port = cfg.network.http_port if self._http_port is None else self._http_port
        self._http = MediaHTTPServer(self._media_dir, host=host, port=port)
        media = MediaManager(cfg.audio, self._media_dir, self._base_url())
        players = build_players(cfg.outputs, cfg.reliability, DEFAULT_COMBINED_SINK)
        state = StateStore(self._state_path)
        self._orchestrator = Orchestrator(media, OutputManager(players), state)
        if cfg.prayer_times.source != "offline":
            raise ValueError(
                f"prayer_times.source '{cfg.prayer_times.source}' is not supported in Phase 1 (offline only)"
            )
        provider = OfflineProvider(cfg.prayer_times.offline, cfg.location)
        adjuster = ScheduleAdjuster(cfg.prayer_times.prayers)
        backend = BackgroundScheduler(timezone=cfg.location.timezone)
        return AdhanScheduler(
            provider=provider,
            adjuster=adjuster,
            on_prayer=self._orchestrator.handle_prayer,
            backend=backend,
            misfire_grace_seconds=cfg.reliability.misfire_grace_seconds,
            on_regenerate=state.set_schedule,
        )

    def trigger(self, prayer: Prayer) -> None:
        """Ad-hoc play for `adhan test-play`: start the media HTTP server so
        Cast outputs can fetch the file, fire the adhan, then stop it."""
        configure_logging(self._config.logging.level, self._config.logging.json)
        assert self._http is not None and self._orchestrator is not None, "call build() first"
        self._http.start()
        try:
            self._orchestrator.handle_prayer(prayer)
        finally:
            self._http.stop()

    def run(self) -> None:
        configure_logging(self._config.logging.level, self._config.logging.json)
        scheduler = self.build()
        assert self._http is not None
        self._http.start()
        scheduler.start()
        logger.info("adhan service started", extra={"base_url": self._base_url()})
        threading.Event().wait()  # run forever
