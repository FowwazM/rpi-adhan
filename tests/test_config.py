import textwrap

import pytest

from adhan.config import load_config, Config, Madhab, FajrMode


VALID = textwrap.dedent(
    """
    version: 1
    location:
      latitude: 29.7007851
      longitude: -95.8028693
      timezone: America/Chicago
    prayer_times:
      source: offline
      offline:
        method: north_america
        madhab: hanafi
        high_latitude_rule: middle_of_the_night
      prayers:
        fajr:
          enabled: true
          mode: before_sunrise
          before_sunrise_minutes: 30
        asr:
          enabled: true
          offset_minutes: 0
    audio:
      default_file: adhan.mp3
      per_prayer_files:
        fajr: adhan_fajr.mp3
      default_volume: 0.6
      per_prayer_volume:
        fajr: 0.4
    outputs:
      cast:
        - name: "Downstairs group"
      bluetooth:
        adapter: auto
        keepalive: true
        speakers:
          - {name: "JBL Charge 5", mac: "AA:BB:CC:DD:EE:FF"}
    network:
      http_host: auto
      http_port: 8127
    """
)


def _write(tmp_path, text):
    p = tmp_path / "config.yaml"
    p.write_text(text)
    return p


def test_load_valid_config(tmp_path):
    cfg = load_config(_write(tmp_path, VALID))
    assert isinstance(cfg, Config)
    assert cfg.location.timezone == "America/Chicago"
    assert cfg.prayer_times.offline.madhab is Madhab.HANAFI
    assert cfg.prayer_times.prayers["fajr"].mode is FajrMode.BEFORE_SUNRISE
    assert cfg.audio.per_prayer_volume["fajr"] == 0.4
    assert cfg.outputs.bluetooth.speakers[0].mac == "AA:BB:CC:DD:EE:FF"
    assert cfg.reliability.misfire_grace_seconds == 300


def test_invalid_timezone_rejected(tmp_path):
    bad = VALID.replace("America/Chicago", "Mars/Olympus")
    with pytest.raises(ValueError, match="timezone"):
        load_config(_write(tmp_path, bad))


def test_volume_out_of_range_rejected(tmp_path):
    bad = VALID.replace("default_volume: 0.6", "default_volume: 2.0")
    with pytest.raises(ValueError):
        load_config(_write(tmp_path, bad))


def test_latitude_out_of_range_rejected(tmp_path):
    bad = VALID.replace("latitude: 29.7007851", "latitude: 200.0")
    with pytest.raises(ValueError):
        load_config(_write(tmp_path, bad))
