"""Export crawl results to DataFrame, CSV, and JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import OUTPUT_DIR


def to_dataframe(results: list[dict[str, Any]]) -> pd.DataFrame:
    """Flatten structured results into a Pandas DataFrame."""
    rows: list[dict[str, Any]] = []

    for result in results:
        word = result.get("word", "")
        display_word = result.get("display_word", word.replace("-", " "))
        url = result.get("url", "")

        for entry in result.get("entries", []):
            pos = entry.get("pos", "")
            ipa_uk = entry.get("ipa_uk", "")
            ipa_us = entry.get("ipa_us", "")
            audio_uk = entry.get("audio_uk", "")
            audio_us = entry.get("audio_us", "")

            for sense_index, sense in enumerate(entry.get("senses", []), start=1):
                rows.append(
                    {
                        "word": word,
                        "display_word": display_word,
                        "url": url,
                        "pos": pos,
                        "ipa_uk": ipa_uk,
                        "ipa_us": ipa_us,
                        "audio_uk": audio_uk,
                        "audio_us": audio_us,
                        "sense_index": sense_index,
                        "guideword": sense.get("guideword", ""),
                        "cefr": sense.get("cefr", ""),
                        "english_definitions": "; ".join(sense.get("english_definitions", [])),
                        "chinese_definitions": "; ".join(sense.get("chinese_definitions", [])),
                        "examples": json.dumps(sense.get("examples", []), ensure_ascii=False),
                    }
                )

    if not rows:
        return pd.DataFrame(
            columns=[
                "word",
                "display_word",
                "url",
                "pos",
                "ipa_uk",
                "ipa_us",
                "audio_uk",
                "audio_us",
                "sense_index",
                "guideword",
                "cefr",
                "english_definitions",
                "chinese_definitions",
                "examples",
            ]
        )

    return pd.DataFrame(rows)


def export_results(
    results: list[dict[str, Any]],
    csv_path: str | Path | None = None,
    json_path: str | Path | None = None,
) -> tuple[pd.DataFrame, Path, Path]:
    """
    Export results to CSV and JSON files.

    Returns:
        Tuple of (dataframe, csv_path, json_path).
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    resolved_csv = Path(csv_path) if csv_path else OUTPUT_DIR / "output.csv"
    resolved_json = Path(json_path) if json_path else OUTPUT_DIR / "output.json"

    if resolved_json.suffix.lower() != ".json":
        resolved_json = resolved_json.with_suffix(".json")

    df = to_dataframe(results)
    df.to_csv(resolved_csv, index=False, encoding="utf-8-sig")

    with resolved_json.open("w", encoding="utf-8") as json_file:
        json.dump(results, json_file, ensure_ascii=False, indent=2)

    return df, resolved_csv, resolved_json
