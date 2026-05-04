"""Shell-address detection for Layer 1."""
from typing import Optional
from agents.grant_writer_v2.core.vocab import match_shell_address


def detect(address_text: str) -> tuple[Optional[str], float]:
    """Returns (pattern_id, confidence). confidence=0 means no match."""
    return match_shell_address(address_text)
