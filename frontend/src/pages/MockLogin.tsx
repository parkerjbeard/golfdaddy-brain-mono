import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';

export default function MockLogin() {
  const navigate = useNavigate();
  const { loading } = useAuth();

  useEffect(() => {
    // For development, bypass authentication
    if (!loading) {
      console.log("Mock login - bypassing authentication");
      // Navigate to dashboard directly
      navigate('/dashboard');
    }
  }, [loading, navigate]);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center">
        <h1 className="text-2xl font-bold mb-4">Development Mode</h1>
        <p className="text-gray-600">Bypassing authentication...</p>
      </div>
    </div>
  );
}