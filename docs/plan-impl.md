# Raspberry Pi Adhan Appliance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-Raspberry-Pi Python appliance that plays the adhan at the five daily prayer times to Google Nest (network cast) and Bluetooth speakers (including Echos used as Bluetooth speakers), configured entirely by one `config.yaml`.

**Architecture:** A supervised Python service. A `TimeProvider` computes the day's prayer schedule offline (`adhanpy`); a `ScheduleAdjuster` applies per-prayer offsets and the Fajr "before sunrise" mode; an APScheduler-based `AdhanScheduler` fires one-shot jobs; an `Orchestrator` resolves the adhan file + volume and fans the play request out through an `OutputManager` to `Player` implementations (`CastPlayer`, `BluetoothPlayer`), each wrapped by a `ReliablePlayer` (health-check + retry). Structured JSON logs and a `state.json` heartbeat provide observability. Bluetooth pairing, keep-alive, and reconnect are handled by systemd-level scripts outside the Python app. Hardware is isolated behind interfaces so the core is fully unit-testable without a Pi.

**Tech Stack:** Python 3.11, pydantic v2, PyYAML, adhanpy, APScheduler, pychromecast, PipeWire/BlueZ (system), pytest + pytest-cov + freezegun, systemd.

**Reference:** The design spec is `docs/plan-spec.md`. Read it before starting. Phase 2 items (web UI, Mawaqit source, golden image, MQTT) are explicitly **out of scope** for this plan.

---

## File Structure

```
rpi-adhan-v2/
├── docs/
│   ├── plan-spec.md                 # design spec (exists)
│   └── plan-impl.md                 # this plan
├── pyproject.toml                   # package + deps + pytest/coverage config
├── .gitignore
├── README.md
├── config/
│   └── config.example.yaml          # annotated template (the per-client delta)
├── media/
│   └── .gitkeep                     # adhan MP3s dropped here at deploy time
├── systemd/
│   ├── adhan.service                # main service
│   ├── adhan-bt-keepalive.service   # silent keep-alive so BT speakers don't sleep
│   └── adhan-bt-watchdog.service    # reconnect watchdog
├── scripts/
│   ├── install.sh                   # one-shot installer
│   ├── bt-pair.sh                   # interactive pairing wizard
│   ├── bt-keepalive.sh              # keep-alive loop
│   └── bt-watchdog.sh               # reconnect loop
├── src/adhan/
│   ├── __init__.py
│   ├── __main__.py                  # `python -m adhan`
│   ├── models.py                    # Prayer, PrayerSchedule, MediaRef, PlayResult, HealthStatus
│   ├── config.py                    # pydantic config models + load_config
│   ├── netutil.py                   # LAN IP detection
│   ├── times/
│   │   ├── __init__.py
│   │   ├── base.py                  # TimeProvider protocol
│   │   ├── offline.py               # OfflineProvider (adhanpy)
│   │   └── adjuster.py              # ScheduleAdjuster
│   ├── scheduler.py                 # AdhanScheduler
│   ├── media.py                     # MediaManager + MediaHTTPServer
│   ├── players/
│   │   ├── __init__.py
│   │   ├── base.py                  # Player protocol
│   │   ├── reliable.py              # ReliablePlayer (health + retry)
│   │   ├── manager.py               # OutputManager (fan-out)
│   │   ├── cast.py                  # CastPlayer (pychromecast)
│   │   └── bluetooth.py             # BluetoothPlayer (PipeWire)
│   ├── state.py                     # StateStore -> state.json
│   ├── logging_setup.py             # JSON logging
│   ├── orchestrator.py              # Orchestrator
│   ├── app.py                       # build_app() wiring + App.run()
│   └── cli.py                       # argparse entry point
└── tests/
    ├── conftest.py
    ├── fakes.py                     # FakeTimeProvider, FakePlayer, FakeScheduler, FakeCast, RecordingRunner
    ├── test_config.py
    ├── test_offline_provider.py
    ├── test_adjuster.py
    ├── test_scheduler.py
    ├── test_media.py
    ├── test_reliable.py
    ├── test_output_manager.py
    ├── test_cast_player.py
    ├── test_bluetooth_player.py
    ├── test_state.py
    ├── test_logging.py
    ├── test_orchestrator.py
    └── test_cli.py
```

**Design boundaries:** `times/` owns "when", `players/` owns "how it plays", `orchestrator.py` connects them, `app.py` wires concrete instances from config. Every hardware library (adhanpy, pychromecast, subprocess/PipeWire) is reached through a small seam that tests replace with a fake.

---

## Milestone 0 — Scaffolding

### Task 0.1: Project skeleton, dependencies, test harness

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/adhan/__init__.py`, `tests/__init__.py`, `tests/conftest.py`, `tests/test_smoke.py`

- [ ] **Step 1: Write `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/
.pytest_cache/
.coverage
htmlcov/
dist/
build/
state.json
*.log
.DS_Store
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "adhan"
version = "0.1.0"
description = "Raspberry Pi adhan appliance"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.5",
    "PyYAML>=6.0",
    "adhanpy>=1.0.0",
    "APScheduler>=3.10",
    "PyChromecast>=14.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=5.0", "freezegun>=1.4"]

[project.scripts]
adhan = "adhan.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[tool.coverage.run]
source = ["adhan"]
omit = ["src/adhan/__main__.py", "src/adhan/players/cast.py", "src/adhan/players/bluetooth.py", "src/adhan/app.py"]

[tool.coverage.report]
fail_under = 95
show_missing = true
```

Note: `cast.py`, `bluetooth.py`, and `app.py` are omitted from the coverage gate because they are thin hardware/wiring seams validated by the smoke checklist (Task 9.1), not unit coverage. Their injectable logic is still tested.

- [ ] **Step 3: Write `src/adhan/__init__.py`**

```python
"""Raspberry Pi adhan appliance."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Write `tests/__init__.py` (empty) and `tests/conftest.py`**

```python
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
```

- [ ] **Step 5: Write `tests/test_smoke.py`**

```python
def test_package_imports():
    import adhan

    assert adhan.__version__ == "0.1.0"
```

- [ ] **Step 6: Create venv, install, run**

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest tests/test_smoke.py -v
```
Expected: 1 passed.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: scaffold adhan package and test harness"
```

---

## Milestone 1 — Domain models & configuration

### Task 1.1: Core domain models

**Files:**
- Create: `src/adhan/models.py`, `tests/test_models.py`

- [ ] **Step 1: Write the failing test — `tests/test_models.py`**

```python
from datetime import datetime, timezone

from adhan.models import (
    Prayer,
    PLAYABLE_PRAYERS,
    PrayerSchedule,
    MediaRef,
    PlayResult,
    HealthState,
    HealthStatus,
)


def _dt(h, m):
    return datetime(2026, 7, 18, h, m, tzinfo=timezone.utc)


def test_playable_prayers_excludes_sunrise():
    assert PLAYABLE_PRAYERS == [
        Prayer.FAJR,
        Prayer.DHUHR,
        Prayer.ASR,
        Prayer.MAGHRIB,
        Prayer.ISHA,
    ]


def test_prayer_schedule_get_by_prayer():
    sched = PrayerSchedule(
        fajr=_dt(5, 0), sunrise=_dt(6, 30), dhuhr=_dt(13, 0),
        asr=_dt(17, 0), maghrib=_dt(20, 30), isha=_dt(22, 0),
    )
    assert sched.get(Prayer.ASR) == _dt(17, 0)


def test_play_result_defaults():
    r = PlayResult(player="cast:Living", success=True)
    assert r.error is None and r.attempts == 1


def test_media_ref_and_health():
    m = MediaRef(file_path="/x/a.mp3", url="http://1.2.3.4:8127/a.mp3")
    assert m.url.endswith("a.mp3")
    h = HealthStatus(player="bt", state=HealthState.OK)
    assert h.state is HealthState.OK
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_models.py -v` — Expected: FAIL (`ModuleNotFoundError: adhan.models`).

- [ ] **Step 3: Write `src/adhan/models.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Prayer(str, Enum):
    FAJR = "fajr"
    DHUHR = "dhuhr"
    ASR = "asr"
    MAGHRIB = "maghrib"
    ISHA = "isha"


# Sunrise is computed but never played; keep it out of the playable set.
PLAYABLE_PRAYERS: list[Prayer] = [
    Prayer.FAJR,
    Prayer.DHUHR,
    Prayer.ASR,
    Prayer.MAGHRIB,
    Prayer.ISHA,
]


@dataclass(frozen=True)
class PrayerSchedule:
    fajr: datetime
    sunrise: datetime
    dhuhr: datetime
    asr: datetime
    maghrib: datetime
    isha: datetime

    def get(self, prayer: Prayer) -> datetime:
        return getattr(self, prayer.value)


@dataclass(frozen=True)
class MediaRef:
    file_path: str  # absolute path on disk (for Bluetooth/local playback)
    url: str        # http URL served to Cast devices


@dataclass(frozen=True)
class PlayResult:
    player: str
    success: bool
    error: str | None = None
    attempts: int = 1


class HealthState(str, Enum):
    OK = "ok"
    UNREACHABLE = "unreachable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class HealthStatus:
    player: str
    state: HealthState
    detail: str | None = None
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_models.py -v` — Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add core domain models"
```

### Task 1.2: Configuration models and loader

**Files:**
- Create: `src/adhan/config.py`, `tests/test_config.py`, `config/config.example.yaml`

- [ ] **Step 1: Write the failing test — `tests/test_config.py`**

```python
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
    # defaults fill in
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_config.py -v` — Expected: FAIL (`ModuleNotFoundError: adhan.config`).

- [ ] **Step 3: Write `src/adhan/config.py`**

```python
from __future__ import annotations

from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Madhab(str, Enum):
    SHAFI = "shafi"
    HANAFI = "hanafi"


class FajrMode(str, Enum):
    CALCULATED = "calculated"
    BEFORE_SUNRISE = "before_sunrise"


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LocationConfig(_Base):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str

    @field_validator("timezone")
    @classmethod
    def _tz_exists(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError, OSError):
            raise ValueError(f"Unknown timezone: {v}")
        return v


class OfflineConfig(_Base):
    method: str = "north_america"
    madhab: Madhab = Madhab.SHAFI
    high_latitude_rule: str = "middle_of_the_night"


class PrayerConfig(_Base):
    enabled: bool = True
    offset_minutes: int = 0
    mode: FajrMode = FajrMode.CALCULATED  # only meaningful for fajr
    before_sunrise_minutes: int = 30


class PrayerTimesConfig(_Base):
    source: str = "offline"
    offline: OfflineConfig = OfflineConfig()
    prayers: dict[str, PrayerConfig] = Field(default_factory=dict)


class AudioConfig(_Base):
    default_file: str
    per_prayer_files: dict[str, str] = Field(default_factory=dict)
    default_volume: float = Field(0.6, ge=0.0, le=1.0)
    per_prayer_volume: dict[str, float] = Field(default_factory=dict)


class CastOutput(_Base):
    name: str


class BluetoothSpeaker(_Base):
    name: str
    mac: str


class BluetoothConfig(_Base):
    adapter: str = "auto"
    keepalive: bool = True
    speakers: list[BluetoothSpeaker] = Field(default_factory=list)


class OutputsConfig(_Base):
    cast: list[CastOutput] = Field(default_factory=list)
    bluetooth: BluetoothConfig = BluetoothConfig()


class NetworkConfig(_Base):
    http_host: str = "auto"
    http_port: int = 8127


class ReliabilityConfig(_Base):
    retry_attempts: int = Field(2, ge=1)
    retry_backoff_seconds: float = Field(5.0, ge=0.0)
    misfire_grace_seconds: int = Field(300, ge=0)


class LoggingConfig(_Base):
    level: str = "INFO"
    json: bool = True


class Config(_Base):
    version: int
    location: LocationConfig
    prayer_times: PrayerTimesConfig
    audio: AudioConfig
    outputs: OutputsConfig
    network: NetworkConfig = NetworkConfig()
    reliability: ReliabilityConfig = ReliabilityConfig()
    logging: LoggingConfig = LoggingConfig()


def load_config(path: str | Path) -> Config:
    data = yaml.safe_load(Path(path).read_text())
    return Config.model_validate(data)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_config.py -v` — Expected: PASS (4 passed).

- [ ] **Step 5: Write `config/config.example.yaml`** (the annotated deploy template)

```yaml
version: 1

location:
  latitude: 29.7007851
  longitude: -95.8028693
  timezone: America/Chicago        # IANA tz; drives DST automatically

prayer_times:
  source: offline                  # offline (Phase 2: mawaqit)
  offline:
    method: north_america          # ISNA; see adhanpy CalculationMethod names
    madhab: hanafi                 # shafi | hanafi (affects Asr)
    high_latitude_rule: middle_of_the_night
  prayers:
    fajr:
      enabled: true
      mode: before_sunrise         # calculated | before_sunrise
      before_sunrise_minutes: 30
      offset_minutes: 0
    dhuhr:   {enabled: true, offset_minutes: 0}
    asr:     {enabled: true, offset_minutes: 0}
    maghrib: {enabled: true, offset_minutes: 0}
    isha:    {enabled: true, offset_minutes: 0}

audio:
  default_file: adhan.mp3          # relative to the media directory
  per_prayer_files:
    fajr: adhan_fajr.mp3
  default_volume: 0.6
  per_prayer_volume:
    fajr: 0.4

outputs:
  cast:
    - name: "Downstairs group"     # Google Home speaker-group OR device name
  bluetooth:
    adapter: auto                  # auto | hci0 | hci1 ...
    keepalive: true
    speakers:
      - {name: "JBL Charge 5", mac: "AA:BB:CC:DD:EE:FF"}
      - {name: "Echo Dot Bedroom", mac: "11:22:33:44:55:66"}

network:
  http_host: auto                  # Pi LAN IP (Chromecast needs an IP, not .local)
  http_port: 8127

reliability:
  retry_attempts: 2
  retry_backoff_seconds: 5
  misfire_grace_seconds: 300

logging:
  level: INFO
  json: true
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add config models, loader, and example config"
```

---

## Milestone 2 — Prayer times

### Task 2.1: TimeProvider protocol + FakeTimeProvider

**Files:**
- Create: `src/adhan/times/__init__.py` (empty), `src/adhan/times/base.py`, `tests/fakes.py`, `tests/test_times_base.py`

- [ ] **Step 1: Write the failing test — `tests/test_times_base.py`**

```python
from datetime import date, datetime, timezone

from adhan.models import PrayerSchedule
from adhan.times.base import TimeProvider
from tests.fakes import FakeTimeProvider


def test_fake_provider_satisfies_protocol():
    sched = PrayerSchedule(
        fajr=datetime(2026, 7, 18, 5, 0, tzinfo=timezone.utc),
        sunrise=datetime(2026, 7, 18, 6, 30, tzinfo=timezone.utc),
        dhuhr=datetime(2026, 7, 18, 13, 0, tzinfo=timezone.utc),
        asr=datetime(2026, 7, 18, 17, 0, tzinfo=timezone.utc),
        maghrib=datetime(2026, 7, 18, 20, 30, tzinfo=timezone.utc),
        isha=datetime(2026, 7, 18, 22, 0, tzinfo=timezone.utc),
    )
    provider: TimeProvider = FakeTimeProvider(sched)
    assert provider.get_schedule(date(2026, 7, 18)) is sched
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_times_base.py -v` — Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `src/adhan/times/__init__.py` (empty) and `src/adhan/times/base.py`**

```python
from __future__ import annotations

from datetime import date
from typing import Protocol

from adhan.models import PrayerSchedule


class TimeProvider(Protocol):
    def get_schedule(self, day: date) -> PrayerSchedule: ...
```

- [ ] **Step 4: Write `tests/fakes.py`** (seed with FakeTimeProvider; extended in later tasks)

```python
from __future__ import annotations

from datetime import date

from adhan.models import PrayerSchedule


class FakeTimeProvider:
    def __init__(self, schedule: PrayerSchedule):
        self._schedule = schedule
        self.calls: list[date] = []

    def get_schedule(self, day: date) -> PrayerSchedule:
        self.calls.append(day)
        return self._schedule
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_times_base.py -v` — Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add TimeProvider protocol and fake"
```

### Task 2.2: OfflineProvider (adhanpy)

**Files:**
- Create: `src/adhan/times/offline.py`, `tests/test_offline_provider.py`

- [ ] **Step 1: Write the failing test — `tests/test_offline_provider.py`**

The test asserts robust structural properties (order, tz-awareness, correct date) rather than brittle exact strings. After the first green run, record a golden value cross-checked against aladhan.com for this location (see the note in the test).

```python
from datetime import date
from zoneinfo import ZoneInfo

from adhan.config import LocationConfig, OfflineConfig, Madhab
from adhan.times.offline import OfflineProvider


LOCATION = LocationConfig(latitude=29.7007851, longitude=-95.8028693, timezone="America/Chicago")


def test_schedule_is_ordered_and_localized():
    provider = OfflineProvider(OfflineConfig(method="north_america", madhab=Madhab.SHAFI), LOCATION)
    sched = provider.get_schedule(date(2026, 7, 18))

    order = [sched.fajr, sched.sunrise, sched.dhuhr, sched.asr, sched.maghrib, sched.isha]
    assert order == sorted(order), "prayer times must be monotonically increasing"

    for dt in order:
        assert dt.tzinfo is not None, "times must be timezone-aware"
        local = dt.astimezone(ZoneInfo("America/Chicago"))
        assert local.date() == date(2026, 7, 18)


def test_hanafi_asr_is_later_than_shafi():
    day = date(2026, 7, 18)
    shafi = OfflineProvider(OfflineConfig(madhab=Madhab.SHAFI), LOCATION).get_schedule(day)
    hanafi = OfflineProvider(OfflineConfig(madhab=Madhab.HANAFI), LOCATION).get_schedule(day)
    assert hanafi.asr > shafi.asr


# NOTE (post-green): add a golden-value test pinning fajr..isha for LOCATION on a
# fixed date to within +/- 2 minutes of aladhan.com output, to guard against
# library regressions. Keep it as a separate test so structural tests stay stable.
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_offline_provider.py -v` — Expected: FAIL (`ModuleNotFoundError: adhan.times.offline`).

- [ ] **Step 3: Write `src/adhan/times/offline.py`**

adhanpy exposes `PrayerTimes(coordinates, date, calculation_method=?, calculation_parameters=?, time_zone=?)`. Passing a `time_zone` returns localized datetimes. If the installed adhanpy version's parameter names differ, adjust the two call sites below — verify with `python -c "from adhanpy.PrayerTimes import PrayerTimes; help(PrayerTimes.__init__)"`.

```python
from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from adhanpy.PrayerTimes import PrayerTimes
from adhanpy.calculation.CalculationMethod import CalculationMethod
from adhanpy.calculation.CalculationParameters import CalculationParameters
from adhanpy.calculation.HighLatitudeRule import HighLatitudeRule
from adhanpy.calculation.Madhab import Madhab as AdhanMadhab

from adhan.config import LocationConfig, Madhab, OfflineConfig
from adhan.models import PrayerSchedule

_METHOD_MAP = {
    "muslim_world_league": CalculationMethod.MUSLIM_WORLD_LEAGUE,
    "egyptian": CalculationMethod.EGYPTIAN,
    "karachi": CalculationMethod.KARACHI,
    "umm_al_qura": CalculationMethod.UMM_AL_QURA,
    "dubai": CalculationMethod.DUBAI,
    "moonsighting_committee": CalculationMethod.MOON_SIGHTING_COMMITTEE,
    "north_america": CalculationMethod.NORTH_AMERICA,
    "kuwait": CalculationMethod.KUWAIT,
    "qatar": CalculationMethod.QATAR,
    "singapore": CalculationMethod.SINGAPORE,
    "tehran": CalculationMethod.TEHRAN,
    "turkey": CalculationMethod.TURKEY,
}

_HLR_MAP = {
    "middle_of_the_night": HighLatitudeRule.MIDDLE_OF_THE_NIGHT,
    "seventh_of_the_night": HighLatitudeRule.SEVENTH_OF_THE_NIGHT,
    "twilight_angle": HighLatitudeRule.TWILIGHT_ANGLE,
}


class OfflineProvider:
    def __init__(self, offline: OfflineConfig, location: LocationConfig):
        if offline.method not in _METHOD_MAP:
            raise ValueError(f"Unknown calculation method: {offline.method}")
        if offline.high_latitude_rule not in _HLR_MAP:
            raise ValueError(f"Unknown high_latitude_rule: {offline.high_latitude_rule}")
        self._offline = offline
        self._location = location
        self._tz = ZoneInfo(location.timezone)

    def get_schedule(self, day: date) -> PrayerSchedule:
        params = CalculationParameters(method=_METHOD_MAP[self._offline.method])
        params.madhab = (
            AdhanMadhab.HANAFI if self._offline.madhab is Madhab.HANAFI else AdhanMadhab.SHAFI
        )
        params.high_latitude_rule = _HLR_MAP[self._offline.high_latitude_rule]

        pt = PrayerTimes(
            (self._location.latitude, self._location.longitude),
            day,
            calculation_parameters=params,
            time_zone=self._tz,
        )
        return PrayerSchedule(
            fajr=pt.fajr,
            sunrise=pt.sunrise,
            dhuhr=pt.dhuhr,
            asr=pt.asr,
            maghrib=pt.maghrib,
            isha=pt.isha,
        )
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_offline_provider.py -v` — Expected: PASS (2 passed). If it errors on the `PrayerTimes(...)` call, run the `help()` command above and adjust the keyword names, then re-run.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add offline (adhanpy) prayer-time provider"
```

### Task 2.3: ScheduleAdjuster (offsets + Fajr mode)

**Files:**
- Create: `src/adhan/times/adjuster.py`, `tests/test_adjuster.py`

- [ ] **Step 1: Write the failing test — `tests/test_adjuster.py`**

```python
from datetime import datetime, timezone

from adhan.config import FajrMode, PrayerConfig
from adhan.models import Prayer, PrayerSchedule
from adhan.times.adjuster import ScheduleAdjuster


def _dt(h, m):
    return datetime(2026, 7, 18, h, m, tzinfo=timezone.utc)


SCHED = PrayerSchedule(
    fajr=_dt(5, 0), sunrise=_dt(6, 30), dhuhr=_dt(13, 0),
    asr=_dt(17, 0), maghrib=_dt(20, 30), isha=_dt(22, 0),
)


def test_fajr_before_sunrise_mode():
    adj = ScheduleAdjuster({"fajr": PrayerConfig(mode=FajrMode.BEFORE_SUNRISE, before_sunrise_minutes=30)})
    out = adj.adjust(SCHED)
    assert out[Prayer.FAJR] == _dt(6, 0)  # 06:30 - 30m


def test_offset_applied():
    adj = ScheduleAdjuster({"asr": PrayerConfig(offset_minutes=60)})
    out = adj.adjust(SCHED)
    assert out[Prayer.ASR] == _dt(18, 0)  # 17:00 + 60m


def test_disabled_prayer_excluded():
    adj = ScheduleAdjuster({"isha": PrayerConfig(enabled=False)})
    out = adj.adjust(SCHED)
    assert Prayer.ISHA not in out
    assert Prayer.FAJR in out  # defaults enabled


def test_defaults_when_prayer_missing_from_config():
    adj = ScheduleAdjuster({})
    out = adj.adjust(SCHED)
    assert out[Prayer.FAJR] == _dt(5, 0)  # calculated, no offset
    assert set(out) == {Prayer.FAJR, Prayer.DHUHR, Prayer.ASR, Prayer.MAGHRIB, Prayer.ISHA}
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_adjuster.py -v` — Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `src/adhan/times/adjuster.py`**

```python
from __future__ import annotations

from datetime import datetime, timedelta

from adhan.config import FajrMode, PrayerConfig
from adhan.models import PLAYABLE_PRAYERS, Prayer, PrayerSchedule


class ScheduleAdjuster:
    def __init__(self, prayers: dict[str, PrayerConfig]):
        self._prayers = prayers

    def _config_for(self, prayer: Prayer) -> PrayerConfig:
        return self._prayers.get(prayer.value, PrayerConfig())

    def adjust(self, schedule: PrayerSchedule) -> dict[Prayer, datetime]:
        result: dict[Prayer, datetime] = {}
        for prayer in PLAYABLE_PRAYERS:
            cfg = self._config_for(prayer)
            if not cfg.enabled:
                continue
            if prayer is Prayer.FAJR and cfg.mode is FajrMode.BEFORE_SUNRISE:
                base = schedule.sunrise - timedelta(minutes=cfg.before_sunrise_minutes)
            else:
                base = schedule.get(prayer)
            result[prayer] = base + timedelta(minutes=cfg.offset_minutes)
        return result
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_adjuster.py -v` — Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add schedule adjuster (offsets + fajr mode)"
```

---

## Milestone 3 — Scheduler

### Task 3.1: AdhanScheduler

**Files:**
- Create: `src/adhan/scheduler.py`, `tests/test_scheduler.py`; Modify: `tests/fakes.py`

- [ ] **Step 1: Add `FakeScheduler` to `tests/fakes.py`**

```python
class FakeJob:
    def __init__(self, run_date, args, job_id):
        self.run_date = run_date
        self.args = args
        self.id = job_id


class FakeScheduler:
    """Records add_job calls the way APScheduler would be driven."""

    def __init__(self):
        self.jobs: list[FakeJob] = []
        self.started = False
        self.cron_jobs: list[dict] = []

    def add_job(self, func, trigger, **kwargs):
        if trigger == "date":
            self.jobs.append(FakeJob(kwargs["run_date"], kwargs.get("args", []), kwargs.get("id")))
        elif trigger == "cron":
            self.cron_jobs.append(kwargs)
        return FakeJob(kwargs.get("run_date"), kwargs.get("args", []), kwargs.get("id"))

    def remove_all_jobs(self):
        self.jobs.clear()

    def start(self):
        self.started = True
```

- [ ] **Step 2: Write the failing test — `tests/test_scheduler.py`**

```python
from datetime import date, datetime, timezone

from freezegun import freeze_time

from adhan.config import PrayerConfig
from adhan.models import Prayer, PrayerSchedule
from adhan.scheduler import AdhanScheduler
from adhan.times.adjuster import ScheduleAdjuster
from tests.fakes import FakeScheduler, FakeTimeProvider


def _dt(h, m):
    return datetime(2026, 7, 18, h, m, tzinfo=timezone.utc)


SCHED = PrayerSchedule(
    fajr=_dt(5, 0), sunrise=_dt(6, 30), dhuhr=_dt(13, 0),
    asr=_dt(17, 0), maghrib=_dt(20, 30), isha=_dt(22, 0),
)


def _make(fired, backend):
    return AdhanScheduler(
        provider=FakeTimeProvider(SCHED),
        adjuster=ScheduleAdjuster({}),
        on_prayer=lambda p: fired.append(p),
        backend=backend,
        misfire_grace_seconds=300,
    )


@freeze_time("2026-07-18 11:00:00")  # UTC; before dhuhr, after fajr
def test_schedule_day_only_future_prayers():
    backend = FakeScheduler()
    _make([], backend).schedule_day(datetime.now(timezone.utc))
    ids = {j.id for j in backend.jobs}
    # fajr (05:00) is in the past and must be skipped; dhuhr..isha scheduled
    assert ids == {"prayer-dhuhr", "prayer-asr", "prayer-maghrib", "prayer-isha"}


@freeze_time("2026-07-18 11:00:00")
def test_scheduled_job_fires_callback():
    fired = []
    backend = FakeScheduler()
    sched = _make(fired, backend)
    sched.schedule_day(datetime.now(timezone.utc))
    job = next(j for j in backend.jobs if j.id == "prayer-dhuhr")
    sched._fire(*job.args)
    assert fired == [Prayer.DHUHR]


def test_compute_jobs_returns_all_enabled():
    jobs = _make([], FakeScheduler()).compute_jobs(date(2026, 7, 18))
    assert set(jobs) == {Prayer.FAJR, Prayer.DHUHR, Prayer.ASR, Prayer.MAGHRIB, Prayer.ISHA}
```

- [ ] **Step 3: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_scheduler.py -v` — Expected: FAIL (`ModuleNotFoundError: adhan.scheduler`).

- [ ] **Step 4: Write `src/adhan/scheduler.py`**

```python
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Callable, Protocol

from adhan.models import Prayer
from adhan.times.adjuster import ScheduleAdjuster
from adhan.times.base import TimeProvider

logger = logging.getLogger(__name__)


class SchedulerBackend(Protocol):
    def add_job(self, func: Callable, trigger: str, **kwargs): ...
    def remove_all_jobs(self) -> None: ...
    def start(self) -> None: ...


class AdhanScheduler:
    def __init__(
        self,
        provider: TimeProvider,
        adjuster: ScheduleAdjuster,
        on_prayer: Callable[[Prayer], None],
        backend: SchedulerBackend,
        misfire_grace_seconds: int = 300,
        on_regenerate: Callable[[dict[Prayer, datetime]], None] | None = None,
    ):
        self._provider = provider
        self._adjuster = adjuster
        self._on_prayer = on_prayer
        self._backend = backend
        self._grace = misfire_grace_seconds
        self._on_regenerate = on_regenerate

    def compute_jobs(self, day: date) -> dict[Prayer, datetime]:
        return self._adjuster.adjust(self._provider.get_schedule(day))

    def schedule_day(self, now: datetime) -> dict[Prayer, datetime]:
        jobs = self.compute_jobs(now.date())
        for prayer, when in jobs.items():
            if when <= now:
                continue
            self._backend.add_job(
                self._fire,
                "date",
                run_date=when,
                args=[prayer],
                id=f"prayer-{prayer.value}",
                misfire_grace_time=self._grace,
                replace_existing=True,
            )
        if self._on_regenerate is not None:
            self._on_regenerate(jobs)
        return jobs

    def _fire(self, prayer: Prayer) -> None:
        logger.info("firing adhan", extra={"prayer": prayer.value})
        self._on_prayer(prayer)

    def _regenerate(self) -> None:
        self._backend.remove_all_jobs()
        self.schedule_day(datetime.now().astimezone())
        # re-register the daily regeneration cron (removed by remove_all_jobs)
        self._register_daily_regen()

    def _register_daily_regen(self) -> None:
        self._backend.add_job(
            self._regenerate, "cron", hour=0, minute=1, id="daily-regen", replace_existing=True
        )

    def start(self) -> None:
        self.schedule_day(datetime.now().astimezone())
        self._register_daily_regen()
        self._backend.start()
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_scheduler.py -v` — Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add AdhanScheduler with daily regeneration"
```

---

## Milestone 4 — Media

### Task 4.1: MediaManager (resolve file + volume) and LAN IP helper

**Files:**
- Create: `src/adhan/netutil.py`, `src/adhan/media.py`, `tests/test_media.py`

- [ ] **Step 1: Write the failing test — `tests/test_media.py` (resolve part)**

```python
import pytest

from adhan.config import AudioConfig
from adhan.media import MediaManager
from adhan.models import Prayer


def _audio():
    return AudioConfig(
        default_file="adhan.mp3",
        per_prayer_files={"fajr": "adhan_fajr.mp3"},
        default_volume=0.6,
        per_prayer_volume={"fajr": 0.4},
    )


def test_resolve_default(tmp_path):
    (tmp_path / "adhan.mp3").write_bytes(b"x")
    mm = MediaManager(_audio(), tmp_path, "http://10.0.0.5:8127")
    media, volume = mm.resolve(Prayer.DHUHR)
    assert media.url == "http://10.0.0.5:8127/adhan.mp3"
    assert media.file_path == str(tmp_path / "adhan.mp3")
    assert volume == 0.6


def test_resolve_fajr_override(tmp_path):
    (tmp_path / "adhan_fajr.mp3").write_bytes(b"x")
    mm = MediaManager(_audio(), tmp_path, "http://10.0.0.5:8127")
    media, volume = mm.resolve(Prayer.FAJR)
    assert media.url.endswith("/adhan_fajr.mp3")
    assert volume == 0.4


def test_resolve_missing_file_raises(tmp_path):
    mm = MediaManager(_audio(), tmp_path, "http://10.0.0.5:8127")
    with pytest.raises(FileNotFoundError):
        mm.resolve(Prayer.DHUHR)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_media.py -v` — Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `src/adhan/netutil.py`**

```python
from __future__ import annotations

import socket


def get_lan_ip() -> str:
    """Best-effort primary LAN IPv4 address (no traffic actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()
```

- [ ] **Step 4: Write `src/adhan/media.py`** (MediaManager only; HTTP server added in Task 4.2)

```python
from __future__ import annotations

from pathlib import Path

from adhan.config import AudioConfig
from adhan.models import MediaRef, Prayer


class MediaManager:
    def __init__(self, audio: AudioConfig, media_dir: Path, base_url: str):
        self._audio = audio
        self._media_dir = Path(media_dir)
        self._base_url = base_url.rstrip("/")

    def _filename(self, prayer: Prayer) -> str:
        return self._audio.per_prayer_files.get(prayer.value, self._audio.default_file)

    def resolve(self, prayer: Prayer) -> tuple[MediaRef, float]:
        filename = self._filename(prayer)
        path = self._media_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Adhan file not found: {path}")
        volume = self._audio.per_prayer_volume.get(prayer.value, self._audio.default_volume)
        media = MediaRef(file_path=str(path), url=f"{self._base_url}/{filename}")
        return media, volume
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_media.py -v` — Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add MediaManager and LAN IP helper"
```

### Task 4.2: Media HTTP server (serves the media dir to Cast devices)

**Files:**
- Modify: `src/adhan/media.py`; Modify: `tests/test_media.py`

- [ ] **Step 1: Add the failing test to `tests/test_media.py`**

```python
import urllib.request

from adhan.media import MediaHTTPServer


def test_http_server_serves_media_file(tmp_path):
    (tmp_path / "adhan.mp3").write_bytes(b"ADHAN-BYTES")
    server = MediaHTTPServer(tmp_path, host="127.0.0.1", port=0)
    server.start()
    try:
        url = f"http://127.0.0.1:{server.port}/adhan.mp3"
        body = urllib.request.urlopen(url, timeout=5).read()
        assert body == b"ADHAN-BYTES"
    finally:
        server.stop()


def test_http_server_blocks_directory_listing(tmp_path):
    (tmp_path / "adhan.mp3").write_bytes(b"x")
    server = MediaHTTPServer(tmp_path, host="127.0.0.1", port=0)
    server.start()
    try:
        import urllib.error

        try:
            urllib.request.urlopen(f"http://127.0.0.1:{server.port}/", timeout=5)
            assert False, "directory listing should be forbidden"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        server.stop()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_media.py -k http -v` — Expected: FAIL (`ImportError: MediaHTTPServer`).

- [ ] **Step 3: Append `MediaHTTPServer` to `src/adhan/media.py`**

```python
import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class _MediaRequestHandler(SimpleHTTPRequestHandler):
    def list_directory(self, path):  # no directory listings
        self.send_error(404, "Not found")
        return None

    def log_message(self, *args):  # silence default stderr logging
        pass


class MediaHTTPServer:
    def __init__(self, media_dir, host: str, port: int):
        handler = functools.partial(_MediaRequestHandler, directory=str(media_dir))
        self._httpd = ThreadingHTTPServer((host, port), handler)
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return self._httpd.server_address[1]

    def start(self) -> None:
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread:
            self._thread.join(timeout=5)
```

`SimpleHTTPRequestHandler(directory=...)` confines serving to `media_dir` and rejects `..` traversal. Overriding `list_directory` turns index requests into 404s.

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_media.py -v` — Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add restricted media HTTP server"
```

---

## Milestone 5 — Players

### Task 5.1: Player protocol + FakePlayer

**Files:**
- Create: `src/adhan/players/__init__.py` (empty), `src/adhan/players/base.py`; Modify: `tests/fakes.py`; Create: `tests/test_players_base.py`

- [ ] **Step 1: Add `FakePlayer` to `tests/fakes.py`**

```python
from adhan.models import HealthState, HealthStatus, MediaRef, PlayResult


class FakePlayer:
    """Fails its first `fail_times` play() calls, then succeeds."""

    def __init__(self, name: str, fail_times: int = 0, health=HealthState.OK, raises: bool = False):
        self.name = name
        self._fail_times = fail_times
        self._health = health
        self._raises = raises
        self.calls: list[tuple[MediaRef, float]] = []

    def health_check(self) -> HealthStatus:
        return HealthStatus(player=self.name, state=self._health)

    def play(self, media: MediaRef, volume: float) -> PlayResult:
        self.calls.append((media, volume))
        if len(self.calls) <= self._fail_times:
            if self._raises:
                raise RuntimeError("boom")
            return PlayResult(self.name, success=False, error="simulated failure")
        return PlayResult(self.name, success=True)
```

- [ ] **Step 2: Write the failing test — `tests/test_players_base.py`**

```python
from adhan.models import MediaRef
from adhan.players.base import Player
from tests.fakes import FakePlayer


def test_fake_player_satisfies_protocol():
    p: Player = FakePlayer("cast:Living")
    r = p.play(MediaRef("/x/a.mp3", "http://h/a.mp3"), 0.5)
    assert r.success and p.name == "cast:Living"
```

- [ ] **Step 3: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_players_base.py -v` — Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 4: Write `src/adhan/players/__init__.py` (empty) and `src/adhan/players/base.py`**

```python
from __future__ import annotations

from typing import Protocol

from adhan.models import HealthStatus, MediaRef, PlayResult


class Player(Protocol):
    name: str

    def health_check(self) -> HealthStatus: ...
    def play(self, media: MediaRef, volume: float) -> PlayResult: ...
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_players_base.py -v` — Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add Player protocol and fake player"
```

### Task 5.2: ReliablePlayer (health-check + retry)

**Files:**
- Create: `src/adhan/players/reliable.py`, `tests/test_reliable.py`

- [ ] **Step 1: Write the failing test — `tests/test_reliable.py`**

```python
from adhan.models import HealthState, MediaRef
from adhan.players.reliable import ReliablePlayer
from tests.fakes import FakePlayer

MEDIA = MediaRef("/x/a.mp3", "http://h/a.mp3")


def _wrap(inner, attempts=2):
    sleeps = []
    rp = ReliablePlayer(inner, attempts=attempts, backoff_seconds=5, sleep=sleeps.append)
    return rp, sleeps


def test_succeeds_first_try():
    rp, sleeps = _wrap(FakePlayer("p"))
    r = rp.play(MEDIA, 0.5)
    assert r.success and r.attempts == 1 and sleeps == []


def test_retries_then_succeeds():
    rp, sleeps = _wrap(FakePlayer("p", fail_times=1), attempts=2)
    r = rp.play(MEDIA, 0.5)
    assert r.success and r.attempts == 2 and sleeps == [5]


def test_all_attempts_fail():
    rp, sleeps = _wrap(FakePlayer("p", fail_times=5), attempts=2)
    r = rp.play(MEDIA, 0.5)
    assert not r.success and r.attempts == 2 and r.error == "simulated failure"


def test_exception_is_caught_as_failure():
    rp, _ = _wrap(FakePlayer("p", fail_times=5, raises=True), attempts=1)
    r = rp.play(MEDIA, 0.5)
    assert not r.success and "boom" in r.error


def test_name_delegates():
    rp, _ = _wrap(FakePlayer("cast:Kitchen"))
    assert rp.name == "cast:Kitchen"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_reliable.py -v` — Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `src/adhan/players/reliable.py`**

```python
from __future__ import annotations

import logging
from typing import Callable

from adhan.models import MediaRef, PlayResult
from adhan.players.base import Player

logger = logging.getLogger(__name__)


class ReliablePlayer:
    def __init__(
        self,
        inner: Player,
        attempts: int,
        backoff_seconds: float,
        sleep: Callable[[float], None] | None = None,
    ):
        self._inner = inner
        self._attempts = max(1, attempts)
        self._backoff = backoff_seconds
        import time

        self._sleep = sleep or time.sleep

    @property
    def name(self) -> str:
        return self._inner.name

    def health_check(self):
        return self._inner.health_check()

    def play(self, media: MediaRef, volume: float) -> PlayResult:
        health = self._inner.health_check()
        logger.info(
            "pre-play health", extra={"player": self.name, "health": health.state.value}
        )
        last_error = "unknown error"
        for attempt in range(1, self._attempts + 1):
            try:
                result = self._inner.play(media, volume)
                if result.success:
                    return PlayResult(self.name, True, attempts=attempt)
                last_error = result.error or "play returned failure"
            except Exception as exc:  # hardware calls can raise
                last_error = str(exc)
            if attempt < self._attempts:
                self._sleep(self._backoff * attempt)
        logger.warning(
            "play failed", extra={"player": self.name, "error": last_error, "attempts": self._attempts}
        )
        return PlayResult(self.name, False, error=last_error, attempts=self._attempts)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_reliable.py -v` — Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add ReliablePlayer with health-check and retry"
```

### Task 5.3: OutputManager (concurrent fan-out)

**Files:**
- Create: `src/adhan/players/manager.py`, `tests/test_output_manager.py`

- [ ] **Step 1: Write the failing test — `tests/test_output_manager.py`**

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_output_manager.py -v` — Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `src/adhan/players/manager.py`**

```python
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from adhan.models import MediaRef, PlayResult
from adhan.players.base import Player


class OutputManager:
    def __init__(self, players: list[Player]):
        self._players = players

    def play_all(self, media: MediaRef, volume: float) -> list[PlayResult]:
        if not self._players:
            return []
        with ThreadPoolExecutor(max_workers=len(self._players)) as pool:
            futures = [pool.submit(p.play, media, volume) for p in self._players]
            return [f.result() for f in futures]
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_output_manager.py -v` — Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add OutputManager fan-out"
```

### Task 5.4: CastPlayer (pychromecast, injectable)

**Files:**
- Create: `src/adhan/players/cast.py`, `tests/test_cast_player.py`; Modify: `tests/fakes.py`

CastPlayer takes a `cast_factory` callable so tests inject a fake. The factory returns an object exposing the small slice of the pychromecast API we use.

- [ ] **Step 1: Add `FakeCast` to `tests/fakes.py`**

```python
class _FakeMediaController:
    def __init__(self, states):
        self._states = list(states)
        self.played = None
        self.player_state = "UNKNOWN"

    def play_media(self, url, content_type):
        self.played = (url, content_type)

    def block_until_active(self, timeout=None):
        pass

    @property
    def status(self):
        self.player_state = self._states.pop(0) if self._states else "IDLE"

        class _S:
            pass

        s = _S()
        s.player_state = self.player_state
        return s


class FakeCast:
    def __init__(self, name="Living", volume=0.3, states=("PLAYING", "IDLE")):
        self.name = name
        self.volume_level = volume
        self.set_volumes: list[float] = []
        self.media_controller = _FakeMediaController(states)
        self.waited = False

    def wait(self, timeout=None):
        self.waited = True

    def set_volume(self, level):
        self.volume_level = level
        self.set_volumes.append(level)

    @property
    def status(self):
        class _S:
            pass

        s = _S()
        s.volume_level = self.volume_level
        return s
```

- [ ] **Step 2: Write the failing test — `tests/test_cast_player.py`**

```python
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
    assert fake.set_volumes[0] == 0.7      # announce volume
    assert fake.set_volumes[-1] == 0.3     # restored original


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
```

- [ ] **Step 3: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_cast_player.py -v` — Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 4: Write `src/adhan/players/cast.py`**

The default `cast_factory` uses pychromecast's `get_listed_chromecasts`. Verify the discovery call against the installed version with `python -c "import pychromecast; help(pychromecast.get_listed_chromecasts)"`; adjust if the signature differs.

```python
from __future__ import annotations

import time
from typing import Callable

from adhan.models import HealthState, HealthStatus, MediaRef, PlayResult

_ACTIVE_STATES = {"PLAYING", "BUFFERING"}


def _default_factory(name: str):
    import pychromecast

    chromecasts, browser = pychromecast.get_listed_chromecasts(friendly_names=[name])
    if not chromecasts:
        raise OSError(f"Cast device not found: {name}")
    cc = chromecasts[0]
    cc.wait(timeout=10)
    return cc


class CastPlayer:
    def __init__(
        self,
        name: str,
        cast_factory: Callable[[str], object] = _default_factory,
        poll_interval: float = 1.0,
        max_wait_seconds: float = 600.0,
    ):
        self.name = f"cast:{name}"
        self._device_name = name
        self._factory = cast_factory
        self._poll = poll_interval
        self._max_wait = max_wait_seconds

    def health_check(self) -> HealthStatus:
        try:
            self._factory(self._device_name)
            return HealthStatus(self.name, HealthState.OK)
        except Exception as exc:
            return HealthStatus(self.name, HealthState.UNREACHABLE, detail=str(exc))

    def play(self, media: MediaRef, volume: float) -> PlayResult:
        try:
            cc = self._factory(self._device_name)
            previous = cc.status.volume_level
            cc.set_volume(volume)
            mc = cc.media_controller
            mc.play_media(media.url, "audio/mpeg")
            mc.block_until_active(timeout=30)
            self._wait_for_finish(mc)
            cc.set_volume(previous)
            return PlayResult(self.name, True)
        except Exception as exc:
            return PlayResult(self.name, False, error=str(exc))

    def _wait_for_finish(self, mc) -> None:
        waited = 0.0
        while mc.status.player_state in _ACTIVE_STATES:
            if self._poll <= 0 or waited >= self._max_wait:
                break
            time.sleep(self._poll)
            waited += self._poll
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_cast_player.py -v` — Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add CastPlayer (pychromecast) with injectable factory"
```

### Task 5.5: BluetoothPlayer (PipeWire, injectable runner)

**Files:**
- Create: `src/adhan/players/bluetooth.py`, `tests/test_bluetooth_player.py`; Modify: `tests/fakes.py`

BluetoothPlayer shells out to PipeWire/PulseAudio tools (`pactl`, `paplay`) against a pre-created combined sink. A `runner` callable (default `subprocess.run`) is injected so tests assert the exact commands.

- [ ] **Step 1: Add `RecordingRunner` to `tests/fakes.py`**

```python
import subprocess


class RecordingRunner:
    """Stands in for subprocess.run. `fail_on` = substring that triggers CalledProcessError."""

    def __init__(self, sinks_output="adhan_combined\t...\n", fail_on: str | None = None):
        self.commands: list[list[str]] = []
        self._sinks_output = sinks_output
        self._fail_on = fail_on

    def __call__(self, args, check=False, capture_output=False, text=False, timeout=None):
        self.commands.append(args)
        if self._fail_on and self._fail_on in " ".join(args):
            raise subprocess.CalledProcessError(1, args)
        stdout = ""
        if args[:3] == ["pactl", "list", "short"]:
            stdout = self._sinks_output

        class _CP:
            pass

        cp = _CP()
        cp.returncode = 0
        cp.stdout = stdout
        return cp
```

- [ ] **Step 2: Write the failing test — `tests/test_bluetooth_player.py`**

```python
from adhan.models import HealthState, MediaRef
from adhan.players.bluetooth import BluetoothPlayer
from tests.fakes import RecordingRunner

MEDIA = MediaRef("/media/adhan.mp3", "http://h/adhan.mp3")


def test_play_sets_volume_then_plays_to_sink():
    runner = RecordingRunner(sinks_output="42\tadhan_combined\tmodule\tformat\tRUNNING\n")
    player = BluetoothPlayer("adhan_combined", runner=runner)
    r = player.play(MEDIA, 0.4)
    assert r.success
    cmds = [" ".join(c) for c in runner.commands]
    assert any("set-sink-volume adhan_combined 40%" in c for c in cmds)
    assert any("paplay --device=adhan_combined /media/adhan.mp3" in c for c in cmds)


def test_health_ok_when_sink_present():
    runner = RecordingRunner(sinks_output="42\tadhan_combined\tx\ty\tRUNNING\n")
    assert BluetoothPlayer("adhan_combined", runner=runner).health_check().state is HealthState.OK


def test_health_unreachable_when_sink_absent():
    runner = RecordingRunner(sinks_output="42\tother_sink\tx\ty\tRUNNING\n")
    assert (
        BluetoothPlayer("adhan_combined", runner=runner).health_check().state
        is HealthState.UNREACHABLE
    )


def test_play_failure_returns_error():
    runner = RecordingRunner(sinks_output="42\tadhan_combined\tx\ty\tRUNNING\n", fail_on="paplay")
    r = BluetoothPlayer("adhan_combined", runner=runner).play(MEDIA, 0.4)
    assert not r.success
```

- [ ] **Step 3: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_bluetooth_player.py -v` — Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 4: Write `src/adhan/players/bluetooth.py`**

```python
from __future__ import annotations

import subprocess
from typing import Callable

from adhan.models import HealthState, HealthStatus, MediaRef, PlayResult

Runner = Callable[..., subprocess.CompletedProcess]


class BluetoothPlayer:
    """Plays to a PipeWire combined sink that aggregates the paired A2DP sinks.

    The combined sink itself is created by the system layer (Task 8.3) so all
    Bluetooth speakers play together from a single play() call.
    """

    def __init__(self, sink_name: str, runner: Runner = subprocess.run):
        self.name = f"bluetooth:{sink_name}"
        self._sink = sink_name
        self._run = runner

    def _sink_present(self) -> bool:
        cp = self._run(["pactl", "list", "short", "sinks"], check=True, capture_output=True, text=True)
        return any(self._sink in line.split() for line in (cp.stdout or "").splitlines())

    def health_check(self) -> HealthStatus:
        try:
            if self._sink_present():
                return HealthStatus(self.name, HealthState.OK)
            return HealthStatus(self.name, HealthState.UNREACHABLE, detail="combined sink missing")
        except Exception as exc:
            return HealthStatus(self.name, HealthState.UNREACHABLE, detail=str(exc))

    def play(self, media: MediaRef, volume: float) -> PlayResult:
        try:
            percent = f"{int(round(volume * 100))}%"
            self._run(["pactl", "set-sink-volume", self._sink, percent], check=True)
            self._run(["paplay", f"--device={self._sink}", media.file_path], check=True)
            return PlayResult(self.name, True)
        except Exception as exc:
            return PlayResult(self.name, False, error=str(exc))
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_bluetooth_player.py -v` — Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add BluetoothPlayer (PipeWire combined sink)"
```

---

## Milestone 6 — State, logging, orchestration

### Task 6.1: StateStore (state.json)

**Files:**
- Create: `src/adhan/state.py`, `tests/test_state.py`

- [ ] **Step 1: Write the failing test — `tests/test_state.py`**

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_state.py -v` — Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `src/adhan/state.py`**

```python
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Callable

from adhan.models import Prayer, PlayResult


class StateStore:
    def __init__(self, path: str | Path, clock: Callable[[], datetime] | None = None):
        self._path = Path(path)
        self._clock = clock or (lambda: datetime.now().astimezone())
        self._data: dict = {
            "service_started_at": self._clock().isoformat(),
            "next_prayer": None,
            "today_schedule": {},
            "last_results": {},
        }
        self._write()

    def set_schedule(self, jobs: dict[Prayer, datetime]) -> None:
        self._data["today_schedule"] = {p.value: when.isoformat() for p, when in jobs.items()}
        now = self._clock()
        upcoming = sorted((when, p) for p, when in jobs.items() if when > now)
        if upcoming:
            when, prayer = upcoming[0]
            self._data["next_prayer"] = {"name": prayer.value, "time": when.isoformat()}
        else:
            self._data["next_prayer"] = None
        self._write()

    def record_result(self, prayer: Prayer, results: list[PlayResult]) -> None:
        self._data["last_results"][prayer.value] = {
            "at": self._clock().isoformat(),
            "outputs": {
                r.player: {"success": r.success, "error": r.error, "attempts": r.attempts}
                for r in results
            },
        }
        self._write()

    def _write(self) -> None:
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        os.replace(tmp, self._path)  # atomic on POSIX
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_state.py -v` — Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add StateStore heartbeat (state.json)"
```

### Task 6.2: JSON logging setup

**Files:**
- Create: `src/adhan/logging_setup.py`, `tests/test_logging.py`

- [ ] **Step 1: Write the failing test — `tests/test_logging.py`**

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_logging.py -v` — Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `src/adhan/logging_setup.py`**

```python
from __future__ import annotations

import json
import logging
import sys

_STANDARD = set(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: str = "INFO", as_json: bool = True) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter() if as_json else logging.Formatter("%(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_logging.py -v` — Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add JSON logging setup"
```

### Task 6.3: Orchestrator

**Files:**
- Create: `src/adhan/orchestrator.py`, `tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing test — `tests/test_orchestrator.py`**

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_orchestrator.py -v` — Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `src/adhan/orchestrator.py`**

```python
from __future__ import annotations

import logging

from adhan.media import MediaManager
from adhan.models import Prayer, PlayResult
from adhan.players.manager import OutputManager
from adhan.state import StateStore

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, media: MediaManager, outputs: OutputManager, state: StateStore):
        self._media = media
        self._outputs = outputs
        self._state = state

    def handle_prayer(self, prayer: Prayer) -> None:
        logger.info("adhan triggered", extra={"prayer": prayer.value})
        try:
            media, volume = self._media.resolve(prayer)
        except FileNotFoundError as exc:
            logger.error("media resolve failed", extra={"prayer": prayer.value, "error": str(exc)})
            self._state.record_result(prayer, [PlayResult("media", False, error=str(exc))])
            return
        results = self._outputs.play_all(media, volume)
        for r in results:
            logger.info(
                "output result",
                extra={"prayer": prayer.value, "player": r.player, "success": r.success},
            )
        self._state.record_result(prayer, results)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_orchestrator.py -v` — Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add Orchestrator wiring prayer -> play -> state"
```

---

## Milestone 7 — Application assembly & CLI

### Task 7.1: App builder & run loop

**Files:**
- Create: `src/adhan/app.py`, `src/adhan/__main__.py`; Modify: `tests/test_orchestrator.py` is unaffected. Create: `tests/test_app.py`

`app.py` is excluded from the coverage gate (wiring), but its player-construction helper is pure and tested.

- [ ] **Step 1: Write the failing test — `tests/test_app.py`**

```python
from adhan.app import build_players
from adhan.config import BluetoothConfig, BluetoothSpeaker, CastOutput, OutputsConfig, ReliabilityConfig


def test_build_players_creates_cast_and_bluetooth_wrapped():
    outputs = OutputsConfig(
        cast=[CastOutput(name="Living")],
        bluetooth=BluetoothConfig(speakers=[BluetoothSpeaker(name="JBL", mac="AA:BB:CC:DD:EE:FF")]),
    )
    players = build_players(outputs, ReliabilityConfig(), combined_sink="adhan_combined")
    names = sorted(p.name for p in players)
    assert names == ["bluetooth:adhan_combined", "cast:Living"]


def test_build_players_no_bluetooth_when_no_speakers():
    outputs = OutputsConfig(cast=[CastOutput(name="Living")], bluetooth=BluetoothConfig(speakers=[]))
    players = build_players(outputs, ReliabilityConfig(), combined_sink="adhan_combined")
    assert [p.name for p in players] == ["cast:Living"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_app.py -v` — Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `src/adhan/app.py`**

```python
from __future__ import annotations

import logging
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from adhan.config import Config, OutputsConfig, ReliabilityConfig
from adhan.logging_setup import configure_logging
from adhan.media import MediaHTTPServer, MediaManager
from adhan.netutil import get_lan_ip
from adhan.orchestrator import Orchestrator
from adhan.players.base import Player
from adhan.players.bluetooth import BluetoothPlayer
from adhan.players.cast import CastPlayer
from adhan.players.manager import OutputManager
from adhan.players.reliable import ReliablePlayer
from adhan.scheduler import AdhanScheduler
from adhan.state import StateStore
from adhan.times.adjuster import ScheduleAdjuster
from adhan.times.offline import OfflineProvider

logger = logging.getLogger(__name__)

DEFAULT_COMBINED_SINK = "adhan_combined"


def build_players(
    outputs: OutputsConfig, reliability: ReliabilityConfig, combined_sink: str
) -> list[Player]:
    raw: list[Player] = [CastPlayer(c.name) for c in outputs.cast]
    if outputs.bluetooth.speakers:
        raw.append(BluetoothPlayer(combined_sink))
    return [
        ReliablePlayer(p, attempts=reliability.retry_attempts, backoff_seconds=reliability.retry_backoff_seconds)
        for p in raw
    ]


class App:
    def __init__(self, config: Config, media_dir: Path, state_path: Path):
        self._config = config
        self._media_dir = Path(media_dir)
        self._state_path = Path(state_path)
        self._http: MediaHTTPServer | None = None

    def _base_url(self) -> str:
        host = self._config.network.http_host
        if host == "auto":
            host = get_lan_ip()
        return f"http://{host}:{self._config.network.http_port}"

    def build(self) -> AdhanScheduler:
        cfg = self._config
        host = get_lan_ip() if cfg.network.http_host == "auto" else cfg.network.http_host
        self._http = MediaHTTPServer(self._media_dir, host=host, port=cfg.network.http_port)

        media = MediaManager(cfg.audio, self._media_dir, self._base_url())
        players = build_players(cfg.outputs, cfg.reliability, DEFAULT_COMBINED_SINK)
        state = StateStore(self._state_path)
        orchestrator = Orchestrator(media, OutputManager(players), state)

        provider = OfflineProvider(cfg.prayer_times.offline, cfg.location)
        adjuster = ScheduleAdjuster(cfg.prayer_times.prayers)
        backend = BackgroundScheduler(timezone=cfg.location.timezone)
        return AdhanScheduler(
            provider=provider,
            adjuster=adjuster,
            on_prayer=orchestrator.handle_prayer,
            backend=backend,
            misfire_grace_seconds=cfg.reliability.misfire_grace_seconds,
            on_regenerate=state.set_schedule,
        )

    def run(self) -> None:
        configure_logging(self._config.logging.level, self._config.logging.json)
        scheduler = self.build()
        assert self._http is not None
        self._http.start()
        scheduler.start()
        logger.info("adhan service started", extra={"base_url": self._base_url()})
        import threading

        threading.Event().wait()  # run forever
```

- [ ] **Step 4: Write `src/adhan/__main__.py`**

```python
from adhan.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_app.py -v` — Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add application builder and run loop"
```

### Task 7.2: CLI

**Files:**
- Create: `src/adhan/cli.py`, `tests/test_cli.py`

- [ ] **Step 1: Write the failing test — `tests/test_cli.py`**

```python
import json
from datetime import datetime, timezone

from adhan.cli import build_parser, cmd_status


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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_cli.py -v` — Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `src/adhan/cli.py`**

```python
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
    from adhan.app import App
    from adhan.config import load_config
    from adhan.models import Prayer

    config = load_config(args.config)
    app = App(config, Path(args.media), Path(args.state))
    scheduler = app.build()
    scheduler._on_prayer(Prayer(args.prayer))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "status":
        return cmd_status(args.state)
    if args.command == "test-play":
        return cmd_test_play(args)
    return 2
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_cli.py -v` — Expected: PASS (3 passed).

- [ ] **Step 5: Run the whole suite with coverage**

Run: `.venv/bin/pytest --cov` — Expected: all pass; coverage ≥95% on gated modules.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add CLI (run/status/test-play)"
```

---

## Milestone 8 — Packaging & Bluetooth system integration

These artifacts are validated by `shellcheck`, `systemd-analyze verify`, and the smoke checklist (Task 9.1), not unit tests.

### Task 8.1: systemd main service

**Files:**
- Create: `systemd/adhan.service`

- [ ] **Step 1: Write `systemd/adhan.service`**

```ini
[Unit]
Description=Adhan appliance
After=network-online.target pipewire.service
Wants=network-online.target

[Service]
Type=simple
User=adhan
Group=adhan
SupplementaryGroups=audio bluetooth
ExecStart=/opt/adhan/.venv/bin/adhan --config /etc/adhan/config.yaml --media /etc/adhan/media --state /var/lib/adhan/state.json run
Restart=always
RestartSec=10
StateDirectory=adhan

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Validate**

Run: `systemd-analyze verify systemd/adhan.service` (on the Pi or any systemd host) — Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat: add systemd unit for adhan service"
```

### Task 8.2: Bluetooth pairing wizard

**Files:**
- Create: `scripts/bt-pair.sh`

- [ ] **Step 1: Write `scripts/bt-pair.sh`**

```bash
#!/usr/bin/env bash
# Interactive Bluetooth pairing wizard. Pairs + trusts each speaker so the
# watchdog can auto-reconnect later. Run once per deployment.
set -euo pipefail

ADAPTER="${1:-}"
if [[ -n "$ADAPTER" ]]; then
  bluetoothctl select "$ADAPTER"
fi

echo "Put your Bluetooth speaker into pairing mode, then note its MAC below."
bluetoothctl --timeout 20 scan on || true
echo
read -rp "Enter speaker MAC (AA:BB:CC:DD:EE:FF): " MAC

bluetoothctl pair "$MAC"
bluetoothctl trust "$MAC"
bluetoothctl connect "$MAC"

echo "Paired, trusted, and connected $MAC."
echo "Add this speaker to config.yaml under outputs.bluetooth.speakers."
```

- [ ] **Step 2: Make executable + lint**

```bash
chmod +x scripts/bt-pair.sh
shellcheck scripts/bt-pair.sh
```
Expected: no shellcheck errors.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat: add Bluetooth pairing wizard"
```

### Task 8.3: Combined sink + keep-alive service

**Files:**
- Create: `scripts/bt-keepalive.sh`, `systemd/adhan-bt-keepalive.service`

- [ ] **Step 1: Write `scripts/bt-keepalive.sh`**

Creates the combined sink over all connected A2DP sinks and pushes an inaudible tone so speakers never sleep.

```bash
#!/usr/bin/env bash
# Maintain a PipeWire combined sink over all Bluetooth A2DP sinks and keep the
# speakers awake with a continuous near-silent stream.
set -euo pipefail

SINK_NAME="adhan_combined"

create_combined_sink() {
  # Collect current bluez A2DP sink names.
  mapfile -t BT_SINKS < <(pactl list short sinks | awk '/bluez_output/ {print $2}')
  if [[ ${#BT_SINKS[@]} -eq 0 ]]; then
    return 1
  fi
  if ! pactl list short sinks | awk '{print $2}' | grep -qx "$SINK_NAME"; then
    local joined
    joined=$(IFS=,; echo "${BT_SINKS[*]}")
    pactl load-module module-combine-sink sink_name="$SINK_NAME" slaves="$joined" >/dev/null
  fi
  return 0
}

while true; do
  if create_combined_sink; then
    # ~1% volume sine keeps A2DP links active; -1 amplitude near silence.
    pactl set-sink-volume "$SINK_NAME" 100% || true
    paplay --device="$SINK_NAME" /opt/adhan/share/silence.wav || true
  fi
  sleep 30
done
```

Note: `install.sh` (Task 8.5) generates `/opt/adhan/share/silence.wav` (a 30s low-level tone) so this script has audio to push.

- [ ] **Step 2: Write `systemd/adhan-bt-keepalive.service`**

```ini
[Unit]
Description=Adhan Bluetooth keep-alive (combined sink + anti-sleep)
After=bluetooth.service pipewire.service

[Service]
Type=simple
User=adhan
Group=adhan
SupplementaryGroups=audio bluetooth
ExecStart=/opt/adhan/scripts/bt-keepalive.sh
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 3: Lint + validate + commit**

```bash
chmod +x scripts/bt-keepalive.sh
shellcheck scripts/bt-keepalive.sh
systemd-analyze verify systemd/adhan-bt-keepalive.service
git add -A && git commit -m "feat: add Bluetooth combined-sink keep-alive service"
```
Expected: clean shellcheck + verify.

### Task 8.4: Reconnect watchdog

**Files:**
- Create: `scripts/bt-watchdog.sh`, `systemd/adhan-bt-watchdog.service`

- [ ] **Step 1: Write `scripts/bt-watchdog.sh`**

```bash
#!/usr/bin/env bash
# Reconnect trusted Bluetooth speakers with exponential backoff when they drop.
# MACs are passed as arguments by the systemd unit (from config at install time).
set -euo pipefail

MACS=("$@")
if [[ ${#MACS[@]} -eq 0 ]]; then
  echo "No MACs configured; exiting." >&2
  exit 0
fi

declare -A BACKOFF
for m in "${MACS[@]}"; do BACKOFF["$m"]=2; done

while true; do
  for MAC in "${MACS[@]}"; do
    if bluetoothctl info "$MAC" | grep -q "Connected: yes"; then
      BACKOFF["$MAC"]=2
    else
      echo "Reconnecting $MAC (backoff ${BACKOFF[$MAC]}s)"
      bluetoothctl connect "$MAC" || true
      sleep "${BACKOFF[$MAC]}"
      next=$(( BACKOFF["$MAC"] * 2 ))
      (( next > 120 )) && next=120
      BACKOFF["$MAC"]=$next
    fi
  done
  sleep 10
done
```

- [ ] **Step 2: Write `systemd/adhan-bt-watchdog.service`**

`%I` carries the space-separated MAC list set by the installer via a drop-in or `EnvironmentFile`. The installer writes `/etc/adhan/bt-macs.env` with `MACS="AA:.. 11:.."`.

```ini
[Unit]
Description=Adhan Bluetooth reconnect watchdog
After=bluetooth.service

[Service]
Type=simple
User=adhan
Group=adhan
SupplementaryGroups=bluetooth
EnvironmentFile=/etc/adhan/bt-macs.env
ExecStart=/bin/bash -c '/opt/adhan/scripts/bt-watchdog.sh $MACS'
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 3: Lint + validate + commit**

```bash
chmod +x scripts/bt-watchdog.sh
shellcheck scripts/bt-watchdog.sh
systemd-analyze verify systemd/adhan-bt-watchdog.service
git add -A && git commit -m "feat: add Bluetooth reconnect watchdog"
```
Expected: clean.

### Task 8.5: Installer

**Files:**
- Create: `scripts/install.sh`

- [ ] **Step 1: Write `scripts/install.sh`**

```bash
#!/usr/bin/env bash
# One-shot installer for the adhan appliance on Raspberry Pi OS Lite (Bookworm).
set -euo pipefail

APP_DIR=/opt/adhan
CFG_DIR=/etc/adhan
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "== Installing system packages =="
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip \
  bluez pipewire pipewire-pulse wireplumber pulseaudio-utils shellcheck

echo "== Creating service user =="
id adhan &>/dev/null || sudo useradd --system --create-home --groups audio,bluetooth adhan

echo "== Laying down application =="
sudo mkdir -p "$APP_DIR" "$CFG_DIR/media" /var/lib/adhan "$APP_DIR/share"
sudo cp -r "$REPO_DIR/src" "$REPO_DIR/pyproject.toml" "$APP_DIR/"
sudo cp -r "$REPO_DIR/scripts" "$APP_DIR/"
sudo chmod +x "$APP_DIR"/scripts/*.sh

echo "== Python venv =="
sudo python3 -m venv "$APP_DIR/.venv"
sudo "$APP_DIR/.venv/bin/pip" install -e "$APP_DIR"

echo "== Config =="
[[ -f "$CFG_DIR/config.yaml" ]] || sudo cp "$REPO_DIR/config/config.example.yaml" "$CFG_DIR/config.yaml"

echo "== Keep-alive tone =="
# 30s near-silent 50Hz tone at low volume.
sudo bash -c "command -v sox >/dev/null || apt-get install -y sox"
sudo sox -n -r 44100 -c 2 "$APP_DIR/share/silence.wav" synth 30 sine 50 vol 0.02

echo "== systemd units =="
sudo cp "$REPO_DIR"/systemd/*.service /etc/systemd/system/
sudo chown -R adhan:adhan "$APP_DIR" "$CFG_DIR" /var/lib/adhan
sudo systemctl daemon-reload

cat <<'EOF'

Next steps:
  1. Edit /etc/adhan/config.yaml (location, method, speakers, volumes).
  2. Drop adhan MP3s into /etc/adhan/media/ (adhan.mp3, adhan_fajr.mp3).
  3. Pair Bluetooth speakers:   sudo -u adhan /opt/adhan/scripts/bt-pair.sh
  4. Write MACs:  echo 'MACS="AA:.. 11:.."' | sudo tee /etc/adhan/bt-macs.env
  5. Enable services:
       sudo systemctl enable --now adhan-bt-keepalive adhan-bt-watchdog adhan
  6. Check:  sudo -u adhan /opt/adhan/.venv/bin/adhan --state /var/lib/adhan/state.json status
EOF
```

- [ ] **Step 2: Lint**

```bash
chmod +x scripts/install.sh
shellcheck scripts/install.sh
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat: add installer script"
```

### Task 8.6: README + media placeholder

**Files:**
- Create: `README.md`, `media/.gitkeep`

- [ ] **Step 1: Write `README.md`**

```markdown
# Raspberry Pi Adhan Appliance

Plays the adhan at the five daily prayer times to Google Nest and Bluetooth
speakers (including Echos used as Bluetooth speakers), from a single Raspberry Pi.

See `docs/plan-spec.md` for the design and `docs/plan-impl.md` for the build plan.

## Quick start

```bash
git clone <repo> && cd rpi-adhan-v2
sudo scripts/install.sh
# then follow the printed next steps
```

## Do I need a Bluetooth dongle?

| Setup | Dongle? |
|---|---|
| All Google Nest, no Bluetooth | No |
| Pi 4 on Ethernet or 5 GHz Wi-Fi, <=2 BT speakers | Usually no |
| Pi 4 on 2.4 GHz Wi-Fi with BT speakers | Recommended |
| Pi 3B on Wi-Fi, casting + BT speakers | Recommended (≈required) |
| 3+ BT speakers | Add one dongle (still just one) |

One dongle serves all Bluetooth speakers via the combined sink.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest --cov
```
```

- [ ] **Step 2: Create `media/.gitkeep`** (empty file) so the directory is tracked.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "docs: add README and media placeholder"
```

---

## Milestone 9 — Verification

### Task 9.1: Full suite, coverage gate, and smoke checklist

**Files:**
- Create: `docs/smoke-checklist.md`

- [ ] **Step 1: Run the whole suite with the coverage gate**

Run: `.venv/bin/pytest --cov` — Expected: all tests pass and coverage report shows `fail_under` satisfied (≥95% on gated modules).

- [ ] **Step 2: Write `docs/smoke-checklist.md`** (manual hardware validation per deployment)

```markdown
# Deployment smoke checklist

Run on the target Pi after `install.sh` and configuration.

- [ ] `adhan --config /etc/adhan/config.yaml ... status` prints next prayer.
- [ ] `adhan ... test-play dhuhr` plays on every configured Google Nest target.
- [ ] `adhan ... test-play dhuhr` plays on every Bluetooth speaker simultaneously.
- [ ] Cast target is reached via the Pi's IP URL (not `.local`).
- [ ] Fajr plays the Fajr-specific file at the quieter Fajr volume.
- [ ] Power-cycle a Bluetooth speaker; within ~1 min the watchdog reconnects it.
- [ ] Leave the system idle 30+ min; the Bluetooth speaker has NOT gone to sleep.
- [ ] Reboot the Pi; services come back and `status` shows the schedule.
- [ ] Cross-check computed times against aladhan.com for the client's location.
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "test: add coverage gate run and deployment smoke checklist"
```

---

## Self-Review (completed while writing)

- **Spec coverage:** offline times (Task 2.2), method/madhab/high-lat/offsets (2.2/2.3), Fajr before-sunrise (2.3), enable/disable (2.3), per-prayer file+volume (4.1), Nest cast (5.4), Bluetooth combined sink (5.5, 8.3), concurrent fan-out (5.3), daily regen + DST (3.1), retry + health (5.2), state/observability (6.1/6.2), config-file setup + installer (1.2/8.5), pairing/keep-alive/watchdog (8.2/8.3/8.4), Pi/dongle guidance (README 8.6), tests ≥95% (9.1). Phase 2 items (web UI, Mawaqit, golden image, MQTT) intentionally excluded.
- **Placeholder scan:** no "TBD/TODO/handle appropriately"; every code step has complete code; the two library seams (adhanpy, pychromecast) include an exact verification command rather than a vague note.
- **Type consistency:** `Player.play(media, volume) -> PlayResult` used identically in base/fake/reliable/cast/bluetooth/manager; `PrayerSchedule.get`, `MediaRef(file_path, url)`, `PlayResult(player, success, error, attempts)`, `HealthStatus(player, state, detail)`, `AdhanScheduler(provider, adjuster, on_prayer, backend, ...)` consistent across tasks. Player names are namespaced (`cast:`, `bluetooth:`) consistently in cast.py/bluetooth.py and asserted in app tests.
