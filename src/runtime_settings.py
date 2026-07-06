"""Mutable runtime settings overridden by CLI arguments."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.config import (
    AUDIO_DIR,
    DEFAULT_WORKERS,
    DISCOVERY_SLEEP_MAX,
    DISCOVERY_SLEEP_MIN,
    MAX_RETRIES,
    MAX_WORKERS,
    RETRY_BACKOFF,
    SLEEP_MAX,
    SLEEP_MIN,
)


@dataclass
class RuntimeSettings:
    sleep_min: float = SLEEP_MIN
    sleep_max: float = SLEEP_MAX
    discovery_sleep_min: float = DISCOVERY_SLEEP_MIN
    discovery_sleep_max: float = DISCOVERY_SLEEP_MAX
    max_retries: int = MAX_RETRIES
    retry_backoff: float = RETRY_BACKOFF
    check_robots: bool = True
    workers: int = DEFAULT_WORKERS
    download_audio: bool = False
    audio_dir: Path = field(default_factory=lambda: AUDIO_DIR)


settings = RuntimeSettings()


def configure(
    *,
    sleep_min: float | None = None,
    sleep_max: float | None = None,
    discovery_sleep_min: float | None = None,
    discovery_sleep_max: float | None = None,
    max_retries: int | None = None,
    retry_backoff: float | None = None,
    check_robots: bool | None = None,
    workers: int | None = None,
    download_audio: bool | None = None,
    audio_dir: Path | str | None = None,
) -> None:
    """Apply CLI overrides to the active runtime settings."""
    if sleep_min is not None:
        settings.sleep_min = sleep_min
    if sleep_max is not None:
        settings.sleep_max = sleep_max
    if discovery_sleep_min is not None:
        settings.discovery_sleep_min = discovery_sleep_min
    if discovery_sleep_max is not None:
        settings.discovery_sleep_max = discovery_sleep_max
    if max_retries is not None:
        settings.max_retries = max_retries
    if retry_backoff is not None:
        settings.retry_backoff = retry_backoff
    if check_robots is not None:
        settings.check_robots = check_robots
    if workers is not None:
        settings.workers = max(1, min(workers, MAX_WORKERS))
    if download_audio is not None:
        settings.download_audio = download_audio
    if audio_dir is not None:
        settings.audio_dir = Path(audio_dir)
