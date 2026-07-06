"""Parse Cambridge English-Chinese dictionary HTML into structured data."""

from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from src.fetcher import build_url, resolve_media_url

logger = logging.getLogger(__name__)

CEFR_PATTERN = re.compile(r"\b(A1|A2|B1|B2|C1|C2)\b")


def parse_page(word: str, html: str) -> dict[str, Any] | None:
    """
    Parse dictionary HTML into a structured entry.

    Returns None if the page has no valid dictionary content.
    """
    soup = BeautifulSoup(html, "lxml")
    if not soup.select_one("div.di-body"):
        return None

    entries: list[dict[str, Any]] = []
    entry_blocks = soup.select(
        "div.pr.entry-body__el, div.entry-body__el, "
        "div.pr.idiom-block, div.pr.phrase-block, div.pr.dphrase-block, "
        "span.phrase-di-block, span.dphrase-di-block"
    )

    for entry_el in entry_blocks:
        try:
            parsed_entry = _parse_entry_block(entry_el)
            if parsed_entry and parsed_entry.get("senses"):
                entries.append(parsed_entry)
        except Exception as exc:
            logger.warning("Failed to parse entry block for %s: %s", word, exc)

    if not entries:
        for sense_body in soup.select("div.di-body div.sense-body.dsense_b, div.di-body div.sense-body"):
            try:
                senses = _parse_sense_body(sense_body)
                if senses:
                    entries.append(
                        {
                            "pos": _infer_pos_from_context(sense_body),
                            "ipa_uk": "",
                            "ipa_us": "",
                            "audio_uk": "",
                            "audio_us": "",
                            "senses": senses,
                        }
                    )
            except Exception as exc:
                logger.warning("Failed fallback sense parse for %s: %s", word, exc)

    if not entries:
        return None

    return {
        "word": word.strip().lower(),
        "url": build_url(word),
        "entries": entries,
    }


def _parse_entry_block(entry_el: Tag) -> dict[str, Any] | None:
    pos = _safe_text(entry_el.select_one(".posgram, .posgram.dpos-g"))
    if not pos:
        pos_spans = entry_el.select("span.pos.dpos, .di-info span.pos.dpos")
        if pos_spans:
            pos = ", ".join(_safe_text(span) for span in pos_spans if _safe_text(span))

    ipa_uk = _extract_ipa(entry_el, "uk")
    ipa_us = _extract_ipa(entry_el, "us")
    audio_uk = _extract_audio_url(entry_el, "uk")
    audio_us = _extract_audio_url(entry_el, "us")

    senses: list[dict[str, Any]] = []
    for sense_body in entry_el.select("div.sense-body.dsense_b, div.sense-body"):
        try:
            parsed_senses = _parse_sense_body(sense_body)
            senses.extend(parsed_senses)
        except Exception as exc:
            logger.debug("Sense body parse error: %s", exc)

    if not senses:
        senses = _parse_phrase_di_body(entry_el)

    if not senses:
        return None

    return {
        "pos": pos,
        "ipa_uk": ipa_uk,
        "ipa_us": ipa_us,
        "audio_uk": audio_uk,
        "audio_us": audio_us,
        "senses": senses,
    }


def _parse_phrase_di_body(entry_el: Tag) -> list[dict[str, Any]]:
    """Parse phrase template pages where def-blocks sit in phrase-di-body."""
    senses: list[dict[str, Any]] = []
    phrase_body = entry_el.select_one(
        "span.phrase-di-body, span.dphrase-di-body, .phrase-di-body, .dphrase-di-body"
    )
    if not phrase_body:
        return senses

    for block in phrase_body.select("div.def-block.ddef_block, div.def-block"):
        try:
            sense = _parse_def_block(block, guideword="")
            if sense:
                senses.append(sense)
        except Exception as exc:
            logger.debug("Phrase def-block parse error: %s", exc)

    return senses


def _parse_sense_body(sense_body: Tag) -> list[dict[str, Any]]:
    guideword = ""
    guideword_el = sense_body.find_previous("div", class_=lambda c: c and "dsense_h" in c)
    if guideword_el:
        guideword = _safe_text(guideword_el.select_one(".guideword"))

    senses: list[dict[str, Any]] = []
    def_blocks = sense_body.select("div.def-block.ddef_block, div.def-block")

    if not def_blocks:
        return senses

    for block in def_blocks:
        try:
            sense = _parse_def_block(block, guideword)
            if sense:
                senses.append(sense)
        except Exception as exc:
            logger.debug("Def-block parse error: %s", exc)

    return senses


def _parse_def_block(block: Tag, guideword: str) -> dict[str, Any] | None:
    english_defs: list[str] = []
    chinese_defs: list[str] = []
    examples: list[dict[str, str]] = []

    for def_el in block.select(".ddef_h .def.ddef_d.db, .ddef_h .def"):
        text = _extract_clean_text(def_el)
        if text:
            english_defs.append(text)

    def_body = block.select_one(".def-body.ddef_b, .def-body")
    if def_body:
        for trans in def_body.find_all("span", class_=lambda c: c and "trans" in c, recursive=False):
            if trans.find_parent(class_=lambda c: c and "examp" in c):
                continue
            text = _extract_clean_text(trans)
            if text:
                chinese_defs.append(text)

    for examp in block.select("div.examp.dexamp, li.examp.dexamp, div.examp"):
        try:
            example = _parse_example(examp)
            if example:
                examples.append(example)
        except Exception as exc:
            logger.debug("Example parse error: %s", exc)

    if not english_defs and not chinese_defs and not examples:
        return None

    cefr = _extract_cefr(block)

    return {
        "guideword": guideword,
        "cefr": cefr,
        "english_definitions": english_defs,
        "chinese_definitions": chinese_defs,
        "examples": examples,
    }


def _parse_example(examp: Tag) -> dict[str, str] | None:
    english_el = examp.select_one("span.eg.deg, span.eg")
    chinese_el = examp.select_one("span.trans.dtrans.dtrans-se.hdb.break-cj, span.trans")

    english = _extract_clean_text(english_el)
    chinese = _extract_clean_text(chinese_el)

    if not english and not chinese:
        return None

    return {"english": english, "chinese": chinese}


def _extract_clean_text(element: Tag | None) -> str:
    """Extract text while flattening inline cross-reference links."""
    if element is None:
        return ""

    fragment = BeautifulSoup(str(element), "lxml")
    root = fragment.find(True)
    if root is None:
        return ""

    for anchor in root.select("a.query, a.Ref"):
        anchor.replace_with(anchor.get_text(" ", strip=True))

    return _safe_text(root)


def _extract_audio_url(entry_el: Tag, region: str) -> str:
    source = entry_el.select_one(
        f".dpron-i.{region} source[type='audio/mpeg'], "
        f".dpron-i.{region} .daud source, "
        f".dpron-i.{region} source"
    )
    if not source or not source.get("src"):
        return ""
    return resolve_media_url(source["src"].strip())


def _extract_ipa(entry_el: Tag, region: str) -> str:
    pron_el = entry_el.select_one(f".dpron-i.{region} .pron.dpron, .dpron-i.{region} .pron")
    if not pron_el:
        return ""
    text = _safe_text(pron_el)
    return text.strip("/").strip()


def _extract_cefr(block: Tag) -> str:
    info_el = block.select_one(".ddef_h .ddef-info, .ddef_h .def-info")
    if not info_el:
        return ""
    match = CEFR_PATTERN.search(_safe_text(info_el))
    return match.group(1) if match else ""


def _infer_pos_from_context(sense_body: Tag) -> str:
    container = sense_body.find_parent(
        ["div", "span"],
        class_=lambda c: c
        and any(
            token in c
            for token in (
                "entry-body__el",
                "idiom-block",
                "phrase-block",
                "phrase-di-block",
                "di-body",
            )
        ),
    )
    if not container:
        return ""
    return _safe_text(container.select_one(".posgram, .posgram.dpos-g, span.pos.dpos"))


def _safe_text(element: Tag | None) -> str:
    if element is None:
        return ""
    return " ".join(element.get_text(" ", strip=True).split())
