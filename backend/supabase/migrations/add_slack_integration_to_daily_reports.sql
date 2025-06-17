-- Migration to add Slack integration fields to daily_reports table

-- Add Slack integration fields
ALTER TABLE public.daily_reports
ADD COLUMN IF NOT EXISTS slack_thread_ts text,
ADD COLUMN IF NOT EXISTS slack_channel_id text,
ADD COLUMN IF NOT EXISTS conversation_state jsonb DEFAULT '{}'::jsonb;

-- Add deduplication fields
ALTER TABLE public.daily_reports
ADD COLUMN IF NOT EXISTS deduplication_results jsonb,
ADD COLUMN IF NOT EXISTS confidence_scores jsonb,
ADD COLUMN IF NOT EXISTS commit_hours real,
ADD COLUMN IF NOT EXISTS additional_hours real;

-- Add indexes for Slack fields
CREATE INDEX IF NOT EXISTS idx_daily_reports_slack_thread_ts 
ON public.daily_reports USING btree (slack_thread_ts) 
WHERE slack_thread_ts IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_daily_reports_slack_channel_id 
ON public.daily_reports USING btree (slack_channel_id) 
WHERE slack_channel_id IS NOT NULL;

-- Add comments for new columns
COMMENT ON COLUMN public.daily_reports.slack_thread_ts IS 'Slack thread timestamp for ongoing conversations';
COMMENT ON COLUMN public.daily_reports.slack_channel_id IS 'Slack channel or DM ID where the report was submitted';
COMMENT ON COLUMN public.daily_reports.conversation_state IS 'State of the Slack conversation (status, history, etc.)';
COMMENT ON COLUMN public.daily_reports.deduplication_results IS 'Results from deduplication analysis comparing commits and report content';
COMMENT ON COLUMN public.daily_reports.confidence_scores IS 'Confidence scores for each deduplication match';
COMMENT ON COLUMN public.daily_reports.commit_hours IS 'Hours already accounted for in commits';
COMMENT ON COLUMN public.daily_reports.additional_hours IS 'Additional hours from daily report not in commits';