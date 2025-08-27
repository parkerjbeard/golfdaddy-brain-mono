import React, { createContext, useContext, useEffect, useState } from 'react';
import { Session } from '@supabase/supabase-js';
import { supabase } from '../lib/supabaseClient';
import { secureStorage } from '../services/secureStorage';
import { TokenCleanupService } from '../services/tokenCleanupService';
import logger from '../utils/logger';

interface UserProfile {
  id: string;
  email: string;
  role: 'employee' | 'manager' | 'admin';
  name?: string;
}

interface AuthContextType {
  session: Session | null;
  userProfile: UserProfile | null;
  loading: boolean;
  error: string | null;
  signIn: (email: string, password: string, rememberMe?: boolean) => Promise<{ error: Error | null }>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  session: null,
  userProfile: null,
  loading: true,
  error: null,
  signIn: async () => ({ error: null }),
  signOut: async () => {},
  refreshProfile: async () => {},
});

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

// Helper to get cached profile
const getCachedProfile = async (): Promise<UserProfile | null> => {
  try {
    const cached = await secureStorage.getItem<{ data: UserProfile; timestamp: number }>('userProfile');
    if (!cached) return null;
    
    // Cache for 5 minutes
    if (Date.now() - cached.timestamp < 5 * 60 * 1000) {
      return cached.data;
    }
    
    // Cache expired, remove it
    await secureStorage.removeItem('userProfile');
  } catch (e) {
    console.error('Failed to get cached profile:', e);
  }
  
  return null;
};

// Helper to cache profile
const cacheProfile = async (profile: UserProfile): Promise<void> => {
  try {
    await secureStorage.setItem('userProfile', {
      data: profile,
      timestamp: Date.now()
    }, {
      expiresIn: 5 * 60 * 1000, // 5 minutes
      tags: ['auth', 'profile']
    });
  } catch (error) {
    console.error('Failed to cache profile:', error);
  }
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [session, setSession] = useState<Session | null>(null);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchUserProfile = async (accessToken: string): Promise<UserProfile | null> => {
    try {
      // Check cache first
      const cached = await getCachedProfile();
      if (cached) {
        return cached;
      }

      // Fetch from API - note: auth endpoints are at /auth/* not /api/v1/auth/*
      // When running in development with Vite proxy, use relative URLs
      const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
      const isViteProxy = window.location.port === '8080'; // Vite dev server port
      const apiUrl = isViteProxy ? '/auth/me' : `${baseUrl}/auth/me`;
      
      // Production logging
      logger.logAuthEvent('Fetching user profile', { url: apiUrl, baseUrl });
      
      const response = await fetch(apiUrl, {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'X-API-Key': import.meta.env.VITE_API_KEY || 'dev-api-key',
        },
      });

      if (!response.ok) {
        logger.logAuthError('Profile fetch failed', {
          status: response.status,
          statusText: response.statusText,
          url: apiUrl
        });
        throw new Error(`Failed to fetch profile: ${response.status} ${response.statusText}`);
      }

      const profile = await response.json();
      
      // Cache the profile
      await cacheProfile(profile);
      
      return profile;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch user profile');
      
      // Fallback to creating a basic profile from Supabase data
      if (session?.user) {
        const fallbackProfile: UserProfile = {
          id: session.user.id,
          email: session.user.email || '',
          role: 'employee', // Default to employee (lowest permission)
          name: session.user.user_metadata?.name || session.user.email?.split('@')[0]
        };
        setUserProfile(fallbackProfile);
        return fallbackProfile;
      }
      
      return null;
    }
  };

  const refreshProfile = async () => {
    if (!session?.access_token) return;
    
    // Clear cache to force refresh
    await secureStorage.removeItem('userProfile');
    
    const profile = await fetchUserProfile(session.access_token);
    if (profile) {
      setUserProfile(profile);
    }
  };

  useEffect(() => {
    // Check if Supabase client is available
    if (!supabase) {
      setError('Authentication system unavailable - missing configuration');
      setLoading(false);
      return;
    }

    // Get initial session
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      setSession(session);
      
      if (session?.access_token) {
        try {
          const profile = await fetchUserProfile(session.access_token);
          if (profile) {
            setUserProfile(profile);
          }
        } catch (error) {
          // Error fetching user profile
        }
        setLoading(false);
      } else {
        setLoading(false);
      }
    }).catch(error => {
      // Error getting session
      setLoading(false);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (_event, session) => {
      setSession(session);
      
      if (session?.access_token) {
        const profile = await fetchUserProfile(session.access_token);
        if (profile) {
          setUserProfile(profile);
        }
      } else {
        setUserProfile(null);
        await secureStorage.removeItem('userProfile');
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  const signIn = async (email: string, password: string, rememberMe: boolean = false) => {
    try {
      if (!supabase) {
        throw new Error('Authentication system unavailable - missing configuration');
      }
      
      // Add timeout to the request
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
      
      try {
        // Set session persistence based on rememberMe
        // If rememberMe is true, session will persist for 30 days
        // If false, session will last for 12 hours (configured in Supabase dashboard)
        const { data, error } = await supabase.auth.signInWithPassword({
          email,
          password,
          options: {
            // This tells Supabase to use a longer-lived refresh token
            // The actual session duration is controlled by Supabase dashboard settings
            data: {
              rememberMe: rememberMe
            }
          }
        });
        
        clearTimeout(timeoutId);

        if (error) {
          return { error };
        }

        // Store remember me preference
        if (rememberMe) {
          await secureStorage.setItem('rememberMe', 'true', {
            tags: ['auth', 'preferences']
          });
        } else {
          await secureStorage.removeItem('rememberMe');
        }

        // Session and profile will be handled by the auth state change listener
        return { error: null };
      } catch (timeoutError) {
        clearTimeout(timeoutId);
        return { error: new Error('Network timeout - please check your connection') };
      }
    } catch (err) {
      return { error: err as Error };
    }
  };

  const signOut = async () => {
    try {
      if (!supabase) {
        console.warn('Authentication system unavailable during signOut');
        return;
      }
      await supabase.auth.signOut();
      setUserProfile(null);
      
      // Trigger comprehensive cleanup
      TokenCleanupService.triggerLogout();
      
      // Also remove specific items
      await secureStorage.removeItem('userProfile');
      await secureStorage.removeItem('rememberMe');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to sign out');
    }
  };

  return (
    <AuthContext.Provider
      value={{
        session,
        userProfile,
        loading,
        error,
        signIn,
        signOut,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

// Helper hooks for role checking
export const useHasRole = (requiredRoles: string | string[]) => {
  const { userProfile } = useAuth();
  
  if (!userProfile) return false;
  
  const roles = Array.isArray(requiredRoles) ? requiredRoles : [requiredRoles];
  return roles.includes(userProfile.role);
};

export const useIsAdmin = () => useHasRole('admin');
export const useIsManager = () => useHasRole(['manager', 'admin']);

export const useIsEmployee = () => useHasRole(['employee', 'manager', 'admin']);