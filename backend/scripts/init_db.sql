-- Initialize local PostgreSQL database for development
-- This mirrors the Supabase schema for local development

-- Create users table
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  slack_id TEXT UNIQUE,
  team TEXT,
  role VARCHAR(50) NOT NULL DEFAULT 'employee',
  avatar_url TEXT,
  metadata JSONB DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  github_username TEXT,
  team_id UUID,
  reports_to_id UUID REFERENCES users(id) ON DELETE SET NULL,
  personal_mastery JSONB DEFAULT '{}'::JSONB,
  last_login_at TIMESTAMPTZ,
  is_active BOOLEAN DEFAULT TRUE,
  preferences JSONB DEFAULT '{}'::JSONB
);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_slack_id ON users(slack_id);

-- Add check constraint for valid roles
ALTER TABLE users 
DROP CONSTRAINT IF EXISTS check_user_role;

ALTER TABLE users 
ADD CONSTRAINT check_user_role 
CHECK (role IN ('employee', 'manager', 'admin'));

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at 
BEFORE UPDATE ON users 
FOR EACH ROW 
EXECUTE FUNCTION update_updated_at_column();

-- Insert a default admin user (you can update the email/id to match your Supabase user)
-- Note: You'll need to update this ID to match your actual Supabase auth user ID
INSERT INTO users (id, email, name, role) 
VALUES 
  ('00000000-0000-0000-0000-000000000001', 'admin@example.com', 'Admin User', 'admin')
ON CONFLICT (id) DO UPDATE 
SET role = 'admin';

-- Create other tables that might be referenced
CREATE TABLE IF NOT EXISTS teams (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

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