from datetime import datetime, timezone

from adhan.config import AudioConfig
from adhan.media import MediaManager
from adhan.models import Prayer
from adhan.orchestrator import Orchestrator
from adhan.players.manager import OutputManager
from adhan.state import StateStore
from tests.fakes import FakePlayer


def _media_manager(tmp_path):
    (tmp_path / "adhan.mp3").write_bytes(b"x")
    audio = AudioConfig(default_file="adhan.mp3", default_volume=0.6)
    return MediaManager(audio, tmp_path, "http://10.0.0.5:8127")


def test_handle_prayer_plays_and_records(tmp_path):
    players = [FakePlayer("a"), FakePlayer("b")]
    state = StateStore(tmp_path / "state.json", clock=lambda: datetime(2026, 7, 18, 13, 0, tzinfo=timezone.utc))
    orch = Orchestrator(_media_manager(tmp_path), OutputManager(players), state)

    orch.handle_prayer(Prayer.DHUHR)

    assert players[0].calls and players[0].calls[0][1] == 0.6  # volume passed through
    import json

    data = json.loads((tmp_path / "state.json").read_text())
    assert set(data["last_results"]["dhuhr"]["outputs"]) == {"a", "b"}


def test_handle_prayer_missing_file_is_recorded_not_raised(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    audio = AudioConfig(default_file="adhan.mp3", default_volume=0.6)
    mm = MediaManager(audio, empty, "http://10.0.0.5:8127")
    state = StateStore(tmp_path / "state.json", clock=lambda: datetime(2026, 7, 18, 13, 0, tzinfo=timezone.utc))
    orch = Orchestrator(mm, OutputManager([FakePlayer("a")]), state)

    orch.handle_prayer(Prayer.DHUHR)  # must not raise

    import json

    outputs = json.loads((tmp_path / "state.json").read_text())["last_results"]["dhuhr"]["outputs"]
    assert outputs["media"]["success"] is False
