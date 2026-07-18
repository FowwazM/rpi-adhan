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
