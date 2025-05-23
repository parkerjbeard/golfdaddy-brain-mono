/**
 * New consolidated authentication page
 * Replaces LoginPage.tsx, BasicLoginPage.tsx, and Login.tsx
 */

import React from 'react';
import AuthenticatedLogin from '@/components/auth/AuthenticatedLogin';

const AuthPage: React.FC = () => {
  return <AuthenticatedLogin variant="branded" showSignup={true} />;
};

export default AuthPage;