-- Migration 003: Audit tables.
-- v2_pipeline_runs — one row per (ein, layer) execution
-- v2_llm_calls     — one row per LLM API call
-- v2_layer1_candidates — full audit trail of Layer 1 URL candidates

CREATE TABLE IF NOT EXISTS v2_pipeline_runs (
    run_id          VARCHAR(64)  PRIMARY KEY,
    ein             VARCHAR(9)   NOT NULL,
    layer           VARCHAR(20)  NOT NULL,
    status          VARCHAR(40),
    output_snapshot JSON,
    model           VARCHAR(100),
    prompt_version  VARCHAR(50),
    cost_usd        DECIMAL(8,5) DEFAULT 0,
    duration_ms     INT          DEFAULT 0,
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ein_layer (ein, layer),
    INDEX idx_created   (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS v2_llm_calls (
    id              BIGINT       AUTO_INCREMENT PRIMARY KEY,
    ein             VARCHAR(9),
    layer           VARCHAR(40),
    provider        VARCHAR(20),
    model           VARCHAR(100),
    prompt_hash     VARCHAR(64),
    input_tokens    INT          DEFAULT 0,
    output_tokens   INT          DEFAULT 0,
    cost_usd        DECIMAL(8,5) DEFAULT 0,
    latency_ms      INT          DEFAULT 0,
    status          VARCHAR(20),
    error_message   TEXT,
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ein_layer (ein, layer),
    INDEX idx_created   (created_at),
    INDEX idx_prompt    (prompt_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS v2_layer1_candidates (
    id                  BIGINT       AUTO_INCREMENT PRIMARY KEY,
    ein                 VARCHAR(9)   NOT NULL,
    candidate_url       VARCHAR(500),
    position            INT,
    title               VARCHAR(500),
    snippet             TEXT,
    blocklisted         BOOLEAN      DEFAULT FALSE,
    blocklist_category  VARCHAR(50),
    blocklist_domain    VARCHAR(255),
    verifier_score      DECIMAL(3,2),
    verifier_signals    JSON,
    selected            BOOLEAN      DEFAULT FALSE,
    rejection_reason    VARCHAR(100),
    serpapi_query       VARCHAR(500),
    created_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ein        (ein),
    INDEX idx_blocklist  (blocklisted, blocklist_category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
