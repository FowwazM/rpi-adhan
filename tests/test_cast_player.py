from adhan.models import HealthState, MediaRef
from adhan.players.cast import CastPlayer
from tests.fakes import FakeCast

MEDIA = MediaRef("/x/a.mp3", "http://10.0.0.5:8127/a.mp3")


def test_play_sets_volume_plays_and_restores():
    fake = FakeCast(volume=0.3, states=("PLAYING", "PLAYING", "IDLE"))
    player = CastPlayer("Living", cast_factory=lambda name: fake, poll_interval=0)
    result = player.play(MEDIA, 0.7)
    assert result.success
    assert fake.media_controller.played == ("http://10.0.0.5:8127/a.mp3", "audio/mpeg")
    assert fake.set_volumes[0] == 0.7
    assert fake.set_volumes[-1] == 0.3


def test_health_ok_when_factory_succeeds():
    player = CastPlayer("Living", cast_factory=lambda name: FakeCast(), poll_interval=0)
    assert player.health_check().state is HealthState.OK


def test_health_check_disconnects_the_cast():
    fake = FakeCast()
    player = CastPlayer("Living", cast_factory=lambda name: fake, poll_interval=0)
    player.health_check()
    assert fake.disconnected is True  # no leaked connection per health check


def test_play_disconnects_the_cast():
    fake = FakeCast(volume=0.3, states=("PLAYING", "IDLE"))
    player = CastPlayer("Living", cast_factory=lambda name: fake, poll_interval=0)
    assert player.play(MEDIA, 0.7).success
    assert fake.disconnected is True  # connection released after playback


def test_health_unreachable_when_factory_raises():
    def boom(name):
        raise OSError("not found")

    player = CastPlayer("Living", cast_factory=boom, poll_interval=0)
    assert player.health_check().state is HealthState.UNREACHABLE


def test_play_failure_returns_error():
    def boom(name):
        raise OSError("device offline")

    player = CastPlayer("Living", cast_factory=boom, poll_interval=0)
    r = player.play(MEDIA, 0.5)
    assert not r.success and "device offline" in r.error


def test_play_restores_volume_on_playback_error():
    class _BoomMC:
        def play_media(self, url, content_type):
            raise RuntimeError("cast dropped")

        def block_until_active(self, timeout=None):
            pass

        @property
        def status(self):
            s = type("S", (), {})()
            s.player_state = "IDLE"
            return s

    fake = FakeCast(volume=0.3)
    fake.media_controller = _BoomMC()
    player = CastPlayer("Living", cast_factory=lambda name: fake, poll_interval=0)
    r = player.play(MEDIA, 0.7)
    assert not r.success and "cast dropped" in r.error
    assert fake.set_volumes[-1] == 0.3  # volume restored despite the error


def test_wait_for_finish_polls_until_idle():
    fake = FakeCast(volume=0.3, states=("PLAYING", "PLAYING", "IDLE"))
    sleeps = []
    player = CastPlayer("Living", cast_factory=lambda name: fake, poll_interval=1, sleep=sleeps.append)
    r = player.play(MEDIA, 0.5)
    assert r.success
    assert sleeps == [1, 1]  # polled through 2 PLAYING states, then IDLE
