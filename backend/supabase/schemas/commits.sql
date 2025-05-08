-- Declarative schema for the 'commits' table
CREATE TABLE public.commits (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    commit_hash character varying UNIQUE NOT NULL,
    commit_message character varying,
    commit_url character varying,
    commit_timestamp timestamp without time zone NOT NULL,
    author_id uuid REFERENCES public.users(id),
    author_github_username character varying,
    author_email character varying,
    repository_name character varying,
    repository_url character varying,
    branch character varying,
    diff_url character varying,
    ai_estimated_hours real, -- Use 'real' for float in PostgreSQL
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    lines_added integer,
    lines_deleted integer,
    changed_files jsonb, -- Use jsonb for better performance/indexing
    ai_analysis_notes text,
    complexity_score integer,
    risk_level character varying,
    risk_factor real
);

-- Add indexes for frequently queried columns
CREATE INDEX idx_commits_commit_hash ON public.commits USING btree (commit_hash);
CREATE INDEX idx_commits_commit_timestamp ON public.commits USING btree (commit_timestamp);
CREATE INDEX idx_commits_author_id ON public.commits USING btree (author_id);

-- Add RLS (Row Level Security)
ALTER TABLE public.commits ENABLE ROW LEVEL SECURITY;

-- Allow all authenticated users to view commits
CREATE POLICY "Commits are viewable by authenticated users" 
  ON public.commits 
  FOR SELECT 
  USING (auth.role() = 'authenticated');

-- Policy: Users can update their own commits or admins can update any commit
CREATE POLICY "Users can update their own commits" 
  ON public.commits 
  FOR UPDATE 
  USING (
    auth.uid() = author_id OR
    EXISTS (
      SELECT 1 FROM public.users 
      WHERE id = auth.uid() AND role = 'ADMIN'
    )
  );

-- Policy: Users can create commits
CREATE POLICY "Users can create commits" 
  ON public.commits 
  FOR INSERT 
  WITH CHECK (
    auth.uid() IS NOT NULL
  );

-- Policy: Only creators or admins can delete commits
CREATE POLICY "Only creators or admins can delete commits" 
  ON public.commits 
  FOR DELETE 
  USING (
    auth.uid() = author_id OR
    EXISTS (
      SELECT 1 FROM public.users 
      WHERE id = auth.uid() AND role = 'ADMIN'
    )
  );

-- Optional: Add trigger for updated_at timestamp (alternative to SQLAlchemy's onupdate)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_commits_updated_at
BEFORE UPDATE ON public.commits
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Add comments for columns (optional but good practice)
COMMENT ON COLUMN public.commits.id IS 'Unique identifier for the commit record';
COMMENT ON COLUMN public.commits.commit_hash IS 'The unique SHA hash of the Git commit';
COMMENT ON COLUMN public.commits.commit_message IS 'The commit message';
COMMENT ON COLUMN public.commits.commit_url IS 'URL link to the commit details (e.g., on GitHub)';
COMMENT ON COLUMN public.commits.commit_timestamp IS 'Timestamp when the commit was made';
COMMENT ON COLUMN public.commits.author_id IS 'Foreign key referencing the internal user associated with the commit';
COMMENT ON COLUMN public.commits.author_github_username IS 'Original GitHub username of the commit author';
COMMENT ON COLUMN public.commits.author_email IS 'Original email of the commit author';
COMMENT ON COLUMN public.commits.repository_name IS 'Name of the repository where the commit occurred';
COMMENT ON COLUMN public.commits.repository_url IS 'URL of the repository';
COMMENT ON COLUMN public.commits.branch IS 'The branch the commit was made on';
COMMENT ON COLUMN public.commits.diff_url IS 'URL to the diff patch for the commit';
COMMENT ON COLUMN public.commits.ai_estimated_hours IS 'AI-estimated hours for the work involved in the commit';
COMMENT ON COLUMN public.commits.created_at IS 'Timestamp when the record was created in the database';
COMMENT ON COLUMN public.commits.updated_at IS 'Timestamp when the record was last updated in the database';
COMMENT ON COLUMN public.commits.lines_added IS 'Number of lines added in the commit';
COMMENT ON COLUMN public.commits.lines_deleted IS 'Number of lines deleted in the commit';
COMMENT ON COLUMN public.commits.changed_files IS 'JSON array of file paths changed in the commit';
COMMENT ON COLUMN public.commits.ai_analysis_notes IS 'Text notes from the AI analysis of the commit';
COMMENT ON COLUMN public.commits.complexity_score IS 'AI-rated complexity score (e.g., 1-10)';
COMMENT ON COLUMN public.commits.risk_level IS 'AI-assessed risk level (e.g., low, medium, high)';
COMMENT ON COLUMN public.commits.risk_factor IS 'Multiplier based on risk level (e.g., 1.0, 1.5, 2.0)'; 