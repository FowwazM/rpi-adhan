from datetime import date
from zoneinfo import ZoneInfo

import pytest

from adhan.config import LocationConfig, OfflineConfig, Madhab
from adhan.times.offline import OfflineProvider


LOCATION = LocationConfig(latitude=29.7007851, longitude=-95.8028693, timezone="America/Chicago")


def test_schedule_is_ordered_and_localized():
    provider = OfflineProvider(OfflineConfig(method="north_america", madhab=Madhab.SHAFI), LOCATION)
    sched = provider.get_schedule(date(2026, 7, 18))

    order = [sched.fajr, sched.sunrise, sched.dhuhr, sched.asr, sched.maghrib, sched.isha]
    assert order == sorted(order), "prayer times must be monotonically increasing"

    for dt in order:
        assert dt.tzinfo is not None, "times must be timezone-aware"
        local = dt.astimezone(ZoneInfo("America/Chicago"))
        assert local.date() == date(2026, 7, 18)


def test_hanafi_asr_is_later_than_shafi():
    day = date(2026, 7, 18)
    shafi = OfflineProvider(OfflineConfig(madhab=Madhab.SHAFI), LOCATION).get_schedule(day)
    hanafi = OfflineProvider(OfflineConfig(madhab=Madhab.HANAFI), LOCATION).get_schedule(day)
    assert hanafi.asr > shafi.asr


def test_unknown_method_raises():
    with pytest.raises(ValueError, match="method"):
        OfflineProvider(OfflineConfig(method="bogus"), LOCATION)


def test_unknown_high_latitude_rule_raises():
    with pytest.raises(ValueError, match="high_latitude_rule"):
        OfflineProvider(OfflineConfig(high_latitude_rule="bogus"), LOCATION)
