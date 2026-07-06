#!/usr/bin/env python3
"""CLI entry point for the Cambridge English-Chinese dictionary crawler."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.checkpoint import load_checkpoint
from src.crawler import crawl_words_bulk
from src.exporter import export_results
from src.input_loader import load_words_from_args, load_words_from_file, load_words_from_url
from src.logging_config import setup_logging
from src.runtime_settings import configure, settings
from src.word_discovery import discover_all_words, load_word_list, save_word_list


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crawl Cambridge English-Chinese (Simplified) Dictionary entries.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py industrial engineering\n"
            "  python main.py -f words.txt\n"
            "  python main.py --all\n"
            "  python main.py --all --letters a,b --limit 100\n"
            "  python main.py --discover-only --all\n"
            "  python main.py --all --use-cache --resume\n"
            "  python main.py hello --sleep-min 2 --sleep-max 5 --retries 5\n"
        ),
    )
    parser.add_argument(
        "words",
        nargs="*",
        help="Words to look up directly from the command line",
    )
    parser.add_argument(
        "-f",
        "--file",
        dest="word_file",
        help="Path to a text or JSON file containing words",
    )
    parser.add_argument(
        "-u",
        "--url",
        dest="word_url",
        help="URL of a web page from which to extract words",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_path",
        help="Output CSV path (JSON will use the same base name)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Discover and crawl all words from the Cambridge browse index",
    )
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="Only discover the full word list and save it to cache/word_list.json",
    )
    parser.add_argument(
        "--letters",
        help="Limit browse discovery to specific letters, e.g. a,b,c",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of words to discover or crawl",
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Reuse cache/word_list.json instead of re-discovering words",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume a previous bulk crawl from cache/checkpoint.json",
    )
    parser.add_argument(
        "--save-every",
        type=int,
        default=10,
        help="Save checkpoint every N crawled words (default: 10)",
    )
    parser.add_argument(
        "--sleep-min",
        type=float,
        help="Minimum random delay between requests in seconds",
    )
    parser.add_argument(
        "--sleep-max",
        type=float,
        help="Maximum random delay between requests in seconds",
    )
    parser.add_argument(
        "--retries",
        type=int,
        help="Maximum HTTP retry attempts per request",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )
    parser.add_argument(
        "--no-robots-check",
        action="store_true",
        help="Skip robots.txt compliance check",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        help=f"Concurrent crawl workers (1-{8}, default: 1)",
    )
    parser.add_argument(
        "--download-audio",
        action="store_true",
        help="Download UK/US pronunciation MP3 files to output/audio/",
    )
    parser.add_argument(
        "--audio-dir",
        help="Directory for downloaded audio files (default: output/audio)",
    )
    return parser


def _parse_letters(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [letter.strip().lower() for letter in value.split(",") if letter.strip()]


def resolve_words(args: argparse.Namespace) -> list[str]:
    if args.all or args.discover_only:
        letters = _parse_letters(args.letters)

        if args.use_cache:
            cached = load_word_list()
            if not cached:
                raise ValueError("No cached word list found. Run discovery first without --use-cache.")
            words = cached
        else:
            print("Discovering words from Cambridge browse index...")

            def on_discover(message: str, word_count: int, page_count: int) -> None:
                print(f"[discover] pages={page_count} words={word_count} | {message}")

            words = discover_all_words(
                letters=letters,
                limit=args.limit,
                on_progress=on_discover,
            )
            save_word_list(words, letters=letters)
            print(f"Discovered {len(words)} word(s). Saved to cache/word_list.json")

        if args.discover_only:
            return []

        if args.limit:
            words = words[: args.limit]

        if args.resume:
            checkpoint = load_checkpoint()
            if checkpoint:
                completed = set(checkpoint.get("completed_words", []))
                words = [word for word in words if word not in completed]
                print(f"Resuming bulk crawl. Remaining words: {len(words)}")
            else:
                print("No checkpoint found. Starting a fresh bulk crawl.")

        return words

    sources = sum(
        [
            bool(args.words),
            bool(args.word_file),
            bool(args.word_url),
        ]
    )
    if sources == 0:
        raise ValueError("Provide words, -f/--file, -u/--url, or --all")
    if sources > 1:
        raise ValueError("Use only one input source at a time")

    if args.word_file:
        words = load_words_from_file(args.word_file)
    elif args.word_url:
        words = load_words_from_url(args.word_url)
    else:
        words = load_words_from_args(args.words)

    if args.limit:
        words = words[: args.limit]
    return words


def _resolve_output_paths(args: argparse.Namespace) -> tuple[Path | None, Path | None]:
    if args.output_path:
        csv_path = Path(args.output_path)
        return csv_path, csv_path.with_suffix(".json")

    if args.all:
        bulk_csv = Path("output") / "bulk_output.csv"
        return bulk_csv, bulk_csv.with_suffix(".json")

    return None, None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    setup_logging(args.log_level)
    configure(
        sleep_min=args.sleep_min,
        sleep_max=args.sleep_max,
        max_retries=args.retries,
        check_robots=not args.no_robots_check,
        workers=args.workers,
        download_audio=args.download_audio,
        audio_dir=args.audio_dir,
    )

    try:
        words = resolve_words(args)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.discover_only:
        return 0

    if not words:
        print("No words to crawl.", file=sys.stderr)
        return 1

    preview = ", ".join(words[:5])
    if len(words) > 5:
        preview += ", ..."
    print(f"Crawling {len(words)} word(s): {preview}")

    if len(words) > 1 and settings.workers > 1:
        print(f"Concurrent workers: {settings.workers}")
    if settings.download_audio:
        print(f"Audio download enabled -> {settings.audio_dir}")

    csv_path, json_path = _resolve_output_paths(args)
    use_checkpoint = args.all or args.resume

    def export_partial(results: list) -> None:
        if csv_path and json_path:
            export_results(results, csv_path, json_path)

    def on_progress(word: str, index: int, total: int, success_count: int, error_count: int) -> None:
        print(
            f"[{index}/{total}] {word} | success={success_count} failed={error_count}",
            flush=True,
        )

    results, errors = crawl_words_bulk(
        words,
        resume=args.resume,
        checkpoint=use_checkpoint,
        save_every=args.save_every,
        workers=settings.workers,
        on_progress=on_progress if len(words) > 1 else None,
        on_export=export_partial if use_checkpoint else None,
    )

    df, saved_csv, saved_json = export_results(results, csv_path, json_path)

    print(f"Success: {len(results)} word(s)")
    print(f"Failed: {len(errors)} word(s)")
    print(f"CSV saved to: {saved_csv}")
    print(f"JSON saved to: {saved_json}")
    print(f"DataFrame shape: {df.shape}")

    if errors:
        print("Errors were logged to logs/error_log.txt and logs/crawler.log", file=sys.stderr)

    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
