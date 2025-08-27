import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || ''
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

// Log environment variable status for debugging
console.log('Supabase config:', { 
  hasUrl: !!supabaseUrl, 
  hasKey: !!supabaseAnonKey,
  url: supabaseUrl ? `${supabaseUrl.substring(0, 20)}...` : 'missing'
})

// Create client - ensure we have valid URLs
export const supabase = supabaseUrl && supabaseAnonKey 
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true
      }
    })
  : (() => {
      console.error('Supabase environment variables are missing! Please check your Render environment group.')
      console.error('Required: VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY')
      // Return null instead of invalid client to prevent crashes
      return null
    })()

