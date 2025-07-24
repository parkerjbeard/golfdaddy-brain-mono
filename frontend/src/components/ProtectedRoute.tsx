import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRoles?: string[];
  redirectTo?: string;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ 
  children, 
  requiredRoles, 
  redirectTo = '/login' 
}) => {
  const { session, userProfile, loading } = useAuth();

  // Still loading
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  // Not authenticated
  if (!session) {
    return <Navigate to={redirectTo} replace />;
  }

  // No role requirements - just need to be logged in
  if (!requiredRoles || requiredRoles.length === 0) {
    return <>{children}</>;
  }

  // Check role requirements

  if (userProfile && requiredRoles.includes(userProfile.role)) {
    return <>{children}</>;
  }

  // For admin roles, also allow admin access
  if (userProfile?.role === 'admin') {
    return <>{children}</>;
  }

  // For manager roles, also allow manager access
  if (requiredRoles.includes('manager') && userProfile?.role === 'manager') {
    return <>{children}</>;
  }

  // Not authorized - redirect to dashboard
  return <Navigate to="/dashboard" replace />;
};