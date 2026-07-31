"""Retry missing words and merge bulk output in word_list order."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import OUTPUT_DIR, WORD_LIST_FILE
from src.crawler import crawl_words_bulk
from src.exporter import export_results
from src.logging_config import setup_logging


def load_word_order() -> list[str]:
    data = json.loads(WORD_LIST_FILE.read_text(encoding="utf-8"))
    return data["words"]


def load_results(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def find_missing(word_order: list[str], results: list[dict]) -> list[str]:
    found = {item["word"] for item in results}
    return [word for word in word_order if word not in found]


def merge_results(word_order: list[str], *sources: list[dict]) -> list[dict]:
    by_word: dict[str, dict] = {}
    for source in sources:
        for item in source:
            by_word[item["word"]] = item
    return [by_word[word] for word in word_order if word in by_word]


def main() -> int:
    parser = argparse.ArgumentParser(description="Retry missing words and merge bulk output.")
    parser.add_argument("--bulk-json", type=Path, default=OUTPUT_DIR / "bulk_output.json")
    parser.add_argument("--bulk-csv", type=Path, default=OUTPUT_DIR / "bulk_output.csv")
    parser.add_argument("--retry-json", type=Path, default=OUTPUT_DIR / "retry.json")
    parser.add_argument("--missing-list", type=Path, default=OUTPUT_DIR / "missing_words.txt")
    parser.add_argument("--skip-retry", action="store_true", help="Only merge existing files.")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    setup_logging("INFO")
    word_order = load_word_order()
    bulk_results = load_results(args.bulk_json)
    missing = find_missing(word_order, bulk_results)

    print(f"Word list: {len(word_order)}")
    print(f"Bulk results: {len(bulk_results)}")
    print(f"Missing: {len(missing)}")

    if missing:
        args.missing_list.write_text("\n".join(missing) + "\n", encoding="utf-8")
        print(f"Missing words saved to: {args.missing_list}")

    retry_results: list[dict] = []
    if missing and not args.skip_retry:
        print(f"Retrying {len(missing)} word(s)...")
        retry_results, errors = crawl_words_bulk(missing, checkpoint=False, workers=args.workers)
        print(f"Retry success: {len(retry_results)} | failed: {len(errors)}")
        if errors:
            error_path = OUTPUT_DIR / "retry_errors.json"
            error_path.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Retry errors saved to: {error_path}")
        if retry_results:
            args.retry_json.write_text(
                json.dumps(retry_results, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Retry results saved to: {args.retry_json}")
    elif args.retry_json.exists():
        retry_results = load_results(args.retry_json)
        print(f"Loaded retry results: {len(retry_results)}")

    merged = merge_results(word_order, bulk_results, retry_results)
    still_missing = find_missing(word_order, merged)

    backup_json = args.bulk_json.with_suffix(".json.bak")
    backup_csv = args.bulk_csv.with_suffix(".csv.bak")
    if args.bulk_json.exists():
        backup_json.write_bytes(args.bulk_json.read_bytes())
    if args.bulk_csv.exists():
        backup_csv.write_bytes(args.bulk_csv.read_bytes())

    df, csv_path, json_path = export_results(merged, args.bulk_csv, args.bulk_json)
    print(f"Merged results: {len(merged)}")
    print(f"Still missing: {len(still_missing)}")
    print(f"CSV saved to: {csv_path}")
    print(f"JSON saved to: {json_path}")
    print(f"DataFrame shape: {df.shape}")
    if still_missing:
        still_missing_path = OUTPUT_DIR / "still_missing.txt"
        still_missing_path.write_text("\n".join(still_missing) + "\n", encoding="utf-8")
        print(f"Still missing list: {still_missing_path}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
