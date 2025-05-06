
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

type User = {
  id: string;
  name: string;
  email: string;
  avatar?: string;
  role: 'employee' | 'manager' | 'leadership';
  department?: string;
};

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for existing session
    const storedUser = localStorage.getItem('user');
    if (storedUser) {
      // Parse the stored user
      const parsedUser = JSON.parse(storedUser);
      
      // Force update the role to leadership to give admin privileges
      parsedUser.role = 'leadership';
      
      // Update localStorage with the modified user
      localStorage.setItem('user', JSON.stringify(parsedUser));
      
      // Set the user state with admin privileges
      setUser(parsedUser);
    }
    setLoading(false);
  }, []);

  const login = () => {
    // Mock Google login for demo
    setLoading(true);
    
    // Simulate API delay
    setTimeout(() => {
      const mockUser: User = {
        id: '1',
        name: 'Alex Johnson',
        email: 'alex@company.com',
        avatar: 'https://i.pravatar.cc/300',
        role: 'leadership', // Changed from 'manager' to 'leadership'
        department: 'Engineering',
      };
      
      setUser(mockUser);
      localStorage.setItem('user', JSON.stringify(mockUser));
      setLoading(false);
    }, 800);
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('user');
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
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
