-- CyberChunk PostgreSQL Schema
-- Purpose: Audit-ready cybersecurity knowledge base with vector search
-- Version: 1.0.0

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- DATASETS: Track framework versions (OWASP 2025, CWE 2024, etc.)
-- ============================================================================
CREATE TABLE datasets (
    dataset_id VARCHAR(100) PRIMARY KEY,
    version VARCHAR(50) NOT NULL,
    publisher VARCHAR(100) NOT NULL,
    active BOOLEAN DEFAULT true,  -- Set to false when superseded by new version
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    fetched_at TIMESTAMP WITH TIME ZONE,
    fetched_by VARCHAR(200),
    source_dir TEXT,  -- Path to data/sources/{dataset}_{version}_{date}/
    manifest JSONB,   -- Full manifest.json content
    notes TEXT,
    UNIQUE(dataset_id, version)
);

CREATE INDEX idx_datasets_version ON datasets(dataset_id, version);
CREATE INDEX idx_datasets_active ON datasets(active) WHERE active = true;
COMMENT ON TABLE datasets IS 'Framework datasets with version tracking for audit trail';
COMMENT ON COLUMN datasets.active IS 'Set to false when dataset version is superseded';

-- ============================================================================
-- DOCUMENTS: Individual source files within datasets
-- ============================================================================
CREATE TABLE documents (
    doc_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id VARCHAR(100) NOT NULL REFERENCES datasets(dataset_id) ON DELETE CASCADE,
    source_uri TEXT NOT NULL,
    source_file_path TEXT,  -- Path to preserved source file
    source_file_hash VARCHAR(64),  -- SHA256 of original file
    content_hash VARCHAR(64),  -- SHA256 of processed content
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ingested_by VARCHAR(200),
    pipeline_version VARCHAR(50),
    publisher VARCHAR(100),
    edition VARCHAR(50),
    version VARCHAR(50),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_documents_dataset ON documents(dataset_id);
CREATE INDEX idx_documents_source_uri ON documents(source_uri);
CREATE INDEX idx_documents_hash ON documents(content_hash);
COMMENT ON TABLE documents IS 'Source documents with full provenance tracking';

-- ============================================================================
-- CHUNKS: Enriched knowledge chunks with vectors
-- ============================================================================
CREATE TABLE chunks (
    chunk_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    doc_id UUID NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    section_id UUID,

    -- Core content
    chunk_type VARCHAR(50) NOT NULL,  -- risk, weakness, mitigation, attack_scenario, etc.
    canonical_id VARCHAR(100),  -- CWE-79, A01, T1059, etc.
    title TEXT,
    text TEXT NOT NULL,

    -- Enrichment (Phase 1)
    tags JSONB DEFAULT '{
        "keywords": [],
        "topics": [],
        "taxonomy": [],
        "stride": [],
        "asset_types": [],
        "technologies": [],
        "security_controls": []
    }'::jsonb,
    stride_analysis JSONB,  -- [{"category": "Tampering", "relevance": "high", "reasoning": "..."}]

    -- Embeddings (Phase 2)
    embedding vector(768),  -- nomic-embed-text (768) or text-embedding-3-small (1536)
    embedding_model VARCHAR(100),  -- "nomic-embed-text", "text-embedding-3-small", etc.
    embedding_generated_at TIMESTAMP WITH TIME ZONE,

    -- Links and references
    source_uri TEXT NOT NULL,
    source_locator TEXT,  -- md:heading:2, h2:3, etc.
    section_path TEXT[],  -- ["OWASP Top 10", "A01", "Description"]

    -- Provenance (Audit trail)
    source_file_path TEXT,
    source_file_hash VARCHAR(64),
    ingestion_id VARCHAR(200),  -- "owasp_top10_2025_20250123"
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    pipeline_version VARCHAR(50),

    -- Metadata
    publisher VARCHAR(100),
    edition VARCHAR(50),
    version VARCHAR(50),
    metadata JSONB,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT fk_document FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);

-- Indexes for fast queries
CREATE INDEX idx_chunks_doc ON chunks(doc_id);
CREATE INDEX idx_chunks_type ON chunks(chunk_type);
CREATE INDEX idx_chunks_canonical ON chunks(canonical_id);
CREATE INDEX idx_chunks_ingestion ON chunks(ingestion_id);
CREATE INDEX idx_chunks_tags ON chunks USING gin (tags);
CREATE INDEX idx_chunks_stride ON chunks USING gin ((tags->'stride'));
CREATE INDEX idx_chunks_taxonomy ON chunks USING gin ((tags->'taxonomy'));
CREATE INDEX idx_chunks_asset_types ON chunks USING gin ((tags->'asset_types'));

-- Vector similarity search index (Phase 2)
-- Note: Create this AFTER loading data for better performance
-- CREATE INDEX idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

COMMENT ON TABLE chunks IS 'Knowledge chunks with STRIDE enrichment and vector embeddings';
COMMENT ON COLUMN chunks.embedding IS 'Vector embedding for semantic search (768 or 1536 dimensions)';
COMMENT ON COLUMN chunks.tags IS 'STRIDE categories, CWE/CAPEC references, asset types, etc.';
COMMENT ON COLUMN chunks.metadata IS 'Flexible JSONB for chunk-type-specific data (e.g., link_uri for related_link chunks)';

-- ============================================================================
-- LLM_INTERACTIONS: Track all LLM requests/responses for audit
-- ============================================================================
CREATE TABLE llm_interactions (
    interaction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    doc_id UUID REFERENCES documents(doc_id) ON DELETE CASCADE,

    -- LLM details
    llm_provider VARCHAR(50),  -- openai, anthropic, bedrock
    llm_model VARCHAR(100),    -- gpt-4o-mini, claude-3, etc.

    -- Request
    prompt TEXT NOT NULL,
    prompt_template VARCHAR(200),
    prompt_hash VARCHAR(64),  -- SHA256 of prompt

    -- Response
    response JSONB NOT NULL,  -- Full LLM response
    response_hash VARCHAR(64),  -- SHA256 of response

    -- Metadata
    operation VARCHAR(50),  -- 'ingest', 'enrich', 'validate'
    tokens_used INTEGER,
    cost_usd DECIMAL(10, 6),
    duration_ms INTEGER,

    -- Status
    status VARCHAR(20),  -- success, failure, partial
    error_message TEXT,

    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(200)
);

CREATE INDEX idx_llm_interactions_doc ON llm_interactions(doc_id);
CREATE INDEX idx_llm_interactions_model ON llm_interactions(llm_model);
CREATE INDEX idx_llm_interactions_created ON llm_interactions(created_at DESC);

COMMENT ON TABLE llm_interactions IS 'Complete audit trail of all LLM API calls';
COMMENT ON COLUMN llm_interactions.response IS 'Full JSON response from LLM for reproducibility';

-- ============================================================================
-- AUDIT_LOG: Track all operations for compliance
-- ============================================================================
CREATE TABLE audit_log (
    audit_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    action VARCHAR(50) NOT NULL,  -- ingest, enrich, embed, reindex, query, etc.
    user_id VARCHAR(200),
    dataset_id VARCHAR(100),
    doc_id UUID,
    details JSONB,  -- Operation-specific details
    status VARCHAR(20),  -- success, failure, partial
    error_message TEXT,
    duration_ms INTEGER,
    cost_usd DECIMAL(10, 6)
);

CREATE INDEX idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_dataset ON audit_log(dataset_id);
CREATE INDEX idx_audit_user ON audit_log(user_id);

COMMENT ON TABLE audit_log IS 'Complete audit trail of all system operations';

-- ============================================================================
-- VIEWS: Convenient queries for common use cases
-- ============================================================================

-- View: All weaknesses with STRIDE mapping
CREATE VIEW v_weaknesses_with_stride AS
SELECT
    c.chunk_id,
    c.canonical_id,
    c.title,
    c.chunk_type,
    c.tags->'stride' as stride_categories,
    c.tags->'taxonomy' as taxonomy,
    c.tags->'asset_types' as asset_types,
    d.dataset_id,
    d.version,
    c.source_uri,
    c.ingested_at
FROM chunks c
JOIN documents d ON c.doc_id = d.doc_id
WHERE c.chunk_type IN ('weakness', 'risk')
  AND jsonb_array_length(c.tags->'stride') > 0;

COMMENT ON VIEW v_weaknesses_with_stride IS 'All weaknesses with STRIDE threat categorization';

-- View: Dataset statistics
CREATE VIEW v_dataset_stats AS
SELECT
    ds.dataset_id,
    ds.version,
    ds.publisher,
    COUNT(DISTINCT d.doc_id) as total_documents,
    COUNT(c.chunk_id) as total_chunks,
    COUNT(c.chunk_id) FILTER (WHERE c.embedding IS NOT NULL) as chunks_with_embeddings,
    COUNT(c.chunk_id) FILTER (WHERE c.chunk_type = 'weakness') as weaknesses,
    COUNT(c.chunk_id) FILTER (WHERE c.chunk_type = 'mitigation') as mitigations,
    COUNT(c.chunk_id) FILTER (WHERE c.chunk_type = 'attack_scenario') as attack_scenarios,
    ds.created_at
FROM datasets ds
LEFT JOIN documents d ON ds.dataset_id = d.dataset_id
LEFT JOIN chunks c ON d.doc_id = c.doc_id
GROUP BY ds.dataset_id, ds.version, ds.publisher, ds.created_at;

COMMENT ON VIEW v_dataset_stats IS 'Statistics for each dataset version';

-- View: Latest/Active chunks only
CREATE VIEW v_active_chunks AS
SELECT c.*
FROM chunks c
JOIN documents d ON c.doc_id = d.doc_id
JOIN datasets ds ON d.dataset_id = ds.dataset_id
WHERE ds.active = true;

COMMENT ON VIEW v_active_chunks IS 'Only chunks from active (non-deprecated) dataset versions';

-- ============================================================================
-- FUNCTIONS: Audit trail automation
-- ============================================================================

-- Function: Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers: Auto-update timestamps
CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chunks_updated_at BEFORE UPDATE ON chunks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function: Log audit trail
CREATE OR REPLACE FUNCTION log_audit(
    p_action VARCHAR(50),
    p_user_id VARCHAR(200),
    p_dataset_id VARCHAR(100) DEFAULT NULL,
    p_doc_id UUID DEFAULT NULL,
    p_details JSONB DEFAULT NULL,
    p_status VARCHAR(20) DEFAULT 'success',
    p_error_message TEXT DEFAULT NULL,
    p_duration_ms INTEGER DEFAULT NULL,
    p_cost_usd DECIMAL(10, 6) DEFAULT NULL
)
RETURNS void AS $$
BEGIN
    INSERT INTO audit_log (
        action, user_id, dataset_id, doc_id, details,
        status, error_message, duration_ms, cost_usd
    ) VALUES (
        p_action, p_user_id, p_dataset_id, p_doc_id, p_details,
        p_status, p_error_message, p_duration_ms, p_cost_usd
    );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION log_audit IS 'Helper function to log operations to audit trail';

-- ============================================================================
-- SAMPLE QUERIES (for testing)
-- ============================================================================

-- Find all XSS weaknesses across all versions
-- SELECT * FROM v_weaknesses_with_stride
-- WHERE canonical_id = 'CWE-79'
-- ORDER BY ingested_at DESC;

-- Find chunks with high STRIDE relevance for Information Disclosure
-- SELECT chunk_id, title, canonical_id, stride_analysis
-- FROM chunks
-- WHERE stride_analysis @> '[{"category": "Information Disclosure", "relevance": "high"}]'::jsonb;

-- Find all mitigations for SQL Injection
-- SELECT c.title, c.text, c.source_uri
-- FROM chunks c
-- WHERE c.chunk_type = 'mitigation'
--   AND c.tags->'taxonomy' ? 'CWE-89';

-- Semantic search (after embeddings are generated)
-- SELECT chunk_id, title, 1 - (embedding <=> $1::vector) as similarity
-- FROM chunks
-- WHERE chunk_type = 'mitigation'
--   AND tags->'asset_types' ? 'API'
-- ORDER BY embedding <=> $1::vector
-- LIMIT 10;

-- Dataset version comparison
-- SELECT * FROM v_dataset_stats
-- WHERE dataset_id = 'owasp_top10'
-- ORDER BY version DESC;
