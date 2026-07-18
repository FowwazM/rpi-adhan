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


def test_stop_is_safe_before_start(tmp_path):
    # Calling stop() without a prior start() must not deadlock or raise;
    # it should release the bound socket and return.
    server = MediaHTTPServer(tmp_path, host="127.0.0.1", port=0)
    server.stop()
