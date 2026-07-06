"""Download pronunciation audio files for crawled entries."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.fetcher import fetch_binary, resolve_media_url
from src.runtime_settings import settings

logger = logging.getLogger(__name__)


def download_word_audio(result: dict[str, Any], audio_dir: Path | None = None) -> list[Path]:
    """
    Download UK/US MP3 files referenced in a parsed entry.

    Returns:
        List of saved file paths.
    """
    target_dir = audio_dir or settings.audio_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    word = result.get("word", "unknown")
    saved: list[Path] = []
    seen_urls: set[str] = set()

    for entry in result.get("entries", []):
        for region in ("uk", "us"):
            url = entry.get(f"audio_{region}", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            absolute_url = resolve_media_url(url)
            content, error = fetch_binary(absolute_url)
            if error or content is None:
                logger.warning("Audio download failed for %s (%s): %s", word, region, error)
                continue

            suffix = Path(absolute_url).suffix or ".mp3"
            filename = f"{word}_{region}{suffix}"
            dest = target_dir / filename
            dest.write_bytes(content)
            saved.append(dest)
            logger.info("Saved audio: %s", dest)

    return saved


def download_results_audio(results: list[dict[str, Any]], audio_dir: Path | None = None) -> int:
    """Download audio for all successful crawl results. Returns file count."""
    count = 0
    for result in results:
        count += len(download_word_audio(result, audio_dir))
    return count
