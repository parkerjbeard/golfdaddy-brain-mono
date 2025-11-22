-- Create users table for public profiles linked to auth.users
CREATE TABLE IF NOT EXISTS public.users (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT,
  name TEXT,
  slack_id TEXT UNIQUE,
  team TEXT,
  role TEXT NOT NULL DEFAULT 'USER',
  avatar_url TEXT,
  metadata JSONB DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  github_username TEXT,
  team_id UUID,
  reports_to_id UUID REFERENCES users(id) ON DELETE SET NULL,
  last_login_at TIMESTAMPTZ,
  is_active BOOLEAN DEFAULT TRUE,
  preferences JSONB DEFAULT '{}'::JSONB
);

-- Add RLS (Row Level Security) policies
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Allow logged-in users to read all user profiles
CREATE POLICY "Users are viewable by authenticated users" 
  ON public.users 
  FOR SELECT 
  USING (auth.role() = 'authenticated');

-- Only allow users to update their own profile
CREATE POLICY "Users can update own profile" 
  ON public.users 
  FOR UPDATE 
  USING (auth.uid() = id);

-- Only allow admins to insert new profiles 
-- (except for the initial profile created by auth triggers)
CREATE POLICY "Only admins can create user profiles" 
  ON public.users 
  FOR INSERT 
  WITH CHECK (
    auth.uid() = id OR -- Allow user to create their own profile
    EXISTS (
      SELECT 1 FROM public.users 
      WHERE id = auth.uid() AND role = 'ADMIN'
    )
  );

-- Setup function to automatically create a public profile when a new user signs up
CREATE OR REPLACE FUNCTION public.handle_new_user() 
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.users (id, email, role)
  VALUES (NEW.id, NEW.email, 'USER');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Setup trigger to call the function when a new user is created
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Update the user's updated_at timestamp on update
CREATE OR REPLACE FUNCTION public.set_updated_at() 
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS users_updated_at ON public.users;
CREATE TRIGGER users_updated_at
  BEFORE UPDATE ON public.users
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at(); 