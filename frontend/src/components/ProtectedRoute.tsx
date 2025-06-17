import React from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

interface ProtectedRouteProps {
  children: React.ReactNode
  allowedRoles?: string[]
  redirectTo?: string
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ 
  children, 
  allowedRoles,
  redirectTo = '/login' 
}) => {
  const { session, loading } = useAuth()
  
  console.log('ProtectedRoute render - loading:', loading, 'session:', !!session, 'path:', window.location.pathname);

  if (loading) {
    console.log('ProtectedRoute showing loading state');
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div>Loading... (ProtectedRoute)</div>
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
      </div>
    )
  }

  if (!session) {
    console.log('ProtectedRoute - No session, redirecting to:', redirectTo);
    return <Navigate to={redirectTo} replace />
  }
  
  console.log('ProtectedRoute - User authenticated, rendering children');

  // Role-based access control
  if (allowedRoles && allowedRoles.length > 0) {
    const userRole = session.user?.user_metadata?.role || session.user?.app_metadata?.role
    console.log('ProtectedRoute - checking roles:', {
      allowedRoles,
      userRole,
      user_metadata: session.user?.user_metadata,
      app_metadata: session.user?.app_metadata
    });
    // TODO: Re-enable role check once roles are properly set in Supabase
    const bypassRoleCheck = true; // Temporary bypass
    if (!bypassRoleCheck && (!userRole || !allowedRoles.includes(userRole))) {
      console.log('ProtectedRoute - Access denied, redirecting to dashboard');
      return <Navigate to="/dashboard" replace />
    }
  }

  return <>{children}</>
}