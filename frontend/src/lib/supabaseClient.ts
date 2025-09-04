import { createClient } from '@supabase/supabase-js'

declare global {
  interface Window {
    __APP_CONFIG__?: {
      VITE_SUPABASE_URL?: string
      VITE_SUPABASE_ANON_KEY?: string
    }
  }
}

const runtimeConfig = (typeof window !== 'undefined' && window.__APP_CONFIG__) || {}

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || runtimeConfig.VITE_SUPABASE_URL || ''
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || runtimeConfig.VITE_SUPABASE_ANON_KEY || ''

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
      console.error('Supabase environment variables are missing! Falling back to runtime config failed.')
      console.error('Required: VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY (or provided via /config.js)')
      // Return null instead of invalid client to prevent crashes
      return null
    })()
