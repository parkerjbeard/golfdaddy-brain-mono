import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { supabase } from '../lib/supabaseClient';

export const DevRoleSelector: React.FC = () => {
  const { userProfile, refreshProfile } = useAuth();
  const [isUpdating, setIsUpdating] = useState(false);
  const [message, setMessage] = useState('');

  const updateRole = async (role: string) => {
    setIsUpdating(true);
    setMessage('');
    
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error('No auth token found');
      }

      const response = await fetch(`/dev/sync-current-user/${role}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to update role: ${response.statusText}`);
      }

      const result = await response.json();
      setMessage(`Role updated to ${role}!`);
      
      // Refresh the user profile
      await refreshProfile();
      
      // Reload the page to ensure all components update
      setTimeout(() => window.location.reload(), 500);
    } catch (error) {
      setMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsUpdating(false);
    }
  };

  // Only show in development
  if (process.env.NODE_ENV !== 'development') {
    return null;
  }

  return (
    <div className="fixed bottom-4 right-4 bg-white p-4 rounded-lg shadow-lg border">
      <h3 className="text-sm font-semibold mb-2">Dev: Role Selector</h3>
      <p className="text-xs text-gray-600 mb-2">
        Current role: <strong>{userProfile?.role || 'Unknown'}</strong>
      </p>
      <div className="flex gap-2">
        <button
          onClick={() => updateRole('employee')}
          disabled={isUpdating}
          className="px-3 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
        >
          Employee
        </button>
        <button
          onClick={() => updateRole('manager')}
          disabled={isUpdating}
          className="px-3 py-1 text-xs bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50"
        >
          Manager
        </button>
        <button
          onClick={() => updateRole('admin')}
          disabled={isUpdating}
          className="px-3 py-1 text-xs bg-red-500 text-white rounded hover:bg-red-600 disabled:opacity-50"
        >
          Admin
        </button>
      </div>
      {message && (
        <p className="text-xs mt-2 text-center">
          {message}
        </p>
      )}
    </div>
  );
};