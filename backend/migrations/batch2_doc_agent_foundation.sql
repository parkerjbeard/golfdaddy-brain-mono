-- Batch 2: Database & Data Layer Foundation
-- This migration creates the core tables for the documentation agent system
-- with pgvector support for embeddings and comprehensive indexing

-- Enable pgvector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- 1. DOC_CHUNKS TABLE - Document chunks with vector embeddings
-- ============================================================================
CREATE TABLE IF NOT EXISTS doc_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Document identification
    repo VARCHAR NOT NULL,
    path VARCHAR NOT NULL,
    heading VARCHAR,
    order_key INTEGER NOT NULL,  -- For maintaining chunk order
    
    -- Content
    content TEXT NOT NULL,
    
    -- Vector embedding (3072 dimensions for text-embedding-3-large)
    embedding vector(3072) NOT NULL,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure unique chunks per document
    CONSTRAINT unique_doc_chunk UNIQUE (repo, path, order_key)
);

-- Create indexes for doc_chunks
CREATE INDEX idx_doc_chunks_repo ON doc_chunks(repo);
CREATE INDEX idx_doc_chunks_path ON doc_chunks(path);
CREATE INDEX idx_doc_chunks_repo_path ON doc_chunks(repo, path);
CREATE INDEX idx_doc_chunks_repo_path_order ON doc_chunks(repo, path, order_key);

-- Create HNSW index for vector similarity search (more accurate than IVFFlat)
CREATE INDEX idx_doc_chunks_embedding ON doc_chunks 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ============================================================================
-- 2. CODE_SYMBOLS TABLE - AST-parsed code symbols with embeddings
-- ============================================================================
CREATE TABLE IF NOT EXISTS code_symbols (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Symbol location
    repo VARCHAR NOT NULL,
    path VARCHAR NOT NULL,
    lang VARCHAR NOT NULL,  -- Language: python, typescript, etc.
    
    -- Symbol details
    kind VARCHAR NOT NULL,  -- class, function, method, interface, etc.
    name VARCHAR NOT NULL,
    sig TEXT,  -- Signature (function params, class inheritance, etc.)
    span JSONB,  -- Line/column span: {"start": {"line": 10, "col": 0}, "end": {"line": 20, "col": 0}}
    docstring TEXT,  -- Extracted documentation
    
    -- Vector embedding (3072 dimensions for text-embedding-3-large)
    embedding vector(3072),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure unique symbols
    CONSTRAINT unique_code_symbol UNIQUE (repo, path, kind, name)
);

-- Create indexes for code_symbols
CREATE INDEX idx_code_symbols_repo ON code_symbols(repo);
CREATE INDEX idx_code_symbols_path ON code_symbols(path);
CREATE INDEX idx_code_symbols_name ON code_symbols(name);
CREATE INDEX idx_code_symbols_kind ON code_symbols(kind);
CREATE INDEX idx_code_symbols_repo_path ON code_symbols(repo, path);
CREATE INDEX idx_code_symbols_repo_kind ON code_symbols(repo, kind);
CREATE INDEX idx_code_symbols_repo_name ON code_symbols(repo, name);

-- Create HNSW index for vector similarity search
CREATE INDEX idx_code_symbols_embedding ON code_symbols 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ============================================================================
-- 3. PROPOSALS TABLE - Documentation change proposals
-- ============================================================================
CREATE TABLE IF NOT EXISTS proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source information
    commit VARCHAR NOT NULL,  -- Commit hash that triggered this
    repo VARCHAR NOT NULL,
    
    -- Proposal content
    patch TEXT NOT NULL,  -- The proposed documentation patch
    targets VARCHAR[] DEFAULT '{}',  -- Target files to be modified
    
    -- Status tracking
    status VARCHAR DEFAULT 'pending',  -- pending, approved, rejected, expired, applied
    
    -- Quality scores
    scores JSONB DEFAULT '{}',  -- {"relevance": 0.9, "accuracy": 0.85, "completeness": 0.8}
    
    -- Cost tracking
    cost_cents INTEGER DEFAULT 0,  -- Cost in cents for AI generation
    
    -- Additional metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    CONSTRAINT unique_proposal_commit UNIQUE (commit, repo)
);

-- Create indexes for proposals
CREATE INDEX idx_proposals_commit ON proposals(commit);
CREATE INDEX idx_proposals_repo ON proposals(repo);
CREATE INDEX idx_proposals_status ON proposals(status);
CREATE INDEX idx_proposals_created_at ON proposals(created_at DESC);

-- ============================================================================
-- 4. ENHANCE DOC_APPROVALS TABLE - Add dashboard integration fields
-- ============================================================================

-- Add new columns to existing doc_approvals table
ALTER TABLE doc_approvals 
ADD COLUMN IF NOT EXISTS proposal_id UUID REFERENCES proposals(id) ON DELETE SET NULL;

ALTER TABLE doc_approvals
ADD COLUMN IF NOT EXISTS slack_ts VARCHAR;

ALTER TABLE doc_approvals
ADD COLUMN IF NOT EXISTS opened_by VARCHAR;

ALTER TABLE doc_approvals
ADD COLUMN IF NOT EXISTS head_sha VARCHAR;

ALTER TABLE doc_approvals
ADD COLUMN IF NOT EXISTS check_run_id VARCHAR;

-- Change pr_number from VARCHAR to INTEGER if it exists as VARCHAR
DO $$ 
BEGIN
    -- Check if pr_number exists and is VARCHAR
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'doc_approvals' 
        AND column_name = 'pr_number' 
        AND data_type = 'character varying'
    ) THEN
        -- First, ensure no non-numeric values
        UPDATE doc_approvals 
        SET pr_number = NULL 
        WHERE pr_number IS NOT NULL 
        AND pr_number !~ '^\d+$';
        
        -- Change column type
        ALTER TABLE doc_approvals 
        ALTER COLUMN pr_number TYPE INTEGER 
        USING pr_number::INTEGER;
    ELSIF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'doc_approvals' 
        AND column_name = 'pr_number'
    ) THEN
        -- Add column if it doesn't exist
        ALTER TABLE doc_approvals 
        ADD COLUMN pr_number INTEGER;
    END IF;
END $$;

-- Add indexes for new fields
CREATE INDEX IF NOT EXISTS idx_doc_approvals_proposal_id ON doc_approvals(proposal_id);
CREATE INDEX IF NOT EXISTS idx_doc_approvals_pr_number ON doc_approvals(pr_number);
CREATE INDEX IF NOT EXISTS idx_doc_approvals_check_run_id ON doc_approvals(check_run_id);

-- ============================================================================
-- 5. EMBEDDINGS_META TABLE - Track embedding model versions
-- ============================================================================
CREATE TABLE IF NOT EXISTS embeddings_meta (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Model information
    model VARCHAR NOT NULL UNIQUE,  -- e.g., "text-embedding-3-large"
    dim INTEGER NOT NULL,  -- Dimension size (e.g., 3072)
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert current embedding model metadata
INSERT INTO embeddings_meta (model, dim)
VALUES ('text-embedding-3-large', 3072)
ON CONFLICT (model) DO NOTHING;

-- ============================================================================
-- 6. HELPER FUNCTIONS FOR VECTOR SEARCH
-- ============================================================================

-- Function to find similar document chunks
CREATE OR REPLACE FUNCTION find_similar_chunks(
    query_embedding vector(3072),
    target_repo VARCHAR,
    match_count INT DEFAULT 10,
    match_threshold FLOAT DEFAULT 0.7
)
RETURNS TABLE (
    id UUID,
    repo VARCHAR,
    path VARCHAR,
    heading VARCHAR,
    content TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        dc.id,
        dc.repo,
        dc.path,
        dc.heading,
        dc.content,
        1 - (dc.embedding <=> query_embedding) AS similarity
    FROM doc_chunks dc
    WHERE dc.repo = target_repo
    AND 1 - (dc.embedding <=> query_embedding) > match_threshold
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Function to find similar code symbols
CREATE OR REPLACE FUNCTION find_similar_symbols(
    query_embedding vector(3072),
    target_repo VARCHAR,
    symbol_kind VARCHAR DEFAULT NULL,
    match_count INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    repo VARCHAR,
    path VARCHAR,
    kind VARCHAR,
    name VARCHAR,
    sig TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        cs.id,
        cs.repo,
        cs.path,
        cs.kind,
        cs.name,
        cs.sig,
        1 - (cs.embedding <=> query_embedding) AS similarity
    FROM code_symbols cs
    WHERE cs.repo = target_repo
    AND cs.embedding IS NOT NULL
    AND (symbol_kind IS NULL OR cs.kind = symbol_kind)
    ORDER BY cs.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ============================================================================
-- 7. ROW LEVEL SECURITY POLICIES
-- ============================================================================

-- Enable RLS on new tables
ALTER TABLE doc_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE code_symbols ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE embeddings_meta ENABLE ROW LEVEL SECURITY;

-- Policies for doc_chunks
CREATE POLICY "Users can view all doc chunks"
    ON doc_chunks FOR SELECT
    USING (true);

CREATE POLICY "Service role can manage doc chunks"
    ON doc_chunks FOR ALL
    USING (auth.role() = 'service_role');

-- Policies for code_symbols
CREATE POLICY "Users can view all code symbols"
    ON code_symbols FOR SELECT
    USING (true);

CREATE POLICY "Service role can manage code symbols"
    ON code_symbols FOR ALL
    USING (auth.role() = 'service_role');

-- Policies for proposals
CREATE POLICY "Users can view all proposals"
    ON proposals FOR SELECT
    USING (true);

CREATE POLICY "Service role can manage proposals"
    ON proposals FOR ALL
    USING (auth.role() = 'service_role');

-- Policies for embeddings_meta
CREATE POLICY "Users can view embeddings metadata"
    ON embeddings_meta FOR SELECT
    USING (true);

CREATE POLICY "Service role can manage embeddings metadata"
    ON embeddings_meta FOR ALL
    USING (auth.role() = 'service_role');

-- ============================================================================
-- 8. UPDATE EXISTING TABLES FOR NEW EMBEDDING DIMENSIONS
-- ============================================================================

-- Update existing embedding columns to support 3072 dimensions
-- Note: This will require re-generating embeddings for existing data

-- Update doc_embeddings table if it exists
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'doc_embeddings' 
        AND column_name = 'embedding'
    ) THEN
        -- Drop old indexes
        DROP INDEX IF EXISTS idx_doc_embeddings_embedding;
        
        -- Alter column to new dimension
        ALTER TABLE doc_embeddings 
        ALTER COLUMN embedding TYPE vector(3072);
        
        -- Recreate index with HNSW
        CREATE INDEX idx_doc_embeddings_embedding ON doc_embeddings 
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
    END IF;
END $$;

-- Update code_context table if it exists
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'code_context' 
        AND column_name = 'context_embedding'
    ) THEN
        -- Drop old indexes
        DROP INDEX IF EXISTS idx_code_context_embedding;
        
        -- Alter column to new dimension
        ALTER TABLE code_context 
        ALTER COLUMN context_embedding TYPE vector(3072);
        
        -- Recreate index with HNSW
        CREATE INDEX idx_code_context_embedding ON code_context 
            USING hnsw (context_embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
    END IF;
END $$;

-- ============================================================================
-- 9. MIGRATION COMPLETION LOG
-- ============================================================================
DO $$
BEGIN
    RAISE NOTICE 'Batch 2 migration completed successfully';
    RAISE NOTICE 'Created tables: doc_chunks, code_symbols, proposals, embeddings_meta';
    RAISE NOTICE 'Enhanced table: doc_approvals';
    RAISE NOTICE 'Updated embedding dimensions to 3072 for text-embedding-3-large';
END $$;