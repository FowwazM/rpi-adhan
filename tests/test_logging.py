import json
import logging

from adhan.logging_setup import JsonFormatter, configure_logging


def test_formatter_emits_json_with_extra():
    rec = logging.LogRecord("adhan.test", logging.INFO, "f", 1, "played", None, None)
    rec.prayer = "dhuhr"
    out = json.loads(JsonFormatter().format(rec))
    assert out["level"] == "INFO"
    assert out["message"] == "played"
    assert out["prayer"] == "dhuhr"


def test_configure_logging_sets_level(capsys):
    configure_logging(level="INFO", as_json=True)
    logging.getLogger("adhan.x").info("hello", extra={"k": "v"})
    line = capsys.readouterr().err.strip().splitlines()[-1]
    assert json.loads(line)["message"] == "hello"


def test_extra_cannot_override_core_fields():
    rec = logging.LogRecord("adhan.test", logging.WARNING, "f", 1, "msg", None, None)
    rec.level = "SPOOFED"
    rec.logger = "spoofed"
    out = json.loads(JsonFormatter().format(rec))
    assert out["level"] == "WARNING"       # real severity wins
    assert out["logger"] == "adhan.test"   # real logger name wins
