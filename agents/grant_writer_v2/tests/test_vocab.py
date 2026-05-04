"""Tests for core/vocab.py — vocabulary loading and helpers."""
import pytest
from agents.grant_writer_v2.core.vocab import (
    is_blocklisted,
    validate_focus_areas,
    validate_applicant_types,
    bucket_funding_amount,
    match_shell_address,
    FOCUS_AREA_IDS,
    APPLICANT_TYPE_IDS,
)


def test_blocklist_guidestar():
    blocked, cat, domain = is_blocklisted("https://www.guidestar.org/profile/123")
    assert blocked is True
    assert cat == "directory"


def test_blocklist_wikipedia():
    blocked, cat, domain = is_blocklisted("https://en.wikipedia.org/wiki/Foundation")
    assert blocked is True


def test_blocklist_legitimate_url():
    blocked, _, _ = is_blocklisted("https://www.akindaleFoundation.org")
    assert blocked is False


def test_validate_focus_areas_valid():
    result = validate_focus_areas(["education_k12", "arts_culture"])
    assert "education_k12" in result


def test_validate_focus_areas_invalid():
    with pytest.raises(ValueError):
        validate_focus_areas(["definitely_not_a_focus_area_xyz"])


def test_validate_applicant_types_valid():
    result = validate_applicant_types(["nonprofit_501c3", "individual"])
    assert "nonprofit_501c3" in result


def test_bucket_funding_low():
    assert bucket_funding_amount(1000, 4000) == "lt_5k"


def test_bucket_funding_mid():
    assert bucket_funding_amount(10000, 50000) == "25k_100k"


def test_bucket_funding_high():
    assert bucket_funding_amount(500000, 2000000) == "gt_1m"


def test_bucket_funding_unspecified():
    assert bucket_funding_amount(None, None) == "unspecified"


def test_shell_address_match():
    result = match_shell_address("501 Silverside Road Suite 123 Foundation Source")
    assert result is not None


def test_shell_address_no_match():
    result = match_shell_address("123 Main Street, Springfield, NY 12345")
    assert result is None


def test_focus_area_ids_not_empty():
    assert len(FOCUS_AREA_IDS) > 10


def test_applicant_type_ids_not_empty():
    assert len(APPLICANT_TYPE_IDS) > 5
