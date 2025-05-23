import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';

// Define the schema for form validation
const loginSchema = z.object({
  email: z.string().email({ message: 'Invalid email address' }),
  password: z.string().min(6, { message: 'Password must be at least 6 characters' }),
});

type LoginFormInputs = z.infer<typeof loginSchema>;

interface AuthenticatedLoginProps {
  redirectTo?: string;
  showSignup?: boolean;
  variant?: 'default' | 'branded';
}

const AuthenticatedLogin: React.FC<AuthenticatedLoginProps> = ({ 
  redirectTo,
  showSignup = true,
  variant = 'default'
}) => {
  const navigate = useNavigate();
  const location = useLocation();
  
  // State must be declared before any early returns
  const [isSignUp, setIsSignUp] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<LoginFormInputs>({
    resolver: zodResolver(loginSchema),
  });

  // Authentication hook with error handling - must be called unconditionally
  let authHook;
  try {
    authHook = useAuth();
  } catch (error) {
    console.error("Error loading useAuth hook:", error);
    // Set error state instead of returning early
    if (!authError) {
      setAuthError(String(error));
    }
  }

  const from = redirectTo || location.state?.from?.pathname || "/";

  // Handle authentication redirect
  useEffect(() => {
    if (authHook?.user && authHook?.session) {
      console.log("User authenticated, redirecting to:", from);
      navigate(from, { replace: true });
    }
  }, [authHook?.user, authHook?.session, navigate, from]);

  // Show auth error if hook failed to load
  if (authError) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100 dark:bg-gray-900 px-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold text-red-600">Authentication Error</CardTitle>
            <CardDescription>
              There was a problem loading the authentication system.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-red-500">Please try refreshing the page or contact support.</p>
            <p className="text-sm mt-2 text-gray-500">{authError}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!authHook) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }
  
  const { 
    loginWithEmailPassword, 
    signUpWithEmailPassword, 
    user, 
    loading: authLoading, 
    session 
  } = authHook;

  const onSubmit = async (data: LoginFormInputs) => {
    setFormError(null);
    setFormSuccess(null);
    setIsSubmitting(true);
    
    try {
      if (isSignUp) {
        await signUpWithEmailPassword({ email: data.email, password: data.password });
        setFormSuccess('Sign up successful! Please check your email for a confirmation link if required.');
        toast.success('Sign up successful!');
      } else {
        await loginWithEmailPassword({ email: data.email, password: data.password });
        toast.success('Login successful!');
      }
    } catch (error: unknown) {
      console.error("Login/Signup error:", error);
      const errorMessage = error instanceof Error ? error.message : (isSignUp ? 'Sign up failed' : 'Login failed');
      setFormError(errorMessage);
      toast.error(isSignUp ? 'Sign up failed' : 'Login failed', { 
        description: error instanceof Error ? error.message : 'An error occurred' 
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Loading state
  if (authLoading && !formError) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100 dark:bg-gray-900 px-4">
        <Card className="w-full max-w-md p-8">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
            <h2 className="text-2xl font-bold mb-4">Loading...</h2>
            <p>Authenticating, please wait.</p>
          </div>
        </Card>
      </div>
    );
  }

  const renderBrandedHeader = () => (
    <div className="text-center mb-8">
      <div className="flex justify-center">
        <svg 
          viewBox="0 0 24 24" 
          className="h-12 w-12 text-primary" 
          fill="none" 
          stroke="currentColor" 
          strokeWidth="2"
          strokeLinecap="round" 
          strokeLinejoin="round"
        >
          <rect width="20" height="14" x="2" y="5" rx="2" />
          <path d="M2 10h20" />
        </svg>
      </div>
      <h1 className="mt-4 text-2xl font-semibold tracking-tight">GolfDaddy Brain</h1>
      <p className="mt-1 text-muted-foreground">AI-powered development insights</p>
    </div>
  );

  return (
    <div className={`flex items-center justify-center min-h-screen px-4 ${
      variant === 'branded' 
        ? 'bg-gradient-to-tr from-background to-secondary/40' 
        : 'bg-gray-100 dark:bg-gray-900'
    }`}>
      <div className="w-full max-w-md animate-scale-in">
        {variant === 'branded' && renderBrandedHeader()}
        
        <Card className={variant === 'branded' ? 'p-8' : 'w-full max-w-md'}>
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold">
              {isSignUp ? 'Create an Account' : 'Welcome Back'}
            </CardTitle>
            <CardDescription>
              {isSignUp 
                ? 'Enter your email and password to sign up.' 
                : 'Enter your credentials to access your account.'
              }
            </CardDescription>
          </CardHeader>
          
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input 
                  id="email" 
                  type="email" 
                  placeholder="m@example.com" 
                  {...register('email')} 
                  disabled={isSubmitting || authLoading}
                />
                {errors.email && <p className="text-xs text-red-500">{errors.email.message}</p>}
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input 
                  id="password" 
                  type="password" 
                  {...register('password')} 
                  disabled={isSubmitting || authLoading}
                />
                {errors.password && <p className="text-xs text-red-500">{errors.password.message}</p>}
              </div>
              
              {formError && (
                <div className="p-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-md">
                  {formError}
                </div>
              )}
              
              {formSuccess && (
                <div className="p-3 text-sm text-green-600 bg-green-50 border border-green-200 rounded-md">
                  {formSuccess}
                </div>
              )}
              
              <Button 
                type="submit" 
                className="w-full" 
                disabled={isSubmitting || authLoading}
              >
                {isSubmitting ? 'Processing...' : (isSignUp ? 'Sign Up' : 'Sign In')}
              </Button>
            </form>
          </CardContent>
          
          {showSignup && (
            <CardFooter className="flex flex-col items-center space-y-2">
              <Button 
                variant="link" 
                onClick={() => { 
                  setIsSignUp(!isSignUp); 
                  reset(); 
                  setFormError(null); 
                  setFormSuccess(null); 
                }} 
                disabled={isSubmitting || authLoading}
              >
                {isSignUp ? 'Already have an account? Sign In' : "Don't have an account? Sign Up"}
              </Button>
              
              {variant === 'branded' && (
                <>
                  <Separator className="my-4" />
                  <div className="text-center text-xs text-muted-foreground">
                    By signing in, you agree to our{' '}
                    <a href="#" className="underline hover:text-foreground">Terms of Service</a>
                    {' '}and{' '}
                    <a href="#" className="underline hover:text-foreground">Privacy Policy</a>.
                  </div>
                </>
              )}
            </CardFooter>
          )}
        </Card>
      </div>
    </div>
  );
};

export default AuthenticatedLogin;