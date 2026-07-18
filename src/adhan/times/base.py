from __future__ import annotations

from datetime import date
from typing import Protocol

from adhan.models import PrayerSchedule


class TimeProvider(Protocol):
    def get_schedule(self, day: date) -> PrayerSchedule: ...
