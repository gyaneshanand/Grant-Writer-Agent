-- Migration 002: Create v2_grant_programs table — PRIMARY UNIT of v2.
-- One row per identified grant program.

CREATE TABLE IF NOT EXISTS v2_grant_programs (
    program_id              VARCHAR(64)  PRIMARY KEY,
    ein                     VARCHAR(9)   NOT NULL,
    program_name            VARCHAR(500) NOT NULL,
    program_slug            VARCHAR(255),
    program_url             VARCHAR(500),

    -- Layer 2 verdict
    verdict                 ENUM('VALID','NEEDS_REVIEW','INVALID','ERROR') NOT NULL DEFAULT 'NEEDS_REVIEW',
    verdict_confidence      DECIMAL(3,2),
    verdict_reasoning       TEXT,
    rules_json              JSON,
    override_applied        VARCHAR(40),

    -- Layer 4: Funding
    funding_priorities      TEXT,
    types_of_grant          VARCHAR(500),
    eligibility_criteria    TEXT,
    eligible_applicants_freeform    TEXT,
    eligible_applicant_types        JSON,
    eligible_locations_freeform     TEXT,
    eligible_geographies            JSON,
    excluded_geographies            JSON,
    eligible_focus_areas            JSON,
    excluded_uses                   JSON,
    minimum_org_age_years           INT,
    minimum_budget_usd              DECIMAL(15,2),
    maximum_budget_usd              DECIMAL(15,2),
    requires_501c3                  BOOLEAN,

    grant_amount_freeform           VARCHAR(500),
    grant_amount_min_usd            DECIMAL(12,2),
    grant_amount_max_usd            DECIMAL(12,2),
    grant_amount_typical_usd        DECIMAL(12,2),
    grant_amount_currency           VARCHAR(3)   DEFAULT 'USD',
    funding_match_required          BOOLEAN,
    funding_match_percent           DECIMAL(5,2),

    -- Layer 4: Deadlines
    proposal_deadline_freeform      VARCHAR(500),
    deadlines                       JSON,
    deadline_type                   VARCHAR(30),
    next_deadline_iso               DATE,
    is_currently_open               BOOLEAN,
    application_window_days         INT,
    loi_required                    BOOLEAN,
    loi_deadline_iso                DATE,

    -- Layer 4: Application process
    application_method              JSON,
    application_portal_url          VARCHAR(500),
    application_email               VARCHAR(255),
    application_steps               JSON,
    required_documents              JSON,
    review_timeline_weeks           INT,

    -- Layer 4: Type flags
    is_invitation_only              BOOLEAN DEFAULT FALSE,
    accepts_unsolicited             BOOLEAN DEFAULT TRUE,
    is_recurring                    BOOLEAN DEFAULT FALSE,
    is_currently_active             BOOLEAN DEFAULT TRUE,
    recurrence                      VARCHAR(50),

    -- Layer 4: Contact
    contact_info                    JSON,

    -- Provenance
    source_pages                    JSON,
    source_pdfs                     JSON,
    extraction_method               VARCHAR(50),
    extraction_model                VARCHAR(100),
    extraction_prompt_version       VARCHAR(50),
    extraction_timestamp            TIMESTAMP NULL,
    extraction_confidence           DECIMAL(3,2),
    evidence_quotes                 JSON,
    completeness_score              DECIMAL(3,2),

    -- Layer 5: SEO & metadata
    opportunity_title               VARCHAR(255),
    h1_tag                          VARCHAR(255),
    meta_title                      VARCHAR(255),
    meta_description                VARCHAR(500),
    opportunity_teaser              TEXT,
    opportunity_title_for_subscriber VARCHAR(500),
    slug                            VARCHAR(255),
    canonical_url                   VARCHAR(500),
    categories                      JSON,
    primary_category                VARCHAR(100),
    tags                            JSON,

    -- Layer 5: Filters (deterministic) — names match filter_deriver.py output
    filter_focus_areas              JSON,
    filter_applicant_types          JSON,
    filter_geographies              JSON,
    filter_funding_bucket           VARCHAR(20),
    filter_deadline_type            VARCHAR(30),
    filter_is_open                  BOOLEAN,
    filter_accepts_unsolicited      BOOLEAN,
    filter_loi_required             BOOLEAN,
    filter_geo_scope                VARCHAR(20),
    -- legacy aliases kept for compatibility
    filter_funding_range            VARCHAR(20),
    filter_geography_scope          VARCHAR(20),
    filter_currently_open           BOOLEAN,

    -- Layer 5: Search index
    search_blob                     LONGTEXT,
    search_keywords                 JSON,

    -- OG / Social
    og_title                        VARCHAR(255),
    og_description                  VARCHAR(500),
    og_image_url                    VARCHAR(500),

    -- Dedup
    duplicate_of_program_id         VARCHAR(64),
    similarity_score_to_duplicate   DECIMAL(3,2),
    duplicate_review_status         VARCHAR(30),

    -- Review
    review_status                   VARCHAR(40) DEFAULT 'auto_approved',
    review_flags                    JSON,
    reviewer_notes                  TEXT,
    reviewed_by                     VARCHAR(50),
    reviewed_at                     TIMESTAMP NULL,

    -- Versioning & lifecycle
    version                         INT         DEFAULT 1,
    previous_version_id             VARCHAR(64),
    publish_status                  VARCHAR(20) DEFAULT 'draft',
    published_at                    TIMESTAMP NULL,
    superseded_by_program_id        VARCHAR(64),
    first_seen_at                   TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    last_verified_at                TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    last_updated_at                 TIMESTAMP   DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_stale                        BOOLEAN     DEFAULT FALSE,

    UNIQUE INDEX uniq_slug (slug),
    INDEX idx_ein (ein),
    INDEX idx_verdict (verdict),
    INDEX idx_publish_status (publish_status),
    INDEX idx_review_status (review_status),
    INDEX idx_next_deadline (next_deadline_iso),
    INDEX idx_currently_open (is_currently_open),
    INDEX idx_funding_max (grant_amount_max_usd),
    INDEX idx_funding_range (filter_funding_range),
    INDEX idx_deadline_type (filter_deadline_type),
    INDEX idx_duplicate (duplicate_of_program_id),
    FULLTEXT INDEX ftx_search (search_blob)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
