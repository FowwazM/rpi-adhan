from datetime import datetime, timezone

from adhan.config import FajrMode, PrayerConfig
from adhan.models import Prayer, PrayerSchedule
from adhan.times.adjuster import ScheduleAdjuster


def _dt(h, m):
    return datetime(2026, 7, 18, h, m, tzinfo=timezone.utc)


SCHED = PrayerSchedule(
    fajr=_dt(5, 0), sunrise=_dt(6, 30), dhuhr=_dt(13, 0),
    asr=_dt(17, 0), maghrib=_dt(20, 30), isha=_dt(22, 0),
)


def test_fajr_before_sunrise_mode():
    adj = ScheduleAdjuster({"fajr": PrayerConfig(mode=FajrMode.BEFORE_SUNRISE, before_sunrise_minutes=30)})
    out = adj.adjust(SCHED)
    assert out[Prayer.FAJR] == _dt(6, 0)


def test_offset_applied():
    adj = ScheduleAdjuster({"asr": PrayerConfig(offset_minutes=60)})
    out = adj.adjust(SCHED)
    assert out[Prayer.ASR] == _dt(18, 0)


def test_disabled_prayer_excluded():
    adj = ScheduleAdjuster({"isha": PrayerConfig(enabled=False)})
    out = adj.adjust(SCHED)
    assert Prayer.ISHA not in out
    assert Prayer.FAJR in out


def test_defaults_when_prayer_missing_from_config():
    adj = ScheduleAdjuster({})
    out = adj.adjust(SCHED)
    assert out[Prayer.FAJR] == _dt(5, 0)
    assert set(out) == {Prayer.FAJR, Prayer.DHUHR, Prayer.ASR, Prayer.MAGHRIB, Prayer.ISHA}
