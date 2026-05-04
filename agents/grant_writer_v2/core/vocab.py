"""
Loads all vocabulary YAMLs once at import.
Exposes helpers used by schemas and layer modules.
"""
import os
from pathlib import Path
from typing import Optional
import yaml

_VOCAB_DIR = Path(__file__).parent.parent / "vocabularies"


def _load(filename: str) -> dict:
    with open(_VOCAB_DIR / filename, "r") as f:
        return yaml.safe_load(f)


# Load once at import time
_focus_areas = _load("focus_areas.yaml")
_applicant_types = _load("applicant_types.yaml")
_application_methods = _load("application_methods.yaml")
_deadline_types = _load("deadline_types.yaml")
_funding_buckets = _load("funding_buckets.yaml")
_foundation_types = _load("foundation_types.yaml")
_shell_patterns = _load("shell_address_patterns.yaml")
_geo_codes = _load("geography_codes.yaml")
_blocklist = _load("url_blocklist.yaml")

# Sets for fast membership tests
FOCUS_AREA_IDS: set[str] = {item["id"] for item in _focus_areas["focus_areas"]}
APPLICANT_TYPE_IDS: set[str] = {item["id"] for item in _applicant_types["applicant_types"]}
APPLICATION_METHOD_IDS: set[str] = {item["id"] for item in _application_methods["application_methods"]}
DEADLINE_TYPE_IDS: set[str] = {item["id"] for item in _deadline_types["deadline_types"]}
FUNDING_BUCKET_IDS: set[str] = {item["id"] for item in _funding_buckets["funding_buckets"]}
FOUNDATION_TYPE_IDS: set[str] = {item["id"] for item in _foundation_types["foundation_types"]}
IN_SCOPE_COUNTRIES: set[str] = set(_geo_codes["in_scope_countries"])

# Blocklist: domain → category
_BLOCKED_DOMAINS: dict[str, str] = {}
for _cat, _data in _blocklist["categories"].items():
    for _domain in _data.get("domains", []):
        _BLOCKED_DOMAINS[_domain.lower()] = _cat


def is_blocklisted(url: str) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Returns (is_blocked, category, domain).
    Checks if any blocked domain is a suffix of the URL's domain.
    """
    try:
        from urllib.parse import urlparse
        host = urlparse(url.lower()).netloc.lstrip("www.")
        for domain, category in _BLOCKED_DOMAINS.items():
            if host == domain or host.endswith("." + domain):
                return True, category, domain
    except Exception:
        pass
    return False, None, None


def validate_focus_areas(values: list[str]) -> list[str]:
    """Raises ValueError for any id not in the controlled vocab."""
    invalid = [v for v in values if v not in FOCUS_AREA_IDS]
    if invalid:
        raise ValueError(f"Unknown focus_area ids: {invalid}. Valid ids: {sorted(FOCUS_AREA_IDS)}")
    return values


def validate_applicant_types(values: list[str]) -> list[str]:
    invalid = [v for v in values if v not in APPLICANT_TYPE_IDS]
    if invalid:
        raise ValueError(f"Unknown applicant_type ids: {invalid}")
    return values


def validate_application_methods(values: list[str]) -> list[str]:
    invalid = [v for v in values if v not in APPLICATION_METHOD_IDS]
    if invalid:
        raise ValueError(f"Unknown application_method ids: {invalid}")
    return values


def validate_deadline_type(value: str) -> str:
    if value not in DEADLINE_TYPE_IDS:
        raise ValueError(f"Unknown deadline_type: {value}. Valid: {sorted(DEADLINE_TYPE_IDS)}")
    return value


def bucket_funding_amount(min_usd: Optional[float], max_usd: Optional[float]) -> str:
    """Map funding range to a bucket id from funding_buckets.yaml."""
    amount = max_usd or min_usd
    if amount is None:
        return "unspecified"
    for bucket in _funding_buckets["funding_buckets"]:
        b_min = bucket.get("min_usd", 0)
        b_max = bucket.get("max_usd", float("inf"))
        if b_min <= amount <= b_max:
            return bucket["id"]
    return "gt_1m"


def match_shell_address(address_text: str) -> tuple[Optional[str], float]:
    """
    Returns (pattern_id, confidence) if address matches a known shell pattern.
    confidence is 0.0 if no match.
    """
    if not address_text:
        return None, 0.0
    text = address_text.lower()
    for pattern_id, data in _shell_patterns["shell_address_patterns"].items() if isinstance(_shell_patterns["shell_address_patterns"], dict) else []:
        for p in data.get("patterns", []):
            if p.lower() in text:
                return pattern_id, 0.95
    # Handle list format (YAML loads as list of dicts)
    if isinstance(_shell_patterns.get("shell_address_patterns"), list):
        for item in _shell_patterns["shell_address_patterns"]:
            for p in item.get("patterns", []):
                if p.lower() in text:
                    return item["id"], 0.95
    return None, 0.0
