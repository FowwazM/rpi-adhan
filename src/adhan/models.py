from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Prayer(str, Enum):
    FAJR = "fajr"
    DHUHR = "dhuhr"
    ASR = "asr"
    MAGHRIB = "maghrib"
    ISHA = "isha"


# Sunrise is computed but never played; keep it out of the playable set.
PLAYABLE_PRAYERS: list[Prayer] = [
    Prayer.FAJR,
    Prayer.DHUHR,
    Prayer.ASR,
    Prayer.MAGHRIB,
    Prayer.ISHA,
]


@dataclass(frozen=True)
class PrayerSchedule:
    fajr: datetime
    sunrise: datetime
    dhuhr: datetime
    asr: datetime
    maghrib: datetime
    isha: datetime

    def get(self, prayer: Prayer) -> datetime:
        return getattr(self, prayer.value)


@dataclass(frozen=True)
class MediaRef:
    file_path: str  # absolute path on disk (for Bluetooth/local playback)
    url: str        # http URL served to Cast devices


@dataclass(frozen=True)
class PlayResult:
    player: str
    success: bool
    error: str | None = None
    attempts: int = 1


class HealthState(str, Enum):
    OK = "ok"
    UNREACHABLE = "unreachable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class HealthStatus:
    player: str
    state: HealthState
    detail: str | None = None
