-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Create table for storing document embeddings
CREATE TABLE IF NOT EXISTS doc_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES docs(id) ON DELETE CASCADE,
    doc_approval_id UUID REFERENCES doc_approvals(id) ON DELETE CASCADE,
    
    -- Document metadata
    title VARCHAR NOT NULL,
    content TEXT NOT NULL,
    doc_type VARCHAR,
    file_path VARCHAR,
    repository VARCHAR,
    commit_hash VARCHAR,
    
    -- Vector embedding (1536 dimensions for OpenAI ada-002)
    embedding vector(1536) NOT NULL,
    
    -- Metadata for search and filtering
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure only one embedding per document
    CONSTRAINT unique_doc_embedding UNIQUE (COALESCE(document_id, '00000000-0000-0000-0000-000000000000'::uuid), COALESCE(doc_approval_id, '00000000-0000-0000-0000-000000000000'::uuid))
);

-- Create indexes for efficient similarity search
CREATE INDEX idx_doc_embeddings_embedding ON doc_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_doc_embeddings_document_id ON doc_embeddings(document_id);
CREATE INDEX idx_doc_embeddings_repository ON doc_embeddings(repository);
CREATE INDEX idx_doc_embeddings_metadata ON doc_embeddings USING gin(metadata);

-- Create table for storing code context
CREATE TABLE IF NOT EXISTS code_context (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository VARCHAR NOT NULL,
    file_path VARCHAR NOT NULL,
    
    -- Code structure analysis
    module_name VARCHAR,
    class_names TEXT[], -- Array of class names in file
    function_names TEXT[], -- Array of function names
    imports TEXT[], -- Dependencies
    exports TEXT[], -- What this module exports
    
    -- Patterns and conventions
    design_patterns TEXT[], -- Identified design patterns
    coding_style JSONB, -- Style conventions detected
    
    -- Relationships
    dependencies TEXT[], -- Files this depends on
    dependents TEXT[], -- Files that depend on this
    related_issues TEXT[], -- GitHub issue numbers
    related_prs TEXT[], -- GitHub PR numbers
    
    -- Performance and technical details
    complexity_score FLOAT,
    test_coverage FLOAT,
    last_modified TIMESTAMP,
    
    -- Embedding for the entire file context
    context_embedding vector(1536),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_code_context UNIQUE (repository, file_path)
);

-- Indexes for code context
CREATE INDEX idx_code_context_repository ON code_context(repository);
CREATE INDEX idx_code_context_file_path ON code_context(file_path);
CREATE INDEX idx_code_context_embedding ON code_context USING ivfflat (context_embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_code_context_metadata ON code_context USING gin(metadata);

-- Create table for documentation relationships
CREATE TABLE IF NOT EXISTS doc_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_doc_id UUID NOT NULL,
    target_doc_id UUID NOT NULL,
    relationship_type VARCHAR NOT NULL, -- 'references', 'extends', 'implements', 'related', 'supersedes'
    confidence FLOAT DEFAULT 0.0, -- AI confidence in the relationship
    
    -- Additional context
    context TEXT,
    auto_detected BOOLEAN DEFAULT true,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_relationship UNIQUE (source_doc_id, target_doc_id, relationship_type)
);

-- Indexes for relationships
CREATE INDEX idx_doc_relationships_source ON doc_relationships(source_doc_id);
CREATE INDEX idx_doc_relationships_target ON doc_relationships(target_doc_id);
CREATE INDEX idx_doc_relationships_type ON doc_relationships(relationship_type);

-- Function to find similar documents
CREATE OR REPLACE FUNCTION find_similar_docs(
    query_embedding vector(1536),
    match_count INT DEFAULT 5,
    match_threshold FLOAT DEFAULT 0.8
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    title VARCHAR,
    content TEXT,
    repository VARCHAR,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        de.id,
        de.document_id,
        de.title,
        de.content,
        de.repository,
        1 - (de.embedding <=> query_embedding) AS similarity
    FROM doc_embeddings de
    WHERE 1 - (de.embedding <=> query_embedding) > match_threshold
    ORDER BY de.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Function to find related code context
CREATE OR REPLACE FUNCTION find_related_code(
    query_embedding vector(1536),
    target_repository VARCHAR,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    file_path VARCHAR,
    module_name VARCHAR,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        cc.id,
        cc.file_path,
        cc.module_name,
        1 - (cc.context_embedding <=> query_embedding) AS similarity
    FROM code_context cc
    WHERE cc.repository = target_repository
    AND cc.context_embedding IS NOT NULL
    ORDER BY cc.context_embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Add RLS policies
ALTER TABLE doc_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE code_context ENABLE ROW LEVEL SECURITY;
ALTER TABLE doc_relationships ENABLE ROW LEVEL SECURITY;

-- Policies for authenticated users
CREATE POLICY "Users can view all doc embeddings"
    ON doc_embeddings FOR SELECT
    USING (true);

CREATE POLICY "Service role can manage doc embeddings"
    ON doc_embeddings FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Users can view code context"
    ON code_context FOR SELECT
    USING (true);

CREATE POLICY "Service role can manage code context"
    ON code_context FOR ALL
    USING (auth.role() = 'service_role');