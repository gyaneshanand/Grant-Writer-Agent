-- ============================================================
-- TGP Chatbot - Conversation Persistence Table
-- ============================================================
-- This migration creates the table needed for stateful conversation
-- mode and analytics/audit logging.
--
-- NOTE: Grant search requires access to existing TGP tables:
--   - grants_info
--   - grants_info_interest_map
--   - grants_info_locations_map
--   - grants_info_eligibilty_map
--   - interests
--   - provinces
--   - eligibilties
--
-- Run this migration:
--   mysql -u user -p tgp < scripts/init_chatbot.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS chatbot_conversations (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    user_id INT UNSIGNED DEFAULT NULL,
    role ENUM('user', 'assistant') NOT NULL,
    content TEXT NOT NULL,
    query_type VARCHAR(50) DEFAULT NULL,
    extracted_entities JSON DEFAULT NULL,
    search_results_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at),
    INDEX idx_query_type (query_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Optional: Foreign key to users table (if it exists)
-- ALTER TABLE chatbot_conversations
--   ADD CONSTRAINT fk_chatbot_user
--   FOREIGN KEY (user_id) REFERENCES users(id)
--   ON DELETE SET NULL;
