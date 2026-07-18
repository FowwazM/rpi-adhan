from datetime import date, datetime, timezone

from freezegun import freeze_time

from adhan.config import PrayerConfig
from adhan.models import Prayer, PrayerSchedule
from adhan.scheduler import AdhanScheduler
from adhan.times.adjuster import ScheduleAdjuster
from tests.fakes import FakeScheduler, FakeTimeProvider


def _dt(h, m):
    return datetime(2026, 7, 18, h, m, tzinfo=timezone.utc)


SCHED = PrayerSchedule(
    fajr=_dt(5, 0), sunrise=_dt(6, 30), dhuhr=_dt(13, 0),
    asr=_dt(17, 0), maghrib=_dt(20, 30), isha=_dt(22, 0),
)


def _make(fired, backend):
    return AdhanScheduler(
        provider=FakeTimeProvider(SCHED),
        adjuster=ScheduleAdjuster({}),
        on_prayer=lambda p: fired.append(p),
        backend=backend,
        misfire_grace_seconds=300,
    )


@freeze_time("2026-07-18 11:00:00")  # UTC; before dhuhr, after fajr
def test_schedule_day_only_future_prayers():
    backend = FakeScheduler()
    _make([], backend).schedule_day(datetime.now(timezone.utc))
    ids = {j.id for j in backend.jobs}
    # fajr (05:00) is in the past and must be skipped; dhuhr..isha scheduled
    assert ids == {"prayer-dhuhr", "prayer-asr", "prayer-maghrib", "prayer-isha"}


@freeze_time("2026-07-18 11:00:00")
def test_scheduled_job_fires_callback():
    fired = []
    backend = FakeScheduler()
    sched = _make(fired, backend)
    sched.schedule_day(datetime.now(timezone.utc))
    job = next(j for j in backend.jobs if j.id == "prayer-dhuhr")
    sched._fire(*job.args)
    assert fired == [Prayer.DHUHR]


def test_compute_jobs_returns_all_enabled():
    jobs = _make([], FakeScheduler()).compute_jobs(date(2026, 7, 18))
    assert set(jobs) == {Prayer.FAJR, Prayer.DHUHR, Prayer.ASR, Prayer.MAGHRIB, Prayer.ISHA}
