import json
from datetime import datetime, timezone

from adhan.cli import build_parser, cmd_status, main


def test_parser_run_defaults():
    args = build_parser().parse_args(["run"])
    assert args.command == "run"
    assert args.config.endswith("config.yaml")


def test_parser_test_play_requires_prayer():
    args = build_parser().parse_args(["test-play", "dhuhr"])
    assert args.command == "test-play" and args.prayer == "dhuhr"


def test_cmd_status_prints_state(tmp_path, capsys):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"next_prayer": {"name": "asr", "time": "2026-07-18T17:00:00+00:00"}}))
    rc = cmd_status(str(state))
    assert rc == 0
    assert "asr" in capsys.readouterr().out


def test_cmd_status_missing_file_returns_1(tmp_path, capsys):
    rc = cmd_status(str(tmp_path / "nope.json"))
    assert rc == 1
    assert "No state file" in capsys.readouterr().out


def test_main_dispatches_status(tmp_path, capsys):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"next_prayer": {"name": "isha"}}))
    rc = main(["--state", str(state), "status"])
    assert rc == 0
    assert "isha" in capsys.readouterr().out
