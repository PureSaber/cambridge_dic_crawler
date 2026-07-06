"""Load word lists from CLI args, files, or web pages."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup

from src.config import DEFAULT_HEADERS, DICT_PATH_PATTERN, REQUEST_TIMEOUT, USER_AGENTS
from src.fetcher import normalize_word


def load_words_from_args(words: list[str]) -> list[str]:
    """Normalize words passed directly on the command line."""
    return _dedupe([normalize_word(word) for word in words if word.strip()])


def load_words_from_file(path: str | Path) -> list[str]:
    """Load words from a text or JSON file."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Word file not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix == ".json":
        return _load_words_from_json(file_path)
    return _load_words_from_text(file_path)


def load_words_from_url(url: str) -> list[str]:
    """Fetch a web page and extract Cambridge dictionary words from links."""
    headers = DEFAULT_HEADERS.copy()
    headers["User-Agent"] = random.choice(USER_AGENTS)

    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"Failed to fetch URL: {exc}") from exc

    soup = BeautifulSoup(response.text, "lxml")
    words: list[str] = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if DICT_PATH_PATTERN in href:
            slug = href.split(DICT_PATH_PATTERN, 1)[-1].split("?")[0].split("#")[0]
            slug = unquote(slug).strip("/")
            if slug:
                words.append(normalize_word(slug))
                continue

        text = link.get_text(strip=True)
        if text and re.fullmatch(r"[A-Za-z][A-Za-z\s\-']{0,49}", text):
            words.append(normalize_word(text))

    parsed = urlparse(url)
    if parsed.path and DICT_PATH_PATTERN in parsed.path:
        slug = parsed.path.split(DICT_PATH_PATTERN, 1)[-1].strip("/")
        if slug:
            words.insert(0, normalize_word(slug))

    result = _dedupe(words)
    if not result:
        raise ValueError("No words found on the page")
    return result


def _load_words_from_text(file_path: Path) -> list[str]:
    words: list[str] = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        words.append(normalize_word(line))
    return _dedupe(words)


def _load_words_from_json(file_path: Path) -> list[str]:
    data = json.loads(file_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return _dedupe([normalize_word(str(item)) for item in data if str(item).strip()])
    if isinstance(data, dict) and "words" in data:
        return _dedupe([normalize_word(str(item)) for item in data["words"] if str(item).strip()])
    raise ValueError("JSON file must be a list of words or an object with a 'words' key")


def _dedupe(words: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for word in words:
        if word and word not in seen:
            seen.add(word)
            result.append(word)
    return result
