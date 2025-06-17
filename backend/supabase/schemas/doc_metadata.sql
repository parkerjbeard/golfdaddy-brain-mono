-- Table to store metadata about documentation stored in Git repositories
CREATE TABLE IF NOT EXISTS public.doc_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_git_url TEXT NOT NULL,
    doc_file_path TEXT NOT NULL,
    title TEXT,
    associated_task_id UUID REFERENCES public.tasks(id) ON DELETE SET NULL,
    last_known_commit_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for task association
CREATE INDEX IF NOT EXISTS idx_doc_metadata_task ON public.doc_metadata(associated_task_id);

-- Enable RLS
ALTER TABLE public.doc_metadata ENABLE ROW LEVEL SECURITY;

-- Simple policy allowing authenticated access
CREATE POLICY "Authenticated access to doc_metadata"
    ON public.doc_metadata
    FOR ALL
    USING (auth.role() = 'authenticated');

-- Trigger to maintain updated_at timestamp
DROP TRIGGER IF EXISTS doc_metadata_updated_at ON public.doc_metadata;
CREATE TRIGGER doc_metadata_updated_at
    BEFORE UPDATE ON public.doc_metadata
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
