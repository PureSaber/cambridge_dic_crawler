"""Orchestrate fetching and parsing for a list of words."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable

from src.audio_downloader import download_word_audio
from src.checkpoint import clear_checkpoint, load_bulk_results, load_checkpoint, save_checkpoint
from src.config import CHECKPOINT_EVERY, LOG_DIR
from src.fetcher import build_url, fetch_page
from src.parser import parse_page
from src.runtime_settings import settings

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, int, int, int, int], None]
ExportCallback = Callable[[list[dict[str, Any]]], None]


def crawl_words(words: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Crawl dictionary entries for the given words."""
    return crawl_words_bulk(words, checkpoint=False)


def crawl_words_bulk(
    words: list[str],
    *,
    resume: bool = False,
    checkpoint: bool = False,
    save_every: int = CHECKPOINT_EVERY,
    workers: int | None = None,
    on_progress: ProgressCallback | None = None,
    on_export: ExportCallback | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Crawl dictionary entries with optional checkpoint resume and concurrency."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    worker_count = workers if workers is not None else settings.workers

    state = _CrawlState(
        words=words,
        checkpoint=checkpoint,
        save_every=save_every,
        on_progress=on_progress,
        on_export=on_export,
    )

    if resume and checkpoint:
        checkpoint_data = load_checkpoint()
        if checkpoint_data:
            state.completed_words = set(checkpoint_data.get("completed_words", []))
            state.errors = list(checkpoint_data.get("errors", []))
        state.successes = load_bulk_results()

    pending = [word for word in words if word not in state.completed_words]
    if not pending:
        return state.successes, state.errors

    if worker_count <= 1:
        for word in pending:
            parsed, error = _process_word(word)
            state.record(word, parsed, error)
    else:
        logger.info("Using %s concurrent workers", worker_count)
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {executor.submit(_process_word, word): word for word in pending}
            for future in as_completed(futures):
                word = futures[future]
                try:
                    parsed, error = future.result()
                except Exception as exc:
                    parsed, error = None, _make_error_record(word, build_url(word), f"Worker error: {exc}")
                    logger.exception("Worker failed for %s", word)
                state.record(word, parsed, error)

    if state.newly_processed > 0 and checkpoint:
        state.persist()

    if checkpoint and len(state.completed_words) >= len(words):
        clear_checkpoint()

    return _sort_results(state.successes, words), state.errors


class _CrawlState:
    def __init__(
        self,
        *,
        words: list[str],
        checkpoint: bool,
        save_every: int,
        on_progress: ProgressCallback | None,
        on_export: ExportCallback | None,
    ) -> None:
        self.words = words
        self.total = len(words)
        self.checkpoint = checkpoint
        self.save_every = save_every
        self.on_progress = on_progress
        self.on_export = on_export
        self.lock = threading.Lock()
        self.completed_words: set[str] = set()
        self.successes: list[dict[str, Any]] = []
        self.errors: list[dict[str, str]] = []
        self.newly_processed = 0

    def record(
        self,
        word: str,
        parsed: dict[str, Any] | None,
        error: dict[str, str] | None,
    ) -> None:
        with self.lock:
            self.newly_processed += 1
            self.completed_words.add(word)

            if error:
                self.errors.append(error)
                _log_error(error)
            elif parsed:
                self.successes.append(parsed)
                if settings.download_audio:
                    download_word_audio(parsed)

            if self.on_progress:
                self.on_progress(
                    word,
                    len(self.completed_words),
                    self.total,
                    len(self.successes),
                    len(self.errors),
                )

            if (
                self.checkpoint
                and self.save_every > 0
                and len(self.completed_words) % self.save_every == 0
            ):
                self._persist_locked()

    def persist(self) -> None:
        with self.lock:
            self._persist_locked()

    def _persist_locked(self) -> None:
        save_checkpoint(
            completed_words=sorted(self.completed_words),
            results=self.successes,
            total_words=self.total,
            errors=self.errors,
        )
        if self.on_export:
            try:
                self.on_export(_sort_results(self.successes, self.words))
            except Exception as exc:
                logger.warning("Incremental export failed: %s", exc)


def _process_word(word: str) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    url = build_url(word)
    html, fetch_error = fetch_page(word)

    if fetch_error:
        return None, _make_error_record(word, url, fetch_error)

    try:
        parsed = parse_page(word, html)
    except Exception as exc:
        logger.exception("Unexpected parse failure for %s", word)
        return None, _make_error_record(word, url, f"Parse error: {exc}")

    if not parsed:
        return None, _make_error_record(word, url, "No definitions found")

    return parsed, None


def _sort_results(results: list[dict[str, Any]], word_order: list[str]) -> list[dict[str, Any]]:
    order = {word: index for index, word in enumerate(word_order)}
    return sorted(results, key=lambda item: order.get(item.get("word", ""), len(word_order)))


def _make_error_record(word: str, url: str, reason: str) -> dict[str, str]:
    return {
        "word": word,
        "url": url,
        "reason": reason,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


def _log_error(record: dict[str, str]) -> None:
    logger.warning(
        "Crawl failed word=%s url=%s reason=%s",
        record["word"],
        record["url"],
        record["reason"],
    )
