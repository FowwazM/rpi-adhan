from __future__ import annotations

import subprocess
from datetime import date

from adhan.models import HealthState, HealthStatus, MediaRef, PlayResult, PrayerSchedule


class FakeTimeProvider:
    def __init__(self, schedule: PrayerSchedule):
        self._schedule = schedule
        self.calls: list[date] = []

    def get_schedule(self, day: date) -> PrayerSchedule:
        self.calls.append(day)
        return self._schedule


class FakeJob:
    def __init__(self, run_date, args, job_id, kwargs=None):
        self.run_date = run_date
        self.args = args
        self.id = job_id
        self.kwargs = kwargs or {}


class FakeScheduler:
    """Records add_job calls the way APScheduler would be driven."""

    def __init__(self):
        self.jobs: list[FakeJob] = []
        self.started = False
        self.cron_jobs: list[dict] = []

    def add_job(self, func, trigger, **kwargs):
        if trigger == "date":
            self.jobs.append(FakeJob(kwargs["run_date"], kwargs.get("args", []), kwargs.get("id"), kwargs))
        elif trigger == "cron":
            self.cron_jobs.append(kwargs)
        return FakeJob(kwargs.get("run_date"), kwargs.get("args", []), kwargs.get("id"), kwargs)

    def remove_all_jobs(self):
        self.jobs.clear()
        self.cron_jobs.clear()  # APScheduler clears ALL jobs, cron included

    def start(self):
        self.started = True


class FakePlayer:
    """Fails its first `fail_times` play() calls, then succeeds."""

    def __init__(self, name: str, fail_times: int = 0, health=HealthState.OK, raises: bool = False):
        self.name = name
        self._fail_times = fail_times
        self._health = health
        self._raises = raises
        self.calls: list[tuple[MediaRef, float]] = []

    def health_check(self) -> HealthStatus:
        return HealthStatus(player=self.name, state=self._health)

    def play(self, media: MediaRef, volume: float) -> PlayResult:
        self.calls.append((media, volume))
        if len(self.calls) <= self._fail_times:
            if self._raises:
                raise RuntimeError("boom")
            return PlayResult(self.name, success=False, error="simulated failure")
        return PlayResult(self.name, success=True)


class _FakeMediaController:
    def __init__(self, states):
        self._states = list(states)
        self.played = None
        self.player_state = "UNKNOWN"

    def play_media(self, url, content_type):
        self.played = (url, content_type)

    def block_until_active(self, timeout=None):
        pass

    @property
    def status(self):
        self.player_state = self._states.pop(0) if self._states else "IDLE"

        class _S:
            pass

        s = _S()
        s.player_state = self.player_state
        return s


class FakeCast:
    def __init__(self, name="Living", volume=0.3, states=("PLAYING", "IDLE")):
        self.name = name
        self.volume_level = volume
        self.set_volumes: list[float] = []
        self.media_controller = _FakeMediaController(states)
        self.waited = False

    def wait(self, timeout=None):
        self.waited = True

    def set_volume(self, level):
        self.volume_level = level
        self.set_volumes.append(level)

    @property
    def status(self):
        class _S:
            pass

        s = _S()
        s.volume_level = self.volume_level
        return s


class RecordingRunner:
    """Stands in for subprocess.run. `fail_on` = substring that triggers CalledProcessError."""

    def __init__(self, sinks_output="adhan_combined\t...\n", fail_on: str | None = None):
        self.commands: list[list[str]] = []
        self._sinks_output = sinks_output
        self._fail_on = fail_on

    def __call__(self, args, check=False, capture_output=False, text=False, timeout=None):
        self.commands.append(args)
        if self._fail_on and self._fail_on in " ".join(args):
            raise subprocess.CalledProcessError(1, args)
        stdout = ""
        if args[:3] == ["pactl", "list", "short"]:
            stdout = self._sinks_output

        class _CP:
            pass

        cp = _CP()
        cp.returncode = 0
        cp.stdout = stdout
        return cp
