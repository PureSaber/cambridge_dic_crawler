"""Tests for concurrent crawl orchestration."""

from unittest.mock import patch

from src.crawler import crawl_words_bulk


def test_concurrent_crawl_collects_results():
    words = ["alpha", "beta", "gamma"]

    def fake_process(word: str):
        return {"word": word, "url": f"http://example/{word}", "entries": []}, None

    with patch("src.crawler._process_word", side_effect=fake_process):
        results, errors = crawl_words_bulk(words, workers=3)

    assert len(results) == 3
    assert errors == []
    assert [item["word"] for item in results] == words
