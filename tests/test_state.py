import json
import threading
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


def test_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "dir" / "state.json"
    StateStore(path, clock=lambda: _dt(11, 0))
    assert path.exists()


def test_no_leftover_tmp_file(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path, clock=lambda: _dt(11, 0))
    store.set_schedule({Prayer.DHUHR: _dt(13, 0)})
    store.record_result(Prayer.DHUHR, [PlayResult("a", True)])
    assert list(tmp_path.glob("*.tmp")) == []


def test_records_speaker_health(tmp_path):
    store = StateStore(tmp_path / "state.json", clock=lambda: _dt(13, 0))
    store.record_result(Prayer.DHUHR, [PlayResult("cast:Living", True), PlayResult("bluetooth:x", False, "boom")])
    health = json.loads((tmp_path / "state.json").read_text())["speaker_health"]
    assert health == {"cast:Living": "ok", "bluetooth:x": "unreachable"}


def test_next_prayer_advances_after_fire(tmp_path):
    clock_val = [_dt(11, 0)]
    store = StateStore(tmp_path / "state.json", clock=lambda: clock_val[0])
    store.set_schedule({Prayer.DHUHR: _dt(13, 0), Prayer.ASR: _dt(17, 0)})
    assert json.loads((tmp_path / "state.json").read_text())["next_prayer"]["name"] == "dhuhr"
    clock_val[0] = _dt(13, 30)  # dhuhr has now passed
    store.record_result(Prayer.DHUHR, [PlayResult("cast:x", True)])
    assert json.loads((tmp_path / "state.json").read_text())["next_prayer"]["name"] == "asr"


def test_concurrent_writes_are_safe(tmp_path):
    import threading

    path = tmp_path / "state.json"
    store = StateStore(path, clock=lambda: _dt(11, 0))
    errors = []

    def worker(i):
        try:
            for _ in range(50):
                store.set_schedule({Prayer.DHUHR: _dt(13, 0), Prayer.ASR: _dt(17, 0)})
                store.record_result(Prayer.ISHA, [PlayResult(f"p{i}", True)])
        except Exception as exc:  # e.g. "dictionary changed size during iteration"
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    json.loads(path.read_text())  # final file is valid JSON, not torn
