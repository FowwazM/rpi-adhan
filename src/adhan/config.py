from __future__ import annotations

from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from adhan.models import Prayer

_VALID_PRAYER_KEYS = {p.value for p in Prayer}


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
    offline: OfflineConfig = Field(default_factory=OfflineConfig)
    prayers: dict[str, PrayerConfig] = Field(default_factory=dict)

    @field_validator("prayers")
    @classmethod
    def _known_prayers(cls, v: dict) -> dict:
        unknown = set(v) - _VALID_PRAYER_KEYS
        if unknown:
            raise ValueError(f"Unknown prayer(s): {sorted(unknown)}")
        return v


class AudioConfig(_Base):
    default_file: str
    per_prayer_files: dict[str, str] = Field(default_factory=dict)
    default_volume: float = Field(0.6, ge=0.0, le=1.0)
    per_prayer_volume: dict[str, float] = Field(default_factory=dict)

    @field_validator("per_prayer_files", "per_prayer_volume")
    @classmethod
    def _known_audio_prayers(cls, v: dict) -> dict:
        unknown = set(v) - _VALID_PRAYER_KEYS
        if unknown:
            raise ValueError(f"Unknown prayer(s) in audio config: {sorted(unknown)}")
        return v


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
    bluetooth: BluetoothConfig = Field(default_factory=BluetoothConfig)


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
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    reliability: ReliabilityConfig = Field(default_factory=ReliabilityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def load_config(path: str | Path) -> Config:
    data = yaml.safe_load(Path(path).read_text())
    return Config.model_validate(data)
