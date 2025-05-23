import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { UserRole } from '@/types/user';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRoles?: UserRole[];
  requireAuthentication?: boolean;
  fallbackPath?: string;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredRoles = [],
  requireAuthentication = true,
  fallbackPath = '/login',
}) => {
  const { user, loading, session } = useAuth();
  const location = useLocation();

  // Show loading state while authentication is being checked
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Card className="w-full max-w-md p-8">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
            <h2 className="text-2xl font-bold mb-4">Loading...</h2>
            <p>Checking authentication...</p>
          </div>
        </Card>
      </div>
    );
  }

  // Check if authentication is required and user is not authenticated
  if (requireAuthentication && (!user || !session)) {
    // Redirect to login with the attempted location
    return <Navigate to={fallbackPath} state={{ from: location }} replace />;
  }

  // Check if specific roles are required
  if (requiredRoles.length > 0 && user) {
    const hasRequiredRole = requiredRoles.includes(user.role);
    
    if (!hasRequiredRole) {
      // User is authenticated but doesn't have required role
      return (
        <div className="flex items-center justify-center min-h-screen bg-gray-100 dark:bg-gray-900 px-4">
          <Card className="w-full max-w-md">
            <CardHeader className="text-center">
              <CardTitle className="text-2xl font-bold text-red-600">Access Denied</CardTitle>
              <CardDescription>
                You don't have permission to access this page.
              </CardDescription>
            </CardHeader>
            <CardContent className="text-center">
              <p className="text-gray-600 mb-4">
                This page requires one of the following roles: {requiredRoles.join(', ')}
              </p>
              <p className="text-sm text-gray-500">
                Your current role: {user.role}
              </p>
              <p className="text-sm text-gray-500 mt-2">
                Please contact your administrator if you believe this is an error.
              </p>
            </CardContent>
          </Card>
        </div>
      );
    }
  }

  // User is authenticated and has required permissions
  return <>{children}</>;
};

export default ProtectedRoute;