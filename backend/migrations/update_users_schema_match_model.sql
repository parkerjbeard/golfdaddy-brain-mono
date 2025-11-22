-- Add missing columns to users table to match Pydantic model

ALTER TABLE users ADD COLUMN IF NOT EXISTS github_username TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS team_id UUID;
ALTER TABLE users ADD COLUMN IF NOT EXISTS reports_to_id UUID REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences JSONB DEFAULT '{}'::JSONB;

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_users_github_username ON users(github_username);

-- Add foreign key for team_id if teams table exists
DO $$ 
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'teams') THEN
    ALTER TABLE users 
    DROP CONSTRAINT IF EXISTS fk_users_team_id;
    
    ALTER TABLE users
    ADD CONSTRAINT fk_users_team_id 
    FOREIGN KEY (team_id) 
    REFERENCES teams(id) 
    ON DELETE SET NULL;
  END IF;
END $$;
