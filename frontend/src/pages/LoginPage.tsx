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
import { toast } from 'sonner';

// Define the schema for form validation
const loginSchema = z.object({
  email: z.string().email({ message: 'Invalid email address' }),
  password: z.string().min(6, { message: 'Password must be at least 6 characters' }),
});

type LoginFormInputs = z.infer<typeof loginSchema>;

const LoginPage: React.FC = () => {
  console.log("Rendering LoginPage");
  
  const navigate = useNavigate();
  const location = useLocation();
  
  // Try/catch around useAuth to catch any potential rendering errors
  let authHook;
  try {
    authHook = useAuth();
    console.log("useAuth hook loaded successfully");
  } catch (error) {
    console.error("Error loading useAuth hook:", error);
    // Render fallback UI instead of crashing
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100 dark:bg-gray-900 px-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold">Authentication Error</CardTitle>
            <CardDescription>
              There was a problem loading the authentication system.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-red-500">Please try refreshing the page or contact support.</p>
            <p className="text-sm mt-2">{String(error)}</p>
          </CardContent>
        </Card>
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
  
  const [isSignUp, setIsSignUp] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<LoginFormInputs>({
    resolver: zodResolver(loginSchema),
  });

  const from = location.state?.from?.pathname || "/";

  useEffect(() => {
    console.log("LoginPage useEffect - User:", user ? "Exists" : "None", "Session:", session ? "Exists" : "None");
    
    // Only redirect if both user and session exist
    // This should prevent premature redirects
    if (user && session) {
      console.log("User authenticated, redirecting to:", from);
      navigate(from, { replace: true });
    }
  }, [user, session, navigate, from]);

  const onSubmit = async (data: LoginFormInputs) => {
    console.log("Form submitted with email:", data.email);
    setFormError(null);
    setFormSuccess(null);
    setIsSubmitting(true);
    
    try {
      if (isSignUp) {
        console.log("Attempting signup");
        await signUpWithEmailPassword({ email: data.email, password: data.password });
        setFormSuccess('Sign up successful! Please check your email for a confirmation link if required.');
        toast.success('Sign up successful!');
      } else {
        console.log("Attempting login");
        await loginWithEmailPassword({ email: data.email, password: data.password });
        toast.success('Login successful!');
      }
    } catch (error: any) {
      console.error("Login/Signup error:", error);
      setFormError(error.message || (isSignUp ? 'Sign up failed' : 'Login failed'));
      toast.error(isSignUp ? 'Sign up failed' : 'Login failed', { description: error.message });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Display loading state when the component is initially rendering
  if (authLoading && !formError) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100 dark:bg-gray-900 px-4">
        <Card className="w-full max-w-md p-8">
          <div className="text-center">
            <h2 className="text-2xl font-bold mb-4">Loading...</h2>
            <p>Authenticating, please wait.</p>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100 dark:bg-gray-900 px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-bold">{isSignUp ? 'Create an Account' : 'Welcome Back'}</CardTitle>
          <CardDescription>
            {isSignUp ? 'Enter your email and password to sign up.' : 'Enter your credentials to access your account.'}
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
            
            {formError && <p className="text-sm text-red-500 text-center">{formError}</p>}
            {formSuccess && <p className="text-sm text-green-500 text-center">{formSuccess}</p>}
            
            <Button type="submit" className="w-full" disabled={isSubmitting || authLoading}>
              {isSubmitting ? 'Processing...' : (isSignUp ? 'Sign Up' : 'Sign In')}
            </Button>
          </form>
        </CardContent>
        <CardFooter className="flex flex-col items-center space-y-2">
          <Button variant="link" onClick={() => { setIsSignUp(!isSignUp); reset(); setFormError(null); setFormSuccess(null); }} disabled={isSubmitting || authLoading}>
            {isSignUp ? 'Already have an account? Sign In' : "Don't have an account? Sign Up"}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
};

export default LoginPage; 