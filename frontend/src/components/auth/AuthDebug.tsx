import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function AuthDebug() {
  const auth = useAuth();
  
  return (
    <Card className="fixed bottom-4 right-4 w-96 z-50">
      <CardHeader>
        <CardTitle className="text-sm">Auth Debug</CardTitle>
      </CardHeader>
      <CardContent className="text-xs space-y-1">
        <div>Loading: {String(auth.loading)}</div>
        <div>User: {auth.user ? auth.user.email : 'null'}</div>
        <div>Session: {auth.session ? 'exists' : 'null'}</div>
        <div>Token: {auth.token ? 'exists' : 'null'}</div>
        <div>Is Admin: {String(auth.isAdmin)}</div>
        <button 
          className="mt-2 px-2 py-1 bg-blue-500 text-white rounded"
          onClick={() => window.location.reload()}
        >
          Reload
        </button>
      </CardContent>
    </Card>
  );
}