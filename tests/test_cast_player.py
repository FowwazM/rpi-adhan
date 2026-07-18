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
