import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || ''
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

// During build, these might be empty - that's OK for unified deployment
// They'll be injected at build time via Docker args
if (!supabaseUrl || !supabaseAnonKey) {
  console.warn('Supabase environment variables not found during build')
}

// Create client - for unified deployment, we expect these to be available at build time
export const supabase = supabaseUrl && supabaseAnonKey 
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true
      }
    })
  : createClient('placeholder', 'placeholder') // Fallback to prevent build errors

