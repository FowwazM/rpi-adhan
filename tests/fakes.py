from __future__ import annotations

from datetime import date

from adhan.models import PrayerSchedule


class FakeTimeProvider:
    def __init__(self, schedule: PrayerSchedule):
        self._schedule = schedule
        self.calls: list[date] = []

    def get_schedule(self, day: date) -> PrayerSchedule:
        self.calls.append(day)
        return self._schedule
