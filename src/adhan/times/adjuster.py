from __future__ import annotations

from datetime import datetime, timedelta

from adhan.config import FajrMode, PrayerConfig
from adhan.models import PLAYABLE_PRAYERS, Prayer, PrayerSchedule


class ScheduleAdjuster:
    def __init__(self, prayers: dict[str, PrayerConfig]):
        self._prayers = prayers

    def _config_for(self, prayer: Prayer) -> PrayerConfig:
        return self._prayers.get(prayer.value, PrayerConfig())

    def adjust(self, schedule: PrayerSchedule) -> dict[Prayer, datetime]:
        result: dict[Prayer, datetime] = {}
        for prayer in PLAYABLE_PRAYERS:
            cfg = self._config_for(prayer)
            if not cfg.enabled:
                continue
            if prayer is Prayer.FAJR and cfg.mode is FajrMode.BEFORE_SUNRISE:
                base = schedule.sunrise - timedelta(minutes=cfg.before_sunrise_minutes)
            else:
                base = schedule.get(prayer)
            result[prayer] = base + timedelta(minutes=cfg.offset_minutes)
        return result
