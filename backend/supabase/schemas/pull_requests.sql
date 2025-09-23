-- Declarative schema for the pull_requests table
CREATE TABLE public.pull_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pr_number integer NOT NULL,
    repository_name character varying,
    repository_url character varying,
    title text,
    description text,
    author_id uuid REFERENCES public.users(id) ON DELETE SET NULL,
    author_github_username character varying,
    author_email character varying,
    url character varying,
    status character varying NOT NULL DEFAULT 'open',
    opened_at timestamp with time zone,
    closed_at timestamp with time zone,
    merged_at timestamp with time zone,
    activity_timestamp timestamp with time zone,
    ai_estimated_hours real,
    ai_summary text,
    ai_prompts text[],
    ai_analysis_notes jsonb,
    impact_score real,
    impact_category character varying,
    review_comments integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    UNIQUE (repository_name, pr_number)
);

CREATE INDEX idx_pull_requests_author ON public.pull_requests USING btree (author_id);
CREATE INDEX idx_pull_requests_activity_ts ON public.pull_requests USING btree (activity_timestamp);
CREATE INDEX idx_pull_requests_status ON public.pull_requests USING btree (status);

ALTER TABLE public.pull_requests ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Pull requests are viewable by authenticated users"
  ON public.pull_requests
  FOR SELECT
  USING (auth.role() = 'authenticated');

CREATE POLICY "Users can insert their own pull requests"
  ON public.pull_requests
  FOR INSERT
  WITH CHECK (auth.uid() = author_id OR auth.role() = 'authenticated');

CREATE POLICY "Users can update their own pull requests or admins"
  ON public.pull_requests
  FOR UPDATE
  USING (
    auth.uid() = author_id OR
    EXISTS (
      SELECT 1 FROM public.users WHERE id = auth.uid() AND role IN ('ADMIN', 'MANAGER')
    )
  );

CREATE POLICY "Users can delete their own pull requests or admins"
  ON public.pull_requests
  FOR DELETE
  USING (
    auth.uid() = author_id OR
    EXISTS (
      SELECT 1 FROM public.users WHERE id = auth.uid() AND role IN ('ADMIN', 'MANAGER')
    )
  );

CREATE OR REPLACE FUNCTION update_pull_requests_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_pull_requests_updated_at
BEFORE UPDATE ON public.pull_requests
FOR EACH ROW
EXECUTE FUNCTION update_pull_requests_updated_at();

COMMENT ON COLUMN public.pull_requests.pr_number IS 'Repository-specific pull request number';
COMMENT ON COLUMN public.pull_requests.activity_timestamp IS 'Primary timestamp used for activity rollups';
COMMENT ON COLUMN public.pull_requests.ai_prompts IS 'Array of prompts or nudges associated with the PR';
COMMENT ON COLUMN public.pull_requests.impact_score IS 'Business impact score calculated by AI';
