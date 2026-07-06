"""Tests for browse discovery helpers."""

from src.word_discovery import _browse_url_priority, _sort_words_for_export


def test_browse_priority_prefers_word_prefix_pages():
    word_page = "https://dictionary.cambridge.org/browse/english-chinese-simplified/a/aberrant/"
    idiom_page = "https://dictionary.cambridge.org/browse/english-chinese-simplified/a/a-and-e/"
    assert _browse_url_priority(word_page) < _browse_url_priority(idiom_page)


def test_word_priority_prefers_simple_headwords():
    words = {"bird-s-eye-view", "ability", "bit-of", "abandon"}
    ordered = _sort_words_for_export(words)
    assert ordered.index("abandon") < ordered.index("bird-s-eye-view")
    assert ordered.index("ability") < ordered.index("bit-of")
