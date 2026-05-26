-- Migration 001: Create foundations table and add all v2_* columns.
-- Safe to re-run: CREATE TABLE IF NOT EXISTS + IGNORE errors on duplicate columns.

CREATE TABLE IF NOT EXISTS foundations (
    ein         VARCHAR(9)   PRIMARY KEY,
    name        VARCHAR(500) NOT NULL DEFAULT '',
    city        VARCHAR(100),
    state       VARCHAR(2),
    address     VARCHAR(500),
    created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    -- Identity
    v2_ein_formatted     VARCHAR(11),
    v2_legal_name        VARCHAR(500),
    v2_dba_names         JSON,
    v2_foundation_type   VARCHAR(50),
    v2_irs_subsection    VARCHAR(20)  DEFAULT '501(c)(3)',
    v2_irs_ruling_year   INT,
    v2_ntee_code         VARCHAR(20),

    -- Layer 1
    v2_layer1_status        VARCHAR(40),
    v2_layer1_url           VARCHAR(500),
    v2_layer1_confidence    DECIMAL(3,2),
    v2_layer1_evidence      TEXT,
    v2_layer1_place_id      VARCHAR(100),
    v2_layer1_method        VARCHAR(40),
    v2_layer1_metadata      JSON,
    v2_layer1_processed_at  TIMESTAMP NULL,

    -- Layer 2 rollup
    v2_layer2_status             VARCHAR(40),
    v2_layer2_rollup_verdict     ENUM('VALID','NEEDS_REVIEW','INVALID','ERROR'),
    v2_layer2_program_count      INT          DEFAULT 0,
    v2_layer2_valid_program_count INT         DEFAULT 0,
    v2_layer2_corpus_cache_key   VARCHAR(64),
    v2_layer2_stop_reason        VARCHAR(40),
    v2_layer2_cost_usd           DECIMAL(8,4),
    v2_layer2_processed_at       TIMESTAMP NULL,

    -- Layer 3 org profile (denormalized for fast read)
    v2_org_name               VARCHAR(500),
    v2_mission                TEXT,
    v2_background             TEXT,
    v2_about                  TEXT,
    v2_contact                JSON,
    v2_focus_areas            JSON,
    v2_geography_served       JSON,
    v2_populations_served     JSON,
    v2_social_profiles        JSON,
    v2_total_assets_usd       DECIMAL(15,2),
    v2_total_assets_year      INT,
    v2_annual_giving_usd      DECIMAL(15,2),
    v2_annual_giving_year     INT,
    v2_grants_paid_3yr_avg_usd    DECIMAL(15,2),
    v2_fiscal_year_end        VARCHAR(5),
    v2_founded_year           INT,
    v2_admin_address_pattern  VARCHAR(50),
    v2_accepts_unsolicited    BOOLEAN,
    v2_is_invitation_only     BOOLEAN,
    v2_application_methods    JSON,
    v2_layer3_status          VARCHAR(40),
    v2_layer3_processed_at    TIMESTAMP NULL,

    -- Layer 4
    v2_layer4_status                     VARCHAR(40),
    v2_layer4_consolidated_description   TEXT,
    v2_layer4_processed_at               TIMESTAMP NULL,

    -- Layer 5
    v2_layer5_status          VARCHAR(40),
    v2_layer5_processed_at    TIMESTAMP NULL,

    -- Pipeline state
    v2_pipeline_status   VARCHAR(40)  DEFAULT 'pending',
    v2_last_error        TEXT,
    v2_review_status     VARCHAR(40)  DEFAULT 'auto_approved',
    v2_review_flags      JSON,
    v2_is_stale          BOOLEAN      DEFAULT FALSE,
    v2_first_seen_at     TIMESTAMP    NULL,
    v2_last_verified_at  TIMESTAMP    NULL,
    v2_updated_at        TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_v2_pipeline_status   (v2_pipeline_status),
    INDEX idx_v2_layer1_status     (v2_layer1_status),
    INDEX idx_v2_layer2_rollup     (v2_layer2_rollup_verdict)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
