-- Migration: drop personal_mastery column from users tables
-- Applies to both local dev (users) and Supabase (public.users)

-- Supabase schema
ALTER TABLE IF EXISTS public.users
  DROP COLUMN IF EXISTS personal_mastery;

-- Local/dev schema
ALTER TABLE IF EXISTS users
  DROP COLUMN IF EXISTS personal_mastery;

