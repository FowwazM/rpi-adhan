from adhan.models import MediaRef
from adhan.players.base import Player
from tests.fakes import FakePlayer


def test_fake_player_satisfies_protocol():
    p: Player = FakePlayer("cast:Living")
    r = p.play(MediaRef("/x/a.mp3", "http://h/a.mp3"), 0.5)
    assert r.success and p.name == "cast:Living"
