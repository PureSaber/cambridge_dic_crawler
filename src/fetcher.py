"""HTTP fetching with random delays, retries, and User-Agent rotation."""

from __future__ import annotations

import logging
import random
import time
from urllib.parse import quote, urljoin

import requests

from src.config import (
    BASE_URL,
    CAMBRIDGE_ORIGIN,
    DEFAULT_HEADERS,
    REQUEST_TIMEOUT,
    USER_AGENTS,
)
from src.robots import is_allowed
from src.runtime_settings import settings

logger = logging.getLogger(__name__)


def normalize_word(word: str) -> str:
    """Normalize a word for URL construction."""
    return word.strip().lower().replace(" ", "-")


def build_url(word: str) -> str:
    """Build the Cambridge dictionary URL for a word."""
    slug = normalize_word(word)
    return f"{BASE_URL}/{quote(slug, safe='-')}"


def resolve_media_url(relative_or_absolute: str) -> str:
    """Convert a Cambridge media path to an absolute URL."""
    if relative_or_absolute.startswith(("http://", "https://")):
        return relative_or_absolute
    return urljoin(CAMBRIDGE_ORIGIN, relative_or_absolute)


def _random_headers() -> dict[str, str]:
    headers = DEFAULT_HEADERS.copy()
    headers["User-Agent"] = random.choice(USER_AGENTS)
    return headers


def fetch_html(
    url: str,
    *,
    sleep_min: float | None = None,
    sleep_max: float | None = None,
) -> tuple[str | None, str | None]:
    """
    Fetch arbitrary URL HTML with random delay, retries, and User-Agent.

    Returns:
        Tuple of (html_content, error_message). On success error_message is None.
    """
    if not is_allowed(url):
        return None, "Blocked by robots.txt"

    min_delay = settings.sleep_min if sleep_min is None else sleep_min
    max_delay = settings.sleep_max if sleep_max is None else sleep_max
    time.sleep(random.uniform(min_delay, max_delay))

    last_error = "Unknown error"
    for attempt in range(1, settings.max_retries + 1):
        try:
            response = requests.get(
                url,
                headers=_random_headers(),
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            last_error = f"Request failed: {exc}"
            logger.warning("Fetch attempt %s/%s failed for %s: %s", attempt, settings.max_retries, url, exc)
        else:
            if response.status_code != 200:
                last_error = f"HTTP {response.status_code}"
                logger.warning(
                    "Fetch attempt %s/%s got %s for %s",
                    attempt,
                    settings.max_retries,
                    response.status_code,
                    url,
                )
            elif not response.text or not response.text.strip():
                last_error = "Empty response body"
            else:
                return response.text, None

        if attempt < settings.max_retries:
            backoff = settings.retry_backoff * attempt
            logger.info("Retrying %s in %.1fs", url, backoff)
            time.sleep(backoff)

    return None, last_error


def fetch_binary(
    url: str,
    *,
    sleep_min: float = 0.3,
    sleep_max: float = 1.0,
) -> tuple[bytes | None, str | None]:
    """Download binary content (e.g. MP3) with a short delay."""
    if not is_allowed(url):
        return None, "Blocked by robots.txt"

    time.sleep(random.uniform(sleep_min, sleep_max))
    last_error = "Unknown error"
    for attempt in range(1, settings.max_retries + 1):
        try:
            response = requests.get(
                url,
                headers=_random_headers(),
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            last_error = f"Request failed: {exc}"
        else:
            if response.status_code != 200:
                last_error = f"HTTP {response.status_code}"
            elif not response.content:
                last_error = "Empty response body"
            else:
                return response.content, None

        if attempt < settings.max_retries:
            time.sleep(settings.retry_backoff * attempt)

    return None, last_error


def fetch_page(word: str) -> tuple[str | None, str | None]:
    """Fetch dictionary page HTML for a word."""
    return fetch_html(build_url(word))


def fetch_browse_page(url: str) -> tuple[str | None, str | None]:
    """Fetch a Cambridge browse index page with discovery delays."""
    return fetch_html(
        url,
        sleep_min=settings.discovery_sleep_min,
        sleep_max=settings.discovery_sleep_max,
    )
