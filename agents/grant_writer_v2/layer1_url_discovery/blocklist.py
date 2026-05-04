"""Blocklist check for Layer 1 candidate URLs."""
from typing import Optional
from agents.grant_writer_v2.core.vocab import is_blocklisted as _is_blocklisted


def check(url: str) -> tuple[bool, Optional[str], Optional[str]]:
    """Returns (is_blocked, category, domain)."""
    return _is_blocklisted(url)
