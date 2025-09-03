-- Archive columns and constraints for data lifecycle management
-- This migration adds archive support to existing tables

-- Add archive columns to daily_reports table
ALTER TABLE public.daily_reports 
ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS archive_status TEXT DEFAULT 'active';

-- Add archive columns to commits table  
ALTER TABLE public.commits
ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS archive_status TEXT DEFAULT 'active';

-- Add archive columns to tasks table
ALTER TABLE public.tasks
ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS archive_status TEXT DEFAULT 'active';


-- Create enum for archive status
DO $$ BEGIN
    CREATE TYPE archive_status_enum AS ENUM ('active', 'archived', 'purged');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Update archive_status columns to use enum (optional, for better data integrity)
-- Note: This would require updating existing data first in production
-- ALTER TABLE public.daily_reports ALTER COLUMN archive_status TYPE archive_status_enum USING archive_status::archive_status_enum;
-- ALTER TABLE public.commits ALTER COLUMN archive_status TYPE archive_status_enum USING archive_status::archive_status_enum;
-- ALTER TABLE public.tasks ALTER COLUMN archive_status TYPE archive_status_enum USING archive_status::archive_status_enum;
-- ALTER TABLE public.docs ALTER COLUMN archive_status TYPE archive_status_enum USING archive_status::archive_status_enum;
-- ALTER TABLE public.doc_metadata ALTER COLUMN archive_status TYPE archive_status_enum USING archive_status::archive_status_enum;

-- Add indexes for archive queries
CREATE INDEX IF NOT EXISTS idx_daily_reports_archived_at ON public.daily_reports(archived_at);
CREATE INDEX IF NOT EXISTS idx_daily_reports_archive_status ON public.daily_reports(archive_status);

CREATE INDEX IF NOT EXISTS idx_commits_archived_at ON public.commits(archived_at);
CREATE INDEX IF NOT EXISTS idx_commits_archive_status ON public.commits(archive_status);

CREATE INDEX IF NOT EXISTS idx_tasks_archived_at ON public.tasks(archived_at);
CREATE INDEX IF NOT EXISTS idx_tasks_archive_status ON public.tasks(archive_status);


-- Create composite indexes for efficient active data queries
CREATE INDEX IF NOT EXISTS idx_daily_reports_active_by_date ON public.daily_reports(report_date) 
    WHERE archive_status = 'active';

CREATE INDEX IF NOT EXISTS idx_commits_active_by_timestamp ON public.commits(commit_timestamp)
    WHERE archive_status = 'active';

CREATE INDEX IF NOT EXISTS idx_tasks_active_by_status ON public.tasks(status, updated_at)
    WHERE archive_status = 'active';

-- Update RLS policies to exclude archived data by default
-- Note: This creates new policies, you might want to modify existing ones instead

-- Daily Reports: Exclude archived data from normal queries
DROP POLICY IF EXISTS "Users can manage their own daily reports" ON public.daily_reports;
CREATE POLICY "Users can manage their own active daily reports"
    ON public.daily_reports
    FOR ALL
    USING (auth.uid() = user_id AND (archive_status = 'active' OR archive_status IS NULL))
    WITH CHECK (auth.uid() = user_id);

-- Allow admins to see archived data
CREATE POLICY "Admins can manage all daily reports including archived"
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

-- Tasks: Exclude archived tasks from normal views
DROP POLICY IF EXISTS "Users can view their tasks" ON public.tasks;
CREATE POLICY "Users can view their active tasks" 
  ON public.tasks 
  FOR SELECT 
  USING (
    (archive_status = 'active' OR archive_status IS NULL) AND (
      auth.uid() IN (assignee_id, responsible_id, accountable_id) OR
      auth.uid() = ANY(consulted_ids) OR 
      auth.uid() = ANY(informed_ids) OR
      auth.uid() = creator_id OR
      EXISTS (
        SELECT 1 FROM public.users 
        WHERE id = auth.uid() AND role = 'ADMIN'
      )
    )
  );

-- Allow admins to see archived tasks
CREATE POLICY "Admins can view all tasks including archived" 
  ON public.tasks 
  FOR SELECT 
  USING (
    EXISTS (
      SELECT 1 FROM public.users 
      WHERE id = auth.uid() AND role = 'ADMIN'
    )
  );

-- Commits: Exclude archived commits from normal views  
DROP POLICY IF EXISTS "Commits are viewable by authenticated users" ON public.commits;
CREATE POLICY "Active commits are viewable by authenticated users" 
  ON public.commits 
  FOR SELECT 
  USING (
    auth.role() = 'authenticated' AND (archive_status = 'active' OR archive_status IS NULL)
  );

-- Allow admins to see archived commits
CREATE POLICY "Admins can view all commits including archived" 
  ON public.commits 
  FOR SELECT 
  USING (
    auth.role() = 'authenticated' AND EXISTS (
      SELECT 1 FROM public.users 
      WHERE id = auth.uid() AND role = 'ADMIN'
    )
  );


-- Create a function to automatically set archive status on insert
CREATE OR REPLACE FUNCTION public.set_default_archive_status()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.archive_status IS NULL THEN
        NEW.archive_status = 'active';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers to set default archive status
CREATE TRIGGER set_archive_status_daily_reports
    BEFORE INSERT ON public.daily_reports
    FOR EACH ROW EXECUTE FUNCTION public.set_default_archive_status();

CREATE TRIGGER set_archive_status_commits
    BEFORE INSERT ON public.commits
    FOR EACH ROW EXECUTE FUNCTION public.set_default_archive_status();

CREATE TRIGGER set_archive_status_tasks
    BEFORE INSERT ON public.tasks
    FOR EACH ROW EXECUTE FUNCTION public.set_default_archive_status();


-- Comments on new columns
COMMENT ON COLUMN public.daily_reports.archived_at IS 'Timestamp when the record was archived (soft deleted)';
COMMENT ON COLUMN public.daily_reports.archive_status IS 'Status of the record: active, archived, or purged';

COMMENT ON COLUMN public.commits.archived_at IS 'Timestamp when the record was archived (soft deleted)';
COMMENT ON COLUMN public.commits.archive_status IS 'Status of the record: active, archived, or purged';

COMMENT ON COLUMN public.tasks.archived_at IS 'Timestamp when the record was archived (soft deleted)';
COMMENT ON COLUMN public.tasks.archive_status IS 'Status of the record: active, archived, or purged';
