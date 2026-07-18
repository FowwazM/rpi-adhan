from __future__ import annotations

import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
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
