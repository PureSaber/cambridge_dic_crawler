"""Configuration constants for the Cambridge Dictionary crawler."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
LOG_DIR = PROJECT_ROOT / "logs"
CACHE_DIR = PROJECT_ROOT / "cache"
ERROR_LOG_FILE = LOG_DIR / "error_log.txt"
WORD_LIST_FILE = CACHE_DIR / "word_list.json"
CHECKPOINT_FILE = CACHE_DIR / "checkpoint.json"
BULK_RESULTS_FILE = OUTPUT_DIR / "bulk_results.json"

BASE_URL = "https://dictionary.cambridge.org/dictionary/english-chinese-simplified"
CAMBRIDGE_ORIGIN = "https://dictionary.cambridge.org"
BROWSE_BASE_URL = "https://dictionary.cambridge.org/browse/english-chinese-simplified"
BROWSE_PATH_PREFIX = "/browse/english-chinese-simplified/"
DICT_PATH_PATTERN = "/dictionary/english-chinese-simplified/"

DISCOVERY_SLEEP_MIN = 0.8
DISCOVERY_SLEEP_MAX = 2.0
CHECKPOINT_EVERY = 10
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0

SLEEP_MIN = 1.5
SLEEP_MAX = 4.0
REQUEST_TIMEOUT = 30
DEFAULT_WORKERS = 1
MAX_WORKERS = 8
AUDIO_DIR = OUTPUT_DIR / "audio"

USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.4 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
        "Gecko/20100101 Firefox/125.0"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) "
        "Gecko/20100101 Firefox/125.0"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) "
        "Gecko/20100101 Firefox/125.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Edge/124.0.0.0"
    ),
    (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
    ),
    (
        "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
    ),
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}
