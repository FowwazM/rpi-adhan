from __future__ import annotations

import subprocess
from typing import Callable

from adhan.models import HealthState, HealthStatus, MediaRef, PlayResult

Runner = Callable[..., subprocess.CompletedProcess]


class BluetoothPlayer:
    """Plays to a PipeWire combined sink that aggregates the paired A2DP sinks.

    The combined sink itself is created by the system layer (Task 8.3) so all
    Bluetooth speakers play together from a single play() call.
    """

    def __init__(
        self,
        sink_name: str,
        runner: Runner = subprocess.run,
        command_timeout: float = 15.0,
        play_timeout: float = 300.0,
    ):
        self.name = f"bluetooth:{sink_name}"
        self._sink = sink_name
        self._run = runner
        self._command_timeout = command_timeout
        self._play_timeout = play_timeout

    def _sink_present(self) -> bool:
        cp = self._run(
            ["pactl", "list", "short", "sinks"],
            check=True, capture_output=True, text=True, timeout=self._command_timeout,
        )
        return any(self._sink in line.split() for line in (cp.stdout or "").splitlines())

    def health_check(self) -> HealthStatus:
        try:
            if self._sink_present():
                return HealthStatus(self.name, HealthState.OK)
            return HealthStatus(self.name, HealthState.UNREACHABLE, detail="combined sink missing")
        except Exception as exc:
            return HealthStatus(self.name, HealthState.UNREACHABLE, detail=str(exc))

    def play(self, media: MediaRef, volume: float) -> PlayResult:
        try:
            percent = f"{int(round(volume * 100))}%"
            self._run(["pactl", "set-sink-volume", self._sink, percent], check=True, timeout=self._command_timeout)
            self._run(["paplay", f"--device={self._sink}", media.file_path], check=True, timeout=self._play_timeout)
            return PlayResult(self.name, True)
        except Exception as exc:
            return PlayResult(self.name, False, error=str(exc))
