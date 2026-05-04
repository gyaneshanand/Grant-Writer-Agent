"""
On-disk corpus cache: stores the L2 crawled corpus keyed by EIN.
L3 and L4 read from this to avoid re-crawling.
"""
import json
from pathlib import Path

from agents.grant_writer_v2.config import v2_settings
from agents.grant_writer_v2.core.logger import get_logger

logger = get_logger("corpus_cache")

_CORPUS_DIR = Path(v2_settings.CACHE_DIR) / "corpus"
_CORPUS_DIR.mkdir(parents=True, exist_ok=True)


def _corpus_path(ein: str) -> Path:
    safe = ein.replace("/", "_").replace("\\", "_")
    return _CORPUS_DIR / f"{safe}.json"


def save_corpus(ein: str, corpus: list[dict]) -> None:
    try:
        _corpus_path(ein).write_text(json.dumps(corpus))
    except Exception as e:
        logger.warning(f"[corpus_cache] write failed for {ein}: {e}")


def load_corpus(ein: str) -> list[dict]:
    p = _corpus_path(ein)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception as e:
        logger.warning(f"[corpus_cache] read failed for {ein}: {e}")
        return []
