"""Lightweight robots.txt compliance check."""

from __future__ import annotations

import logging
from functools import lru_cache
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from src.config import DEFAULT_HEADERS, REQUEST_TIMEOUT, USER_AGENTS
from src.runtime_settings import settings

import random

logger = logging.getLogger(__name__)

ROBOTS_URL = "https://dictionary.cambridge.org/robots.txt"


@lru_cache(maxsize=1)
def _load_robot_parser() -> RobotFileParser | None:
    headers = DEFAULT_HEADERS.copy()
    headers["User-Agent"] = random.choice(USER_AGENTS)
    try:
        response = requests.get(ROBOTS_URL, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Could not fetch robots.txt: %s", exc)
        return None

    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    return parser


def is_allowed(url: str, user_agent: str | None = None) -> bool:
    """Return whether fetching the URL is allowed by robots.txt."""
    if not settings.check_robots:
        return True

    parser = _load_robot_parser()
    if parser is None:
        return True

    agent = user_agent or random.choice(USER_AGENTS)
    allowed = parser.can_fetch(agent, url)
    if not allowed:
        logger.warning("robots.txt disallows fetching: %s", url)
    return allowed


def filter_disallowed_urls(urls: list[str]) -> list[str]:
    """Drop URLs blocked by robots.txt."""
    return [url for url in urls if is_allowed(url)]
