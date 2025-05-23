import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { supabase } from '@/lib/supabaseClient'; // Import your Supabase client
import { UserResponse, UserRole } from '@/types/user'; // Import your User type
import { Session, User as SupabaseAuthUser, SignUpWithPasswordCredentials } from '@supabase/supabase-js';
import { useAuthToken } from './useAuthToken';

// Use the environment variable for the API base URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'; // Fallback if not set, though it should be
const API_KEY = import.meta.env.VITE_API_KEY; // Get the API key from environment variables

// Check if API key is available during development only
if (import.meta.env.DEV && !API_KEY) {
  console.warn('API_KEY environment variable is not set. API requests might fail authentication.');
}

interface AuthContextType {
  session: Session | null;
  user: UserResponse | null;
  loading: boolean;
  isAdmin: boolean;
  loginWithEmailPassword: (credentials: SignUpWithPasswordCredentials) => Promise<void>;
  signUpWithEmailPassword: (credentials: SignUpWithPasswordCredentials) => Promise<void>;
  logout: () => Promise<void>;
  token: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const MAX_FETCH_RETRIES = 5;
const RETRY_DELAY_MS = 2000; // 2 seconds

// Helper to introduce a delay
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// Helper to fetch user profile from your backend
async function fetchUserProfile(authToken: string): Promise<UserResponse | null> {
  console.log("[fetchUserProfile] Attempting to fetch user profile.");
  for (let attempt = 1; attempt <= MAX_FETCH_RETRIES; attempt++) {
    try {
      console.log(`[fetchUserProfile] Fetch attempt ${attempt}/${MAX_FETCH_RETRIES} with token:`, authToken.substring(0, 10) + '...');
      
      const headers: Record<string, string> = {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json',
      };
      
      if (API_KEY) {
        headers['X-API-Key'] = API_KEY;
      }

      console.log("[fetchUserProfile] Making request to:", `${API_BASE_URL}/users/me`);
      const response = await fetch(`${API_BASE_URL}/users/me`, { 
        headers,
        method: 'GET',
        credentials: 'include' // Important for Supabase cookies if you evolve auth
      });
      
      console.log("[fetchUserProfile] Response status:", response.status);
      
      if (!response.ok) {
        if (response.status === 401) {
          let errorText = '';
          try { errorText = await response.text(); } catch (e) { /* ignore */ }
          console.warn(`[fetchUserProfile] Failed to fetch user profile: Unauthorized (Attempt ${attempt}). ${errorText ? `Details: ${errorText}` : ''}`);
          if (import.meta.env.DEV && !API_KEY && errorText.includes('API key')) {
            console.warn('[fetchUserProfile] Authentication failed likely due to missing API key. Check environment variables.');
          }
          return null; // Non-retryable for 401
        }
        // For other non-ok statuses, treat as potentially retryable if network related, or break if server error
        const errorData = await response.json().catch(() => ({ detail: `HTTP error ${response.status}` }));
        throw new Error(errorData.detail || `Failed to fetch user profile with status ${response.status}`);
      }
      
      const userData = await response.json();
      console.log("[fetchUserProfile] User data retrieved successfully.");
      return userData;

    } catch (error: any) {
      console.error(`[fetchUserProfile] Error on attempt ${attempt}:`, error.message);
      
      // Check for specific retryable network error messages (case-insensitive)
      const errorMessage = String(error.message).toLowerCase();
      const isRetryableNetworkError = 
        errorMessage.includes('failed to fetch') || // Generic browser network error
        errorMessage.includes('connectionrefused') ||
        errorMessage.includes('connection refused') ||
        errorMessage.includes('failedtoopensocket') ||
        errorMessage.includes('unable to connect');

      if (isRetryableNetworkError && attempt < MAX_FETCH_RETRIES) {
        console.log(`[fetchUserProfile] Retryable network error. Retrying in ${RETRY_DELAY_MS / 1000}s...`);
        await delay(RETRY_DELAY_MS);
      } else if (isRetryableNetworkError && attempt === MAX_FETCH_RETRIES) {
        console.error("[fetchUserProfile] Max retries reached for network error. Giving up.");
        return null; // Give up after max retries for network issues
      } else {
        // Non-retryable error (e.g., JSON parsing error, server-side error not caught above, or programmatic error)
        console.error("[fetchUserProfile] Non-retryable error or max retries reached for other errors. Giving up.");
        return null; // Give up for non-network errors or if it's a non-retryable network error
      }
    }
  }
  console.warn("[fetchUserProfile] Exhausted all attempts to fetch user profile or encountered non-retryable error.");
  return null; // Fallback, should ideally be handled within the loop
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<UserResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const tokenManager = useAuthToken();
  console.log("[AuthProvider] Initializing. Loading:", loading);

  useEffect(() => {
    console.log("[AuthProvider] useEffect started.");
    setLoading(true);
    const getInitialSession = async () => {
      console.log("[AuthProvider] getInitialSession called.");
      try {
        const { data: { session: initialSession }, error } = await supabase.auth.getSession();
        if (error) {
          console.error("[AuthProvider] Error getting initial session:", error);
        }
        console.log("[AuthProvider] Initial session data:", initialSession ? 'Session found' : 'No session');
        setSession(initialSession);
        if (initialSession?.access_token) {
          console.log("[AuthProvider] Initial session has access token. Fetching profile.");
          tokenManager.setToken(initialSession.access_token);
          
          try {
            const profile = await fetchUserProfile(initialSession.access_token);
            console.log("[AuthProvider] Profile fetched:", profile ? 'Profile found' : 'No profile found');
            setUser(profile);
            setIsAdmin(profile?.role === UserRole.ADMIN);
          } catch (profileError) {
            console.error("[AuthProvider] Error fetching user profile:", profileError);
            // Don't clear user data if profile fetch fails - may be temporary network issue
          }
        } else {
          console.log("[AuthProvider] No initial session or no access token.");
          tokenManager.removeToken();
          setUser(null);
          setIsAdmin(false);
        }
      } catch (e) {
        console.error("[AuthProvider] EXCEPTION in getInitialSession:", e);
      } finally {
        setLoading(false);
        console.log("[AuthProvider] getInitialSession finished. Loading:", false);
      }
    };

    getInitialSession();

    console.log("[AuthProvider] Setting up onAuthStateChange listener.");
    const { data: { subscription: authSubscription } } = supabase.auth.onAuthStateChange(
      async (_event, newSession) => {
        console.log("[AuthProvider] onAuthStateChange triggered. Event:", _event, "New session:", newSession ? 'Session exists' : 'No session');
        setLoading(true);
        try {
          setSession(newSession);
          if (newSession?.access_token) {
            console.log("[AuthProvider] onAuthStateChange: New session has access token. Fetching profile.");
            tokenManager.setToken(newSession.access_token);
            
            try {
              const profile = await fetchUserProfile(newSession.access_token);
              console.log("[AuthProvider] onAuthStateChange: Profile fetched:", profile ? 'Profile found' : 'No profile found');
              
              if (profile) {
                setUser(profile);
                setIsAdmin(profile?.role === UserRole.ADMIN);
              } else {
                // Handle case where backend could not return a user profile
                console.warn("[AuthProvider] Backend returned no user profile. Creating fallback profile from auth session");
                
                // Optionally build a minimal user from auth data if backend profile fetch fails
                if (newSession.user) {
                  const fallbackUser = {
                    id: newSession.user.id,
                    email: newSession.user.email,
                    name: newSession.user.email?.split('@')[0] || 'Unknown User',
                    role: UserRole.VIEWER // Default lowest-privilege role
                  };
                  setUser(fallbackUser as UserResponse);
                  setIsAdmin(false);
                }
              }
            } catch (profileError) {
              console.error("[AuthProvider] Error fetching user profile:", profileError);
            }
          } else {
            console.log("[AuthProvider] onAuthStateChange: No new session or no access token.");
            tokenManager.removeToken();
            setUser(null);
            setIsAdmin(false);
          }
        } catch (e) {
          console.error("[AuthProvider] EXCEPTION in onAuthStateChange:", e);
        } finally {
          setLoading(false);
          console.log("[AuthProvider] onAuthStateChange finished. Loading:", false);
        }
      }
    );

    return () => {
      console.log("[AuthProvider] useEffect cleanup. Unsubscribing listener.");
      authSubscription?.unsubscribe();
    };
  }, []);

  const loginWithEmailPassword = async (credentials: SignUpWithPasswordCredentials) => {
    setLoading(true);
    try {
      const { error } = await supabase.auth.signInWithPassword(credentials);
      if (error) {
        console.error('Error logging in:', error.message);
        throw error; // Re-throw error to be caught in UI
      }
      // onAuthStateChange will handle the rest
    } catch (error) {
      console.error('Exception during login:', error);
      throw error;
    } finally {
      // Don't set loading=false here, as onAuthStateChange will handle that
      // but make sure it doesn't stay stuck if onAuthStateChange doesn't fire
      setTimeout(() => {
        setLoading(false);
      }, 5000); // Safety timeout to ensure loading state doesn't get stuck
    }
  };

  const signUpWithEmailPassword = async (credentials: SignUpWithPasswordCredentials) => {
    setLoading(true);
    try {
      const { data, error } = await supabase.auth.signUp(credentials);
      if (error) {
        console.error('Error signing up:', error.message);
        throw error; // Re-throw error to be caught in UI
      }
      // For Supabase, a signUp might automatically sign in the user or send a confirmation email.
      // If it sends a confirmation email, onAuthStateChange might not fire immediately with a session.
      // The UI should inform the user to check their email if data.session is null and data.user is not null.
      if (data.session) {
        // Already handled by onAuthStateChange if session is immediately available
      } else if (data.user && !data.session) {
        // User created but needs confirmation
        console.log('Sign up successful, please check your email for confirmation.');
        // Potentially set some state here to inform UI if needed, though onAuthStateChange should eventually reflect confirmed state
      }
      // setLoading(false); // onAuthStateChange will set loading state
      return; // Return data or handle as needed if further action required here
    } catch (error) {
      console.error('Exception during signup:', error);
      throw error;
    } finally {
      // Don't set loading=false here, as onAuthStateChange will handle that
      // but make sure it doesn't stay stuck if onAuthStateChange doesn't fire
      setTimeout(() => {
        setLoading(false);
      }, 5000); // Safety timeout to ensure loading state doesn't get stuck
    }
  };

  const logout = async () => {
    setLoading(true);
    try {
      await supabase.auth.signOut();
      // onAuthStateChange will handle the rest
    } catch (error) {
      console.error('Error during logout:', error);
    } finally {
      // Don't set loading=false here, as onAuthStateChange will handle that
      // but make sure it doesn't stay stuck if onAuthStateChange doesn't fire
      setTimeout(() => {
        setLoading(false);
      }, 5000); // Safety timeout to ensure loading state doesn't get stuck
    }
  };

  // Listen for token expiration events
  useEffect(() => {
    const handleTokenExpired = () => {
      console.warn("[AuthProvider] Token expired, signing out user");
      logout();
    };

    const handleTokenRefreshNeeded = () => {
      console.info("[AuthProvider] Token refresh needed - should implement refresh logic here");
      // Could implement token refresh logic here if needed
    };

    window.addEventListener('auth-token-expired', handleTokenExpired);
    window.addEventListener('token-refresh-needed', handleTokenRefreshNeeded);

    return () => {
      window.removeEventListener('auth-token-expired', handleTokenExpired);
      window.removeEventListener('token-refresh-needed', handleTokenRefreshNeeded);
    };
  }, []);

  console.log("[AuthProvider] Rendering AuthContext.Provider. Loading:", loading, "User:", user ? 'User exists' : 'No user');
  return (
    <AuthContext.Provider value={{
      session, 
      user, 
      loading, 
      loginWithEmailPassword,
      signUpWithEmailPassword,
      logout, 
      isAdmin, 
      token: tokenManager.getToken()
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
