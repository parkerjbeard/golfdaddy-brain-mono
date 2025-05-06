import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { supabase } from '@/lib/supabaseClient'; // Import your Supabase client
import { UserResponse, UserRole } from '@/types/user'; // Import your User type
import { Session, User as SupabaseAuthUser, SignUpWithPasswordCredentials } from '@supabase/supabase-js';

const API_BASE_URL = '/api'; // Same as in UserManagementPage

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

// Helper to fetch user profile from your backend
async function fetchUserProfile(authToken: string): Promise<UserResponse | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/users/me`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json',
      },
    });
    if (!response.ok) {
      if (response.status === 401) {
        // Token might be invalid or expired, or user not found in your DB post-auth
        console.warn('Failed to fetch user profile: Unauthorized');
        return null;
      }
      const errorData = await response.json().catch(() => ({ detail: 'Network error or invalid JSON' }));
      throw new Error(errorData.detail || 'Failed to fetch user profile');
    }
    return response.json();
  } catch (error) {
    console.error("Error fetching user profile:", error);
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<UserResponse | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    setLoading(true);
    const getInitialSession = async () => {
      const { data: { session: initialSession } } = await supabase.auth.getSession();
      setSession(initialSession);
      if (initialSession?.access_token) {
        localStorage.setItem('authToken', initialSession.access_token);
        setToken(initialSession.access_token);
        const profile = await fetchUserProfile(initialSession.access_token);
        setUser(profile);
        setIsAdmin(profile?.role === UserRole.ADMIN);
      } else {
        localStorage.removeItem('authToken');
        setToken(null);
        setUser(null);
        setIsAdmin(false);
      }
      setLoading(false);
    };

    getInitialSession();

    const { data: authListener } = supabase.auth.onAuthStateChange(
      async (_event, newSession) => {
        setLoading(true);
        setSession(newSession);
        if (newSession?.access_token) {
          localStorage.setItem('authToken', newSession.access_token);
          setToken(newSession.access_token);
          const profile = await fetchUserProfile(newSession.access_token);
          setUser(profile);
          setIsAdmin(profile?.role === UserRole.ADMIN);
        } else {
          localStorage.removeItem('authToken');
          setToken(null);
          setUser(null);
          setIsAdmin(false);
        }
        setLoading(false);
      }
    );

    return () => {
      authListener?.unsubscribe();
    };
  }, []);

  const loginWithEmailPassword = async (credentials: SignUpWithPasswordCredentials) => {
    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword(credentials);
    if (error) {
      console.error('Error logging in:', error.message);
      setLoading(false); // Ensure loading is false on error
      throw error; // Re-throw error to be caught in UI
    }
    // onAuthStateChange will handle the rest
  };

  const signUpWithEmailPassword = async (credentials: SignUpWithPasswordCredentials) => {
    setLoading(true);
    const { data, error } = await supabase.auth.signUp(credentials);
    if (error) {
      console.error('Error signing up:', error.message);
      setLoading(false); // Ensure loading is false on error
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
  };

  const logout = async () => {
    setLoading(true);
    await supabase.auth.signOut();
  };

  return (
    <AuthContext.Provider value={{
      session, 
      user, 
      loading, 
      loginWithEmailPassword,
      signUpWithEmailPassword,
      logout, 
      isAdmin, 
      token 
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
