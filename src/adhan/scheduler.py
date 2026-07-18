from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Callable, Protocol

from adhan.models import Prayer
from adhan.times.adjuster import ScheduleAdjuster
from adhan.times.base import TimeProvider

logger = logging.getLogger(__name__)


class SchedulerBackend(Protocol):
    def add_job(self, func: Callable, trigger: str, **kwargs): ...
    def remove_all_jobs(self) -> None: ...
    def start(self) -> None: ...


class AdhanScheduler:
    def __init__(
        self,
        provider: TimeProvider,
        adjuster: ScheduleAdjuster,
        on_prayer: Callable[[Prayer], None],
        backend: SchedulerBackend,
        misfire_grace_seconds: int = 300,
        on_regenerate: Callable[[dict[Prayer, datetime]], None] | None = None,
    ):
        self._provider = provider
        self._adjuster = adjuster
        self._on_prayer = on_prayer
        self._backend = backend
        self._grace = misfire_grace_seconds
        self._on_regenerate = on_regenerate

    def compute_jobs(self, day: date) -> dict[Prayer, datetime]:
        return self._adjuster.adjust(self._provider.get_schedule(day))

    def schedule_day(self, now: datetime) -> dict[Prayer, datetime]:
        jobs = self.compute_jobs(now.date())
        for prayer, when in jobs.items():
            if when <= now:
                continue
            self._backend.add_job(
                self._fire,
                "date",
                run_date=when,
                args=[prayer],
                id=f"prayer-{prayer.value}",
                misfire_grace_time=self._grace,
                replace_existing=True,
            )
        if self._on_regenerate is not None:
            self._on_regenerate(jobs)
        return jobs

    def _fire(self, prayer: Prayer) -> None:
        logger.info("firing adhan", extra={"prayer": prayer.value})
        self._on_prayer(prayer)

    def _regenerate(self) -> None:
        self._backend.remove_all_jobs()
        self.schedule_day(datetime.now().astimezone())
        # re-register the daily regeneration cron (removed by remove_all_jobs)
        self._register_daily_regen()

    def _register_daily_regen(self) -> None:
        self._backend.add_job(
            self._regenerate, "cron", hour=0, minute=1, id="daily-regen", replace_existing=True
        )

    def start(self) -> None:
        self.schedule_day(datetime.now().astimezone())
        self._register_daily_regen()
        self._backend.start()
