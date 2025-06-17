-- Declarative schema for the 'daily_reports' table
CREATE TABLE public.daily_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    report_date timestamp with time zone NOT NULL,
    raw_text_input text NOT NULL,
    clarified_tasks_summary text,
    ai_analysis jsonb,
    linked_commit_ids text[],
    overall_assessment_notes text,
    final_estimated_hours real,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

-- Create indexes for frequently queried columns
CREATE INDEX idx_daily_reports_user_id ON public.daily_reports USING btree (user_id);
CREATE INDEX idx_daily_reports_report_date ON public.daily_reports USING btree (report_date);

-- IMMUTABLE function to extract date from timestamptz
CREATE OR REPLACE FUNCTION public.get_date_immutable(ts timestamptz)
RETURNS date
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
  SELECT ts::date;
$$;

-- Unique index using the immutable function
CREATE UNIQUE INDEX idx_daily_reports_user_id_report_date ON public.daily_reports (user_id, public.get_date_immutable(report_date));


-- RLS (Row Level Security)
ALTER TABLE public.daily_reports ENABLE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY "Users can manage their own daily reports"
    ON public.daily_reports
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Admins can manage all daily reports"
    ON public.daily_reports
    FOR ALL
    USING (EXISTS (
        SELECT 1 FROM public.users
        WHERE id = auth.uid() AND role = 'ADMIN'
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM public.users
        WHERE id = auth.uid() AND role = 'ADMIN'
    ));

-- Trigger for updated_at timestamp
-- Ensure the function exists (it's also used by commits.sql, so might be created there)
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_daily_reports_updated_at
    BEFORE UPDATE ON public.daily_reports
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- Comments for columns
COMMENT ON COLUMN public.daily_reports.id IS 'Unique identifier for the daily report record';
COMMENT ON COLUMN public.daily_reports.user_id IS 'Foreign key referencing the user who submitted the report';
COMMENT ON COLUMN public.daily_reports.report_date IS 'The date for which the report is submitted';
COMMENT ON COLUMN public.daily_reports.raw_text_input IS 'Raw bullet points or text submitted by the employee';
COMMENT ON COLUMN public.daily_reports.clarified_tasks_summary IS 'AI-generated or user-clarified summary of tasks';
COMMENT ON COLUMN public.daily_reports.ai_analysis IS 'JSONB blob containing detailed AI analysis (estimated hours, difficulty, sentiment, key achievements, blockers, clarification requests)';
COMMENT ON COLUMN public.daily_reports.linked_commit_ids IS 'Array of commit SHAs linked to this daily report';
COMMENT ON COLUMN public.daily_reports.overall_assessment_notes IS 'Managerial or system-generated assessment notes';
COMMENT ON COLUMN public.daily_reports.final_estimated_hours IS 'Final estimated hours for the work reported, possibly adjusted by manager or AI';
COMMENT ON COLUMN public.daily_reports.created_at IS 'Timestamp when the record was created';
COMMENT ON COLUMN public.daily_reports.updated_at IS 'Timestamp when the record was last updated';