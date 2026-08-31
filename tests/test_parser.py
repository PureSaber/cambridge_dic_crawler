"""Tests for Cambridge dictionary HTML parser."""

from pathlib import Path

from src.parser import parse_page

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_regular_entry():
    result = parse_page("testword", _load("entry.html"))
    assert result is not None
    assert result["word"] == "testword"
    assert result["display_word"] == "testword"
    entry = result["entries"][0]
    assert entry["pos"] == "noun"
    assert entry["ipa_uk"] == "test"
    assert entry["audio_uk"].endswith("/media/english-chinese-simplified/uk_pron/t/test.mp3")
    assert entry["audio_us"].endswith("/media/english-chinese-simplified/us_pron/t/test.mp3")
    sense = entry["senses"][0]
    assert sense["cefr"] == "B1"
    assert sense["english_definitions"] == ["a short test definition"]
    assert sense["chinese_definitions"] == ["测试释义"]
    assert sense["examples"][0]["english"] == "This is a sample sentence."


def test_parse_idiom_block():
    result = parse_page("good-idiom", _load("idiom.html"))
    assert result is not None
    assert result["entries"][0]["pos"] == "idiom"
    assert result["entries"][0]["senses"][0]["chinese_definitions"] == ["好的习语"]


def test_parse_phrase_di_block():
    result = parse_page("barrage-of", _load("phrase.html"))
    assert result is not None
    assert result["entries"][0]["pos"] == "phrase"
    assert result["entries"][0]["senses"][0]["english_definitions"] == ["a great number of things"]


def test_parse_missing_content_returns_none():
    assert parse_page("missing", "<html><body></body></html>") is None


def test_preserves_display_headword_and_inline_word_boundaries():
    result = parse_page("may-might-as-well", _load("text_fidelity.html"))
    assert result is not None
    assert result["word"] == "may-might-as-well"
    assert result["display_word"] == "may/might as well"
    assert result["entries"][0]["ipa_us"] == "ˈlɑː.t̬ɚ.i"

    sense = result["entries"][0]["senses"][0]
    assert sense["english_definitions"] == [
        "used to suggest doing something, often when there is nothing better to do"
    ]
    assert sense["chinese_definitions"] == ["（反正也没有更好的办法）要不就…"]
    assert sense["examples"] == [
        {
            "english": "His story took some believing (= was difficult to believe).",
            "chinese": "他的故事令人难以置信。",
        },
        {
            "english": "I can't see her accepting (= I don't think she will accept) the job.",
            "chinese": "我认为她不会接受。",
        },
    ]
