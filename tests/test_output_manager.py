from adhan.models import MediaRef
from adhan.players.manager import OutputManager
from tests.fakes import FakePlayer

MEDIA = MediaRef("/x/a.mp3", "http://h/a.mp3")


def test_plays_all_players_and_aggregates():
    a, b = FakePlayer("a"), FakePlayer("b")
    results = OutputManager([a, b]).play_all(MEDIA, 0.5)
    by_name = {r.player: r.success for r in results}
    assert by_name == {"a": True, "b": True}
    assert a.calls and b.calls


def test_one_failure_does_not_block_others():
    good, bad = FakePlayer("good"), FakePlayer("bad", fail_times=5)
    results = OutputManager([good, bad]).play_all(MEDIA, 0.5)
    by_name = {r.player: r.success for r in results}
    assert by_name == {"good": True, "bad": False}


def test_empty_players_returns_empty():
    assert OutputManager([]).play_all(MEDIA, 0.5) == []
