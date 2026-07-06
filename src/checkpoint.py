"""Checkpoint helpers for long-running bulk crawls."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import BULK_RESULTS_FILE, CACHE_DIR, CHECKPOINT_FILE


def load_checkpoint() -> dict[str, Any] | None:
    """Load crawl checkpoint data if it exists."""
    if not CHECKPOINT_FILE.exists():
        return None
    return json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))


def save_checkpoint(
    *,
    completed_words: list[str],
    results: list[dict[str, Any]],
    total_words: int,
    errors: list[dict[str, str]],
) -> None:
    """Persist crawl progress and partial results."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    BULK_RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "total_words": total_words,
        "completed_count": len(completed_words),
        "error_count": len(errors),
        "completed_words": completed_words,
        "errors": errors,
    }
    CHECKPOINT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    BULK_RESULTS_FILE.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_checkpoint() -> None:
    """Remove checkpoint files after a successful full crawl."""
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
    if BULK_RESULTS_FILE.exists():
        BULK_RESULTS_FILE.unlink()


def load_bulk_results() -> list[dict[str, Any]]:
    """Load partial bulk crawl results from checkpoint storage."""
    if not BULK_RESULTS_FILE.exists():
        return []
    data = json.loads(BULK_RESULTS_FILE.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []
