import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || ''
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

// During build, these might be empty - that's OK
// They'll be injected at runtime
if (!supabaseUrl || !supabaseAnonKey) {
  console.warn('Supabase environment variables not found - they must be set at runtime')
}

// Create client with defaults if env vars are missing (for build time)
export const supabase = supabaseUrl && supabaseAnonKey 
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true
      }
    })
  : null as any // Type assertion for build time when env vars aren't available

