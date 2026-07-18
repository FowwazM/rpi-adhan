import json
from datetime import datetime, timezone

from adhan.models import Prayer, PlayResult
from adhan.state import StateStore


def _dt(h, m):
    return datetime(2026, 7, 18, h, m, tzinfo=timezone.utc)


def test_records_schedule_and_next(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path, clock=lambda: _dt(11, 0))
    store.set_schedule({Prayer.DHUHR: _dt(13, 0), Prayer.ASR: _dt(17, 0)})
    data = json.loads(path.read_text())
    assert data["next_prayer"]["name"] == "dhuhr"
    assert data["today_schedule"]["asr"] == _dt(17, 0).isoformat()


def test_records_results(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path, clock=lambda: _dt(13, 0))
    store.record_result(Prayer.DHUHR, [PlayResult("cast:Living", True), PlayResult("bluetooth:x", False, "boom")])
    data = json.loads(path.read_text())
    entry = data["last_results"]["dhuhr"]
    assert entry["outputs"]["cast:Living"]["success"] is True
    assert entry["outputs"]["bluetooth:x"]["error"] == "boom"


def test_next_prayer_none_when_all_past(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path, clock=lambda: _dt(23, 0))
    store.set_schedule({Prayer.DHUHR: _dt(13, 0)})
    assert json.loads(path.read_text())["next_prayer"] is None
