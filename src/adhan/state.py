from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

from adhan.models import Prayer, PlayResult


class StateStore:
    def __init__(self, path: str | Path, clock: Callable[[], datetime] | None = None):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock or (lambda: datetime.now().astimezone())
        self._lock = threading.Lock()
        self._data: dict = {
            "service_started_at": self._clock().isoformat(),
            "next_prayer": None,
            "today_schedule": {},
            "last_results": {},
        }
        with self._lock:
            self._write()

    def set_schedule(self, jobs: dict[Prayer, datetime]) -> None:
        with self._lock:
            self._data["today_schedule"] = {p.value: when.isoformat() for p, when in jobs.items()}
            now = self._clock()
            upcoming = sorted((when, p.value) for p, when in jobs.items() if when > now)
            if upcoming:
                when, name = upcoming[0]
                self._data["next_prayer"] = {"name": name, "time": when.isoformat()}
            else:
                self._data["next_prayer"] = None
            self._write()

    def record_result(self, prayer: Prayer, results: list[PlayResult]) -> None:
        with self._lock:
            self._data["last_results"][prayer.value] = {
                "at": self._clock().isoformat(),
                "outputs": {
                    r.player: {"success": r.success, "error": r.error, "attempts": r.attempts}
                    for r in results
                },
            }
            self._write()

    def _write(self) -> None:
        # Caller must hold self._lock.
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        os.replace(tmp, self._path)
