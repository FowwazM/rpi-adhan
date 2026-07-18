from adhan.models import HealthState, MediaRef
from adhan.players.reliable import ReliablePlayer
from tests.fakes import FakePlayer

MEDIA = MediaRef("/x/a.mp3", "http://h/a.mp3")


def _wrap(inner, attempts=2):
    sleeps = []
    rp = ReliablePlayer(inner, attempts=attempts, backoff_seconds=5, sleep=sleeps.append)
    return rp, sleeps


def test_succeeds_first_try():
    rp, sleeps = _wrap(FakePlayer("p"))
    r = rp.play(MEDIA, 0.5)
    assert r.success and r.attempts == 1 and sleeps == []


def test_retries_then_succeeds():
    rp, sleeps = _wrap(FakePlayer("p", fail_times=1), attempts=2)
    r = rp.play(MEDIA, 0.5)
    assert r.success and r.attempts == 2 and sleeps == [5]


def test_all_attempts_fail():
    rp, sleeps = _wrap(FakePlayer("p", fail_times=5), attempts=2)
    r = rp.play(MEDIA, 0.5)
    assert not r.success and r.attempts == 2 and r.error == "simulated failure"


def test_exception_is_caught_as_failure():
    rp, _ = _wrap(FakePlayer("p", fail_times=5, raises=True), attempts=1)
    r = rp.play(MEDIA, 0.5)
    assert not r.success and "boom" in r.error


def test_name_delegates():
    rp, _ = _wrap(FakePlayer("cast:Kitchen"))
    assert rp.name == "cast:Kitchen"


def test_health_check_delegates():
    from adhan.models import HealthState

    inner = FakePlayer("p", health=HealthState.UNREACHABLE)
    rp, _ = _wrap(inner)
    assert rp.health_check().state is HealthState.UNREACHABLE


def test_backoff_escalates_across_retries():
    rp, sleeps = _wrap(FakePlayer("p", fail_times=2), attempts=3)
    r = rp.play(MEDIA, 0.5)
    assert r.success and r.attempts == 3 and sleeps == [5, 10]
