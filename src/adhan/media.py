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
