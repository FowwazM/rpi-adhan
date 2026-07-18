from datetime import datetime, timezone

from adhan.models import (
    Prayer,
    PLAYABLE_PRAYERS,
    PrayerSchedule,
    MediaRef,
    PlayResult,
    HealthState,
    HealthStatus,
)


def _dt(h, m):
    return datetime(2026, 7, 18, h, m, tzinfo=timezone.utc)


def test_playable_prayers_excludes_sunrise():
    assert PLAYABLE_PRAYERS == [
        Prayer.FAJR,
        Prayer.DHUHR,
        Prayer.ASR,
        Prayer.MAGHRIB,
        Prayer.ISHA,
    ]


def test_prayer_schedule_get_by_prayer():
    sched = PrayerSchedule(
        fajr=_dt(5, 0), sunrise=_dt(6, 30), dhuhr=_dt(13, 0),
        asr=_dt(17, 0), maghrib=_dt(20, 30), isha=_dt(22, 0),
    )
    assert sched.get(Prayer.ASR) == _dt(17, 0)


def test_play_result_defaults():
    r = PlayResult(player="cast:Living", success=True)
    assert r.error is None and r.attempts == 1


def test_media_ref_and_health():
    m = MediaRef(file_path="/x/a.mp3", url="http://1.2.3.4:8127/a.mp3")
    assert m.url.endswith("a.mp3")
    h = HealthStatus(player="bt", state=HealthState.OK)
    assert h.state is HealthState.OK
