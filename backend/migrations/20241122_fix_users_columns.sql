-- Manual one-shot migration to align public.users schema with current User model.
-- Run this in Supabase SQL editor or any psql session pointed at the project DB.

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS github_username TEXT;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS team_id UUID;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS reports_to_id UUID REFERENCES public.users(id) ON DELETE SET NULL;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS preferences JSONB DEFAULT '{}'::JSONB;

-- Indexes to support lookups
CREATE INDEX IF NOT EXISTS idx_users_github_username ON public.users(github_username);

-- Add FK for team_id if teams table exists
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'teams') THEN
    ALTER TABLE public.users 
      DROP CONSTRAINT IF EXISTS fk_users_team_id;

    ALTER TABLE public.users
      ADD CONSTRAINT fk_users_team_id 
      FOREIGN KEY (team_id) 
      REFERENCES public.teams(id) 
      ON DELETE SET NULL;
  END IF;
END $$;
