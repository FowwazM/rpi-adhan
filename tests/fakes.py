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


class FakeJob:
    def __init__(self, run_date, args, job_id, kwargs=None):
        self.run_date = run_date
        self.args = args
        self.id = job_id
        self.kwargs = kwargs or {}


class FakeScheduler:
    """Records add_job calls the way APScheduler would be driven."""

    def __init__(self):
        self.jobs: list[FakeJob] = []
        self.started = False
        self.cron_jobs: list[dict] = []

    def add_job(self, func, trigger, **kwargs):
        if trigger == "date":
            self.jobs.append(FakeJob(kwargs["run_date"], kwargs.get("args", []), kwargs.get("id"), kwargs))
        elif trigger == "cron":
            self.cron_jobs.append(kwargs)
        return FakeJob(kwargs.get("run_date"), kwargs.get("args", []), kwargs.get("id"), kwargs)

    def remove_all_jobs(self):
        self.jobs.clear()
        self.cron_jobs.clear()  # APScheduler clears ALL jobs, cron included

    def start(self):
        self.started = True
