"""Tests for fetcher utilities."""

from src.fetcher import build_url, normalize_word, resolve_media_url


def test_normalize_word():
    assert normalize_word("  Industrial Engineering ") == "industrial-engineering"


def test_build_url():
    url = build_url("hello")
    assert url.endswith("/english-chinese-simplified/hello")


def test_resolve_media_url():
    assert resolve_media_url("/media/test.mp3").startswith("https://dictionary.cambridge.org/")
    assert resolve_media_url("https://example.com/a.mp3") == "https://example.com/a.mp3"
