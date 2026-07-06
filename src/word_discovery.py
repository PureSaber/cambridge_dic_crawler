"""Discover all words from the Cambridge browse index."""

from __future__ import annotations

import json
import logging
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from src.config import (
    BROWSE_BASE_URL,
    BROWSE_PATH_PREFIX,
    CACHE_DIR,
    DICT_PATH_PATTERN,
    WORD_LIST_FILE,
)
from src.fetcher import fetch_browse_page, normalize_word

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, int, int], None]

# Browse segments that usually group idioms/phrases rather than headword lists.
_IDIOM_INDEX_MARKERS = (
    "-of",
    "-by-",
    "-in-",
    "-on-",
    "-from-",
    "-with-",
    "etc-",
    "-something",
    "-someone",
)


def load_word_list(path: str | Path | None = None) -> list[str] | None:
    """Load a previously saved word list, or None if missing."""
    file_path = Path(path) if path is not None else WORD_LIST_FILE

    if not file_path.exists():
        return None

    data = json.loads(file_path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "words" in data:
        return list(data["words"])
    if isinstance(data, list):
        return list(data)
    return None


def save_word_list(words: list[str], *, letters: list[str] | None = None) -> None:
    """Persist discovered words for reuse and resume."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "discovered_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(words),
        "letters": letters,
        "words": words,
    }
    WORD_LIST_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def discover_all_words(
    *,
    letters: list[str] | None = None,
    limit: int | None = None,
    on_progress: ProgressCallback | None = None,
) -> list[str]:
    """
    Crawl the Cambridge browse index and collect every dictionary headword.

    Browse pages are visited in priority order so regular headword pages are
    scanned before idiom/phrase index pages when possible.
    """
    start_urls = _build_start_urls(letters)
    visited_browse: set[str] = set()
    queue: deque[str] = deque(start_urls)
    words: set[str] = set()

    while queue:
        browse_url = queue.popleft()
        if browse_url in visited_browse:
            continue
        visited_browse.add(browse_url)

        html, error = fetch_browse_page(browse_url)
        if error or not html:
            logger.warning("Browse failed for %s: %s", browse_url, error)
            if on_progress:
                on_progress(f"Browse failed: {browse_url} ({error})", len(words), len(visited_browse))
            continue

        child_browse, page_words = _parse_browse_page(browse_url, html)
        words.update(page_words)

        children = [
            child_url
            for child_url in child_browse
            if child_url not in visited_browse and _is_child_browse_page(browse_url, child_url)
        ]
        _enqueue_children(queue, children)

        if on_progress:
            on_progress(
                f"Scanned {browse_url} (+{len(page_words)} words)",
                len(words),
                len(visited_browse),
            )

        if limit and len(words) >= limit:
            break

    result = _sort_words_for_export(words)
    if limit:
        result = result[:limit]
    return result


def _build_start_urls(letters: list[str] | None) -> list[str]:
    if letters:
        return [f"{BROWSE_BASE_URL}/{letter.strip().lower()}/" for letter in letters if letter.strip()]

    root_url = f"{BROWSE_BASE_URL}/"
    html, error = fetch_browse_page(root_url)
    if error or not html:
        raise ValueError(f"Failed to load browse index: {error}")

    browse_links, _ = _parse_browse_page(root_url, html)
    letter_urls = [
        url
        for url in sorted(browse_links)
        if url != root_url and _is_child_browse_page(root_url, url)
    ]
    if not letter_urls:
        raise ValueError("No browse letter pages found")
    return letter_urls


def _parse_browse_page(current_url: str, html: str) -> tuple[set[str], set[str]]:
    soup = BeautifulSoup(html, "lxml")
    browse_links: set[str] = set()
    words: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        absolute = urljoin(current_url, anchor["href"])
        browse_url = _normalize_browse_url(absolute)
        if browse_url:
            browse_links.add(browse_url)

        word = _extract_word_slug(anchor["href"])
        if word:
            words.add(word)

    return browse_links, words


def _normalize_browse_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != "dictionary.cambridge.org":
        return None
    if not parsed.path.startswith(BROWSE_PATH_PREFIX):
        return None
    return f"https://dictionary.cambridge.org{parsed.path.rstrip('/')}/"


def _extract_word_slug(href: str) -> str | None:
    if DICT_PATH_PATTERN not in href:
        return None
    slug = href.split(DICT_PATH_PATTERN, 1)[-1].split("?")[0].split("#")[0].strip("/")
    if not slug or "/" in slug:
        return None
    return normalize_word(slug)


def _is_child_browse_page(parent_url: str, child_url: str) -> bool:
    parent = parent_url.rstrip("/")
    child = child_url.rstrip("/")
    if child == parent:
        return False
    return child.startswith(parent + "/")


def _browse_url_priority(url: str) -> tuple[int, int, str]:
    """
    Lower sort keys are visited earlier.

    Prefer word-prefix browse pages (e.g. /a/aberrant/) over idiom index pages
    (e.g. /a/a-and-e/).
    """
    parts = urlparse(url).path.strip("/").split("/")
    segment = parts[-1] if parts else ""
    letter = parts[2] if len(parts) > 2 else ""

    priority = 0
    if letter and segment.startswith(f"{letter}-"):
        priority += 20
    if any(marker in segment for marker in _IDIOM_INDEX_MARKERS):
        priority += 10
    if segment.count("-") >= 3:
        priority += 5
    if segment.isalpha() and len(segment) >= 4:
        priority -= 5

    return (priority, len(segment), url)


def _word_priority(word: str) -> tuple[int, int, str]:
    """Prefer simple headwords when applying --limit after discovery."""
    return (word.count("-"), len(word), word)


def _sort_words_for_export(words: set[str]) -> list[str]:
    return sorted(words, key=_word_priority)


def _enqueue_children(queue: deque[str], children: list[str]) -> None:
    """Enqueue child browse pages: higher-priority pages go to the front."""
    ordered = sorted(children, key=_browse_url_priority)
    high_priority = [url for url in ordered if _browse_url_priority(url)[0] < 10]
    low_priority = [url for url in ordered if _browse_url_priority(url)[0] >= 10]

    for url in reversed(high_priority):
        queue.appendleft(url)
    queue.extend(low_priority)
