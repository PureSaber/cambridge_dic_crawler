"""Filter vocabulary by CEFR level and word frequency."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import OUTPUT_DIR
from src.exporter import export_results

CEFR_ORDER = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
DEFAULT_MAX_CEFR = "B2"
DEFAULT_TOP_P = 0.85


def _lookup_forms(slug: str) -> list[str]:
    """Generate candidate surface forms for frequency lookup."""
    forms = [slug.replace("-", " "), slug.replace("-", "")]
    if slug not in forms:
        forms.append(slug)
    seen: set[str] = set()
    unique: list[str] = []
    for form in forms:
        key = form.lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(key)
    return unique


def word_frequency(slug: str) -> float:
    """Return English word frequency (higher = more common)."""
    try:
        import wordfreq
    except ImportError as exc:
        raise ImportError(
            "wordfreq is required for frequency filtering. "
            "Install with: pip install wordfreq"
        ) from exc

    best = 0.0
    for form in _lookup_forms(slug):
        best = max(best, wordfreq.word_frequency(form, "en", minimum=0.0))
    return best


def word_matches_cefr(result: dict[str, Any], max_level: int) -> bool:
    """True if any sense in any entry has CEFR <= max_level."""
    for entry in result.get("entries", []):
        for sense in entry.get("senses", []):
            level_name = (sense.get("cefr") or "").strip().upper()
            if level_name in CEFR_ORDER and CEFR_ORDER[level_name] <= max_level:
                return True
    return False


def collect_cefr_levels(result: dict[str, Any]) -> list[str]:
    levels: set[str] = set()
    for entry in result.get("entries", []):
        for sense in entry.get("senses", []):
            level_name = (sense.get("cefr") or "").strip().upper()
            if level_name in CEFR_ORDER:
                levels.add(level_name)
    return sorted(levels, key=lambda name: CEFR_ORDER[name])


def filter_and_rank(
    results: list[dict[str, Any]],
    *,
    max_cefr: str,
    top_p: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    max_level = CEFR_ORDER[max_cefr.upper()]

    cefr_matched: list[dict[str, Any]] = [
        item for item in results if word_matches_cefr(item, max_level)
    ]

    ranked_rows: list[dict[str, Any]] = []
    for item in cefr_matched:
        slug = item.get("word", "")
        ranked_rows.append(
            {
                "word": slug,
                "frequency": word_frequency(slug),
                "cefr_levels": collect_cefr_levels(item),
                "result": item,
            }
        )

    ranked_rows.sort(key=lambda row: (-row["frequency"], row["word"]))
    keep_count = max(1, math.floor(len(ranked_rows) * top_p))
    selected = ranked_rows[:keep_count]

    stats = {
        "input_words": len(results),
        "cefr_matched_words": len(cefr_matched),
        "max_cefr": max_cefr.upper(),
        "top_p": top_p,
        "selected_words": len(selected),
        "dropped_by_frequency": len(ranked_rows) - len(selected),
        "frequency_source": "wordfreq (English, best match over slug variants)",
    }
    return [row["result"] for row in selected], stats


def build_summary_table(selected_rows: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in selected_rows:
        slug = item.get("word", "")
        rows.append(
            {
                "word": slug,
                "frequency": word_frequency(slug),
                "cefr_levels": ", ".join(collect_cefr_levels(item)),
                "url": item.get("url", ""),
            }
        )
    frame = pd.DataFrame(rows)
    return frame.sort_values(["frequency", "word"], ascending=[False, True])


def write_readme(path: Path, stats: dict[str, Any], output_dir: Path) -> None:
    path.write_text(
        f"""# B2 及以下高频词汇子集

本目录由 `scripts/filter_vocab.py` 生成，用于从全量剑桥英汉词典数据中抽取**更适合学习的高频核心词汇**。

## 筛选规则

1. **CEFR 等级**：保留任意义项标注为 **A1 / A2 / B1 / B2** 的词条（CEFR ≤ B2）。
2. **词频排序**：使用 [wordfreq](https://github.com/rspeer/wordfreq) 英文语料库频率；对 slug 尝试 `give-up` → `give up` 等形式取最高频。
3. **Top {stats['top_p']:.0%}**：在通过 CEFR 筛选的词中，按词频从高到低保留前 **{stats['top_p']:.0%}**（去掉最低频的 {100 - stats['top_p'] * 100:.0f}%）。

## 统计

| 指标 | 数量 |
|---|---|
| 全量词条 | {stats['input_words']} |
| 通过 CEFR ≤ {stats['max_cefr']} | {stats['cefr_matched_words']} |
| 最终输出 | {stats['selected_words']} |
| 因词频截断剔除 | {stats['dropped_by_frequency']} |

## 文件说明

| 文件 | 作用 |
|---|---|
| `vocab.json` | 完整结构化词典数据（与 `bulk_output.json` 格式相同） |
| `vocab.csv` | 扁平化表格，便于 Excel / Pandas 分析 |
| `word_list.txt` | 词表 slug 列表（按词频降序） |
| `summary.csv` | 词 + 词频 + 所含 CEFR 等级，便于快速浏览 |
| `manifest.json` | 筛选参数与统计信息 |
| `README.md` | 本说明 |

## 适用场景

- 制作 **B2 及以下背单词 App / 闪卡** 的词库
- 导入 Anki、Notion、数据库时作为**精简高频词表**
- 避免直接学习全量 {stats['input_words']} 词，先聚焦**常见且难度适中**的词汇

## 重新生成

```powershell
.venv\\Scripts\\python scripts/filter_vocab.py
.venv\\Scripts\\python scripts/filter_vocab.py --max-cefr B1 --top-p 0.9
```
""",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Filter bulk dictionary by CEFR and word frequency."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=OUTPUT_DIR / "bulk_output.json",
        help="Source bulk JSON file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR / "filtered_b2_top85",
        help="Directory for filtered output",
    )
    parser.add_argument(
        "--max-cefr",
        default=DEFAULT_MAX_CEFR,
        choices=sorted(CEFR_ORDER),
        help="Maximum CEFR level to include (default: B2)",
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=DEFAULT_TOP_P,
        help="Keep top fraction by frequency after CEFR filter (default: 0.85)",
    )
    args = parser.parse_args()

    if not 0 < args.top_p <= 1:
        raise ValueError("--top-p must be between 0 and 1")

    results = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(results, list):
        raise ValueError("Input JSON must be a list of word results")

    selected, stats = filter_and_rank(
        results,
        max_cefr=args.max_cefr,
        top_p=args.top_p,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "vocab.json"
    csv_path = args.output_dir / "vocab.csv"
    summary_path = args.output_dir / "summary.csv"
    word_list_path = args.output_dir / "word_list.txt"
    manifest_path = args.output_dir / "manifest.json"

    export_results(selected, csv_path, json_path)
    summary = build_summary_table(selected)
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    word_list_path.write_text(
        "\n".join(item["word"] for item in selected) + "\n",
        encoding="utf-8",
    )

    manifest = {
        **stats,
        "input_file": str(args.input),
        "output_dir": str(args.output_dir),
        "files": {
            "vocab_json": str(json_path),
            "vocab_csv": str(csv_path),
            "summary_csv": str(summary_path),
            "word_list": str(word_list_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_readme(args.output_dir / "README.md", stats, args.output_dir)

    print("=== Filter complete ===")
    for key, value in stats.items():
        print(f"{key}: {value}")
    print(f"Output directory: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
