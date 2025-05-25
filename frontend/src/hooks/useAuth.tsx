import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { Session, SignUpWithPasswordCredentials } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabaseClient";
import { UserRole, UserResponse } from "@/types/user";

/**
 * Authentication context shape – kept compatible with the rest of the code-base
 */
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

/**
 * Translate a Supabase session → minimal UserResponse expected by the UI.
 */
function mapSupabaseUser(session: Session): UserResponse {
  const meta = session.user.user_metadata as Record<string, any> | undefined;
  // Prefer explicit role in metadata, fall back to generic USER
  const role: UserRole = (meta?.role as UserRole) ?? UserRole.USER;
  return {
    id: session.user.id,
    email: session.user.email ?? "",
    name: meta?.name ?? session.user.email?.split("@")[0] ?? "User",
    role,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<UserResponse | null>(null);
  const [loading, setLoading] = useState(true);

  // ---- helpers ----
  const handleSessionChange = (sess: Session | null) => {
    setSession(sess);
    if (sess) {
      const mapped = mapSupabaseUser(sess);
      setUser(mapped);
    } else {
      setUser(null);
    }
  };

  // ---- initial load & listener ----
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      handleSessionChange(session);
      setLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      handleSessionChange(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  // ---- auth actions ----
  const loginWithEmailPassword = async (credentials: SignUpWithPasswordCredentials) => {
    const { error } = await supabase.auth.signInWithPassword(credentials);
    if (error) throw error;
  };

  const signUpWithEmailPassword = async (credentials: SignUpWithPasswordCredentials) => {
    const { error } = await supabase.auth.signUp(credentials);
    if (error) throw error;
  };

  const logout = async () => {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
  };

  const contextValue: AuthContextType = {
    session,
    user,
    loading,
    isAdmin: user?.role === UserRole.ADMIN,
    loginWithEmailPassword,
    signUpWithEmailPassword,
    logout,
    token: session?.access_token ?? null,
  };

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>;
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
};
