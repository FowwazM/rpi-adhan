from datetime import date
from datetime import time as _time
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


def test_matches_aladhan_reference_within_tolerance():
    # Golden reference from api.aladhan.com (method=2 ISNA, school=0 Shafi) for
    # 2026-07-18 at Houston, America/Chicago. Cross-implementation drift (adhanpy
    # vs aladhan) of the SAME method is a few minutes; a wrong method mapping would
    # shift the angle-based Fajr/Isha by 10+ minutes, which this catches.
    reference = {
        "fajr": _time(5, 19),
        "dhuhr": _time(13, 30),
        "asr": _time(17, 5),
        "maghrib": _time(20, 24),
        "isha": _time(21, 39),
    }
    sched = OfflineProvider(
        OfflineConfig(method="north_america", madhab=Madhab.SHAFI), LOCATION
    ).get_schedule(date(2026, 7, 18))
    tz = ZoneInfo("America/Chicago")
    got = {"fajr": sched.fajr, "dhuhr": sched.dhuhr, "asr": sched.asr, "maghrib": sched.maghrib, "isha": sched.isha}
    for name, ref in reference.items():
        local = got[name].astimezone(tz)
        delta = abs((local.hour * 60 + local.minute) - (ref.hour * 60 + ref.minute))
        assert delta <= 5, f"{name}: adhanpy {local.time()} vs aladhan {ref} differ by {delta} min"
