from datetime import date, datetime, timezone

from adhan.models import PrayerSchedule
from adhan.times.base import TimeProvider
from tests.fakes import FakeTimeProvider


def test_fake_provider_satisfies_protocol():
    sched = PrayerSchedule(
        fajr=datetime(2026, 7, 18, 5, 0, tzinfo=timezone.utc),
        sunrise=datetime(2026, 7, 18, 6, 30, tzinfo=timezone.utc),
        dhuhr=datetime(2026, 7, 18, 13, 0, tzinfo=timezone.utc),
        asr=datetime(2026, 7, 18, 17, 0, tzinfo=timezone.utc),
        maghrib=datetime(2026, 7, 18, 20, 30, tzinfo=timezone.utc),
        isha=datetime(2026, 7, 18, 22, 0, tzinfo=timezone.utc),
    )
    provider: TimeProvider = FakeTimeProvider(sched)
    assert provider.get_schedule(date(2026, 7, 18)) is sched
