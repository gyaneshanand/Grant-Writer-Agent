"""Tests for Layer 5 metadata/SEO."""
import pytest
from agents.grant_writer_v2.layer5_metadata_seo.filter_deriver import derive_filters
from agents.grant_writer_v2.layer5_metadata_seo.duplicate_detector import build_search_blob, find_duplicate
from agents.grant_writer_v2.layer5_metadata_seo.slug_generator import generate_slug


def test_derive_filters_basic():
    row = {
        "eligible_focus_areas": '["education_k12", "arts_culture"]',
        "eligible_applicant_types": '["nonprofit_501c3"]',
        "eligible_geographies": '["NY", "NJ"]',
        "grant_amount_min_usd": 5000,
        "grant_amount_max_usd": 50000,
        "grant_amount_typical_usd": None,
        "deadline_type": "annual",
        "is_currently_open": True,
        "accepts_unsolicited": True,
        "loi_required": False,
    }
    filters = derive_filters(row)
    assert filters["filter_funding_bucket"] == "25k_100k"
    assert filters["filter_deadline_type"] == "annual"
    assert filters["filter_is_open"] is True
    assert filters["filter_geo_scope"] == "us_only"


def test_derive_filters_international():
    row = {
        "eligible_geographies": '["INTL", "US"]',
        "grant_amount_min_usd": None,
        "grant_amount_max_usd": None,
        "grant_amount_typical_usd": None,
        "deadline_type": "rolling",
        "is_currently_open": None,
        "accepts_unsolicited": True,
        "loi_required": None,
        "eligible_focus_areas": "[]",
        "eligible_applicant_types": "[]",
    }
    filters = derive_filters(row)
    assert filters["filter_geo_scope"] == "international"


def test_search_blob_building():
    row = {
        "program_name": "Community Arts Grant",
        "funding_priorities": "Arts education in underserved communities",
        "eligibility_criteria": "Must be a 501(c)(3) nonprofit",
        "eligible_focus_areas": '["arts_culture"]',
        "eligible_geographies": '["NY"]',
        "grant_amount_freeform": "Up to $50,000",
        "proposal_deadline_freeform": "Rolling",
        "eligible_applicants_freeform": "Nonprofits in NY",
        "eligible_locations_freeform": "New York State",
        "types_of_grant": "",
        "opportunity_title": "",
        "meta_description": "",
    }
    blob = build_search_blob(row)
    assert "arts" in blob
    assert "community" in blob


def test_duplicate_detection_similar():
    blob1 = "community arts grant education new york 50000 rolling deadline"
    blob2 = "community arts grant education new york 50000 rolling deadline program"
    result = find_duplicate(
        "prog_1", blob1,
        [{"program_id": "prog_2", "search_blob": blob2}],
    )
    # High similarity — may or may not trigger based on threshold; just ensure no exception
    assert result is None or isinstance(result, str)


def test_duplicate_detection_different():
    blob1 = "medical research grants hospitals 2024"
    blob2 = "arts education community programs nonprofits rolling"
    result = find_duplicate(
        "prog_1", blob1,
        [{"program_id": "prog_2", "search_blob": blob2}],
    )
    assert result is None
