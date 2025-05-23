import React from 'react';
import { useAuth } from '@/hooks/useAuth';
import { UserRole } from '@/types/user';

interface RoleGuardProps {
  children: React.ReactNode;
  allowedRoles: UserRole[];
  fallback?: React.ReactNode;
  requireAll?: boolean; // If true, user must have ALL roles, if false, user needs ANY role
}

const RoleGuard: React.FC<RoleGuardProps> = ({
  children,
  allowedRoles,
  fallback = null,
  requireAll = false,
}) => {
  const { user } = useAuth();

  if (!user) {
    return <>{fallback}</>;
  }

  const userRole = user.role;
  
  // Check if user has required role(s)
  const hasAccess = requireAll
    ? allowedRoles.every(role => userRole === role) // Must match all roles (unlikely use case)
    : allowedRoles.includes(userRole); // Must match at least one role

  if (!hasAccess) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
};

// Convenience components for common role checks
export const AdminOnly: React.FC<{ children: React.ReactNode; fallback?: React.ReactNode }> = ({
  children,
  fallback = null,
}) => (
  <RoleGuard allowedRoles={[UserRole.ADMIN]} fallback={fallback}>
    {children}
  </RoleGuard>
);

export const ManagerOnly: React.FC<{ children: React.ReactNode; fallback?: React.ReactNode }> = ({
  children,
  fallback = null,
}) => (
  <RoleGuard allowedRoles={[UserRole.MANAGER, UserRole.ADMIN]} fallback={fallback}>
    {children}
  </RoleGuard>
);

export const DeveloperOnly: React.FC<{ children: React.ReactNode; fallback?: React.ReactNode }> = ({
  children,
  fallback = null,
}) => (
  <RoleGuard allowedRoles={[UserRole.DEVELOPER, UserRole.LEAD, UserRole.MANAGER, UserRole.ADMIN]} fallback={fallback}>
    {children}
  </RoleGuard>
);

export const LeadOnly: React.FC<{ children: React.ReactNode; fallback?: React.ReactNode }> = ({
  children,
  fallback = null,
}) => (
  <RoleGuard allowedRoles={[UserRole.LEAD, UserRole.MANAGER, UserRole.ADMIN]} fallback={fallback}>
    {children}
  </RoleGuard>
);

export const StaffOnly: React.FC<{ children: React.ReactNode; fallback?: React.ReactNode }> = ({
  children,
  fallback = null,
}) => (
  <RoleGuard allowedRoles={[UserRole.USER, UserRole.DEVELOPER, UserRole.LEAD, UserRole.MANAGER, UserRole.ADMIN]} fallback={fallback}>
    {children}
  </RoleGuard>
);

export default RoleGuard;