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


FIXED_NOW = _dt(11, 0)  # UTC, after fajr / before dhuhr


class _RaisingProvider:
    def get_schedule(self, day):
        raise RuntimeError("provider boom")


def _make(fired, backend, clock=None):
    return AdhanScheduler(
        provider=FakeTimeProvider(SCHED),
        adjuster=ScheduleAdjuster({}),
        on_prayer=lambda p: fired.append(p),
        backend=backend,
        misfire_grace_seconds=300,
        clock=clock,
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


def test_start_schedules_today_registers_cron_and_starts_backend():
    backend = FakeScheduler()
    _make([], backend, clock=lambda: FIXED_NOW).start()
    assert {j.id for j in backend.jobs} == {"prayer-dhuhr", "prayer-asr", "prayer-maghrib", "prayer-isha"}
    assert len(backend.cron_jobs) == 1
    assert backend.cron_jobs[0]["hour"] == 0 and backend.cron_jobs[0]["minute"] == 1
    assert backend.cron_jobs[0]["id"] == "daily-regen"
    assert backend.started is True


def test_regenerate_reschedules_and_reregisters_cron():
    backend = FakeScheduler()
    sched = _make([], backend, clock=lambda: FIXED_NOW)
    sched._register_daily_regen()          # a cron already exists
    sched._regenerate()
    assert {j.id for j in backend.jobs} == {"prayer-dhuhr", "prayer-asr", "prayer-maghrib", "prayer-isha"}
    assert any(c["id"] == "daily-regen" for c in backend.cron_jobs)


def test_regenerate_reregisters_cron_even_when_scheduling_fails():
    # Regression for the critical bug: a failing provider must NOT leave the
    # appliance with no cron (which would permanently stop regeneration).
    backend = FakeScheduler()
    sched = AdhanScheduler(
        provider=_RaisingProvider(),
        adjuster=ScheduleAdjuster({}),
        on_prayer=lambda p: None,
        backend=backend,
        clock=lambda: FIXED_NOW,
    )
    sched._regenerate()  # must not raise out of the callback
    assert any(c["id"] == "daily-regen" for c in backend.cron_jobs), "cron must survive a failed regeneration"


def test_on_regenerate_callback_receives_jobs():
    received = {}
    backend = FakeScheduler()
    sched = AdhanScheduler(
        provider=FakeTimeProvider(SCHED),
        adjuster=ScheduleAdjuster({}),
        on_prayer=lambda p: None,
        backend=backend,
        on_regenerate=lambda jobs: received.update(jobs),
    )
    sched.schedule_day(FIXED_NOW)
    assert set(received) == {Prayer.FAJR, Prayer.DHUHR, Prayer.ASR, Prayer.MAGHRIB, Prayer.ISHA}


def test_misfire_grace_forwarded_to_date_jobs():
    backend = FakeScheduler()
    _make([], backend).schedule_day(FIXED_NOW)
    assert backend.jobs and all(j.kwargs["misfire_grace_time"] == 300 for j in backend.jobs)
