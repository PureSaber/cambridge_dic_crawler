"""Audit bulk crawl completeness and download any missing audio files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.audio_downloader import download_word_audio
from src.config import AUDIO_DIR, OUTPUT_DIR, WORD_LIST_FILE
from src.fetcher import resolve_media_url
from src.logging_config import setup_logging


def load_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def expected_audio_files(result: dict) -> list[Path]:
    word = result.get("word", "unknown")
    paths: list[Path] = []
    seen_urls: set[str] = set()

    for entry in result.get("entries", []):
        for region in ("uk", "us"):
            url = entry.get(f"audio_{region}", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            suffix = Path(resolve_media_url(url)).suffix or ".mp3"
            paths.append(AUDIO_DIR / f"{word}_{region}{suffix}")
    return paths


def audit(
    word_order: list[str],
    results: list[dict],
) -> dict:
    by_word = {item["word"]: item for item in results}
    missing_words = [word for word in word_order if word not in by_word]
    extra_words = [word for word in by_word if word not in set(word_order)]
    order_mismatch = [results[i]["word"] for i in range(min(len(word_order), len(results))) if results[i]["word"] != word_order[i]]

    words_without_audio_url: list[str] = []
    missing_audio_files: list[str] = []
    existing_audio_files = 0
    expected_audio_total = 0

    for word in word_order:
        result = by_word.get(word)
        if not result:
            continue
        expected = expected_audio_files(result)
        if not expected:
            words_without_audio_url.append(word)
            continue
        expected_audio_total += len(expected)
        word_missing = False
        for path in expected:
            if path.exists() and path.stat().st_size > 0:
                existing_audio_files += 1
            else:
                word_missing = True
        if word_missing:
            missing_audio_files.append(word)

    return {
        "word_list_count": len(word_order),
        "result_count": len(results),
        "missing_words": missing_words,
        "extra_words": extra_words,
        "order_mismatch_count": len(order_mismatch),
        "order_mismatch_sample": order_mismatch[:5],
        "words_without_audio_url": words_without_audio_url,
        "missing_audio_words": missing_audio_files,
        "expected_audio_total": expected_audio_total,
        "existing_audio_files": existing_audio_files,
    }


def download_missing_audio(results: list[dict], words: list[str]) -> tuple[int, int]:
    by_word = {item["word"]: item for item in results}
    downloaded = 0
    failed_words: list[str] = []

    for word in words:
        result = by_word.get(word)
        if not result:
            continue
        expected = expected_audio_files(result)
        needs_download = any(not path.exists() or path.stat().st_size == 0 for path in expected)
        if not needs_download:
            continue
        saved = download_word_audio(result)
        if saved:
            downloaded += len(saved)
        else:
            failed_words.append(word)

    return downloaded, failed_words


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit bulk output and download missing audio.")
    parser.add_argument("--bulk-json", type=Path, default=OUTPUT_DIR / "bulk_output.json")
    parser.add_argument("--report", type=Path, default=OUTPUT_DIR / "audit_report.json")
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    setup_logging("INFO")
    word_order = json.loads(WORD_LIST_FILE.read_text(encoding="utf-8"))["words"]
    results = load_json_list(args.bulk_json)
    report = audit(word_order, results)

    print("=== Audit ===")
    print(f"Word list: {report['word_list_count']}")
    print(f"Bulk results: {report['result_count']}")
    print(f"Missing words: {len(report['missing_words'])}")
    print(f"Extra words: {len(report['extra_words'])}")
    print(f"Order mismatches: {report['order_mismatch_count']}")
    print(f"Words without audio URL: {len(report['words_without_audio_url'])}")
    print(f"Words with missing audio files: {len(report['missing_audio_words'])}")
    print(f"Audio files on disk: {report['existing_audio_files']} / {report['expected_audio_total']}")

    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report saved to: {args.report}")

    if report["missing_words"]:
        missing_path = OUTPUT_DIR / "audit_missing_words.txt"
        missing_path.write_text("\n".join(report["missing_words"]) + "\n", encoding="utf-8")
        print(f"Missing word list: {missing_path}")

    if report["missing_audio_words"]:
        missing_audio_path = OUTPUT_DIR / "audit_missing_audio.txt"
        missing_audio_path.write_text("\n".join(report["missing_audio_words"]) + "\n", encoding="utf-8")
        print(f"Missing audio list: {missing_audio_path}")

    if args.skip_download:
        return 1 if report["missing_words"] or report["missing_audio_words"] else 0

    if report["missing_audio_words"]:
        print(f"Downloading audio for {len(report['missing_audio_words'])} word(s)...")
        downloaded, failed_words = download_missing_audio(results, report["missing_audio_words"])
        print(f"Downloaded {downloaded} audio file(s)")
        if failed_words:
            failed_path = OUTPUT_DIR / "audit_audio_failed.txt"
            failed_path.write_text("\n".join(failed_words) + "\n", encoding="utf-8")
            print(f"Audio download failed for {len(failed_words)} word(s): {failed_path}")

        report_after = audit(word_order, results)
        print("=== After audio download ===")
        print(f"Words with missing audio files: {len(report_after['missing_audio_words'])}")
        print(f"Audio files on disk: {report_after['existing_audio_files']} / {report_after['expected_audio_total']}")
        args.report.write_text(json.dumps(report_after, ensure_ascii=False, indent=2), encoding="utf-8")

    has_issues = bool(
        report["missing_words"]
        or (report["missing_audio_words"] and args.skip_download)
    )
    if not args.skip_download and report["missing_audio_words"]:
        report_after = audit(word_order, results)
        has_issues = bool(report["missing_words"] or report_after["missing_audio_words"])
    return 1 if has_issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
