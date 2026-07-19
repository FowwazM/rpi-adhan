from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_CONFIG = "/etc/adhan/config.yaml"
DEFAULT_MEDIA = "/etc/adhan/media"
DEFAULT_STATE = "/var/lib/adhan/state.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="adhan", description="Raspberry Pi adhan appliance")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--media", default=DEFAULT_MEDIA)
    parser.add_argument("--state", default=DEFAULT_STATE)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="Run the adhan service")
    sub.add_parser("status", help="Print current state.json")
    tp = sub.add_parser("test-play", help="Play a prayer's adhan now")
    tp.add_argument("prayer", choices=["fajr", "dhuhr", "asr", "maghrib", "isha"])
    return parser


def cmd_status(state_path: str) -> int:
    p = Path(state_path)
    if not p.exists():
        print(f"No state file at {state_path}")
        return 1
    print(json.dumps(json.loads(p.read_text()), indent=2))
    return 0


def cmd_run(args) -> int:
    from adhan.app import App
    from adhan.config import load_config

    config = load_config(args.config)
    App(config, Path(args.media), Path(args.state)).run()
    return 0


def cmd_test_play(args) -> int:
    import tempfile

    from adhan.app import App
    from adhan.config import load_config
    from adhan.models import Prayer

    config = load_config(args.config)
    # Throwaway state dir so a manual test-play never overwrites the live state.json.
    with tempfile.TemporaryDirectory() as tmp:
        app = App(config, Path(args.media), Path(tmp) / "state.json", http_port=0)
        app.build()
        app.trigger(Prayer(args.prayer))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "status":
        return cmd_status(args.state)
    if args.command == "test-play":
        return cmd_test_play(args)
    return 2  # pragma: no cover  (unreachable: subparsers are required=True)
