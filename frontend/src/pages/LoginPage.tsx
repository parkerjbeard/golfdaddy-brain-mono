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

const loginSchema = z.object({
  email: z.string().email({ message: 'Invalid email address' }),
  password: z.string().min(6, { message: 'Password must be at least 6 characters' }),
});

type LoginFormInputs = z.infer<typeof loginSchema>;

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { loginWithEmailPassword, signUpWithEmailPassword, user, loading: authLoading, session } = useAuth();
  const [isSignUp, setIsSignUp] = useState(false); // To toggle between Sign In and Sign Up
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<LoginFormInputs>({
    resolver: zodResolver(loginSchema),
  });

  const from = location.state?.from?.pathname || "/";

  useEffect(() => {
    // If user is already logged in (e.g. navigated here by mistake or session restored)
    // and session is active, redirect them.
    if (user && session) {
      navigate(from, { replace: true });
    }
  }, [user, session, navigate, from]);

  const onSubmit = async (data: LoginFormInputs) => {
    setFormError(null);
    setFormSuccess(null);
    try {
      if (isSignUp) {
        await signUpWithEmailPassword({ email: data.email, password: data.password });
        // Supabase might require email confirmation. The message is logged in useAuth.
        setFormSuccess('Sign up successful! Please check your email for a confirmation link if required.');
        toast.success('Sign up successful!', { description: 'Please check your email for a confirmation link if required.'});
        // Optionally reset form or redirect to a specific page post-signup email sent
        // For now, user will see success message. onAuthStateChange will handle eventual login.
      } else {
        await loginWithEmailPassword({ email: data.email, password: data.password });
        // Successful login is handled by onAuthStateChange in useAuth, which will update user state
        // and trigger the useEffect above to navigate.
        toast.success('Login successful!');
        // No need to navigate here, useEffect will handle it when user state changes
      }
      // reset(); // Reset form on success if desired, or let user see their input
    } catch (error: any) {
      console.error("Login/Signup Page Error:", error);
      setFormError(error.message || (isSignUp ? 'Sign up failed' : 'Login failed'));
      toast.error(isSignUp ? 'Sign up failed' : 'Login failed', { description: error.message });
    }
  };

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
              {authLoading ? 'Processing...' : (isSignUp ? 'Sign Up' : 'Sign In')}
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