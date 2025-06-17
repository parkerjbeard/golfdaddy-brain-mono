import React, { useState, useEffect } from 'react';
import { useApi } from '@/hooks/useApi';
import { User } from '@/types';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/use-toast';
import { Loader2, Save, Search, UserCheck, Github, Hash } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface UserWithMapping extends User {
  github_username?: string | null;
  slack_id?: string | null;
}

interface UserMappingUpdate {
  github_username?: string | null;
  slack_id?: string | null;
}

export const UserMappingManager: React.FC = () => {
  const { client, loading: apiLoading, error: apiError } = useApi();
  const [users, setUsers] = useState<UserWithMapping[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [editingUser, setEditingUser] = useState<string | null>(null);
  const [tempValues, setTempValues] = useState<{ [key: string]: UserMappingUpdate }>({});
  const [saving, setSaving] = useState<{ [key: string]: boolean }>({});
  const [confirmDialog, setConfirmDialog] = useState<{ userId: string; field: 'github' | 'slack' } | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    if (client) {
      fetchUsers();
    }
  }, [client]);

  const fetchUsers = async () => {
    if (!client) return;
    
    try {
      setLoading(true);
      // Fetch all users with pagination
      const response = await client.get('/api/v1/users', {
        params: { page: 1, size: 100 } // Adjust size as needed
      });
      
      if (response.data?.users) {
        setUsers(response.data.users);
      }
    } catch (error) {
      console.error('Failed to fetch users:', error);
      toast({
        title: 'Error',
        description: 'Failed to load users. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (userId: string) => {
    const user = users.find(u => u.id === userId);
    if (user) {
      setEditingUser(userId);
      setTempValues({
        ...tempValues,
        [userId]: {
          github_username: user.github_username || '',
          slack_id: user.slack_id || '',
        }
      });
    }
  };

  const handleCancel = (userId: string) => {
    setEditingUser(null);
    const newTempValues = { ...tempValues };
    delete newTempValues[userId];
    setTempValues(newTempValues);
  };

  const handleSave = async (userId: string) => {
    if (!client || !tempValues[userId]) return;

    // Check if clearing a value
    const updates = tempValues[userId];
    const user = users.find(u => u.id === userId);
    
    if (user?.github_username && !updates.github_username) {
      setConfirmDialog({ userId, field: 'github' });
      return;
    }
    
    if (user?.slack_id && !updates.slack_id) {
      setConfirmDialog({ userId, field: 'slack' });
      return;
    }

    await performSave(userId);
  };

  const performSave = async (userId: string) => {
    if (!client || !tempValues[userId]) return;

    setSaving({ ...saving, [userId]: true });
    
    try {
      const updates = tempValues[userId];
      const payload: any = {};
      
      // Only include fields that have changed
      if (updates.github_username !== undefined) {
        payload.github_username = updates.github_username || null;
      }
      if (updates.slack_id !== undefined) {
        payload.slack_id = updates.slack_id || null;
      }

      const response = await client.put(`/api/v1/users/${userId}`, payload);
      
      if (response.data) {
        // Update local state
        setUsers(users.map(u => 
          u.id === userId ? { ...u, ...response.data } : u
        ));
        
        toast({
          title: 'Success',
          description: 'User mapping updated successfully.',
        });
        
        setEditingUser(null);
        const newTempValues = { ...tempValues };
        delete newTempValues[userId];
        setTempValues(newTempValues);
      }
    } catch (error) {
      console.error('Failed to update user:', error);
      toast({
        title: 'Error',
        description: 'Failed to update user mapping. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setSaving({ ...saving, [userId]: false });
    }
  };

  const handleInputChange = (userId: string, field: keyof UserMappingUpdate, value: string) => {
    setTempValues({
      ...tempValues,
      [userId]: {
        ...tempValues[userId],
        [field]: value,
      }
    });
  };

  const filteredUsers = users.filter(user => {
    const searchLower = searchTerm.toLowerCase();
    return (
      user.name?.toLowerCase().includes(searchLower) ||
      user.email?.toLowerCase().includes(searchLower) ||
      user.github_username?.toLowerCase().includes(searchLower) ||
      user.slack_id?.toLowerCase().includes(searchLower)
    );
  });

  if (apiLoading || loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  if (apiError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>
          Failed to initialize API client. Please check your authentication.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserCheck className="h-5 w-5" />
            User Mapping Management
          </CardTitle>
          <CardDescription>
            Map GitHub usernames and Slack IDs to users for integration features
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-4 relative">
            <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search by name, email, GitHub username, or Slack ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9"
            />
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>
                    <div className="flex items-center gap-1">
                      <Github className="h-4 w-4" />
                      GitHub Username
                    </div>
                  </TableHead>
                  <TableHead>
                    <div className="flex items-center gap-1">
                      <Hash className="h-4 w-4" />
                      Slack ID
                    </div>
                  </TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredUsers.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground">
                      No users found
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredUsers.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell>
                        <div>
                          <div className="font-medium">{user.name || 'Unnamed User'}</div>
                          <div className="text-sm text-muted-foreground">{user.email}</div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{user.role}</Badge>
                      </TableCell>
                      <TableCell>
                        {editingUser === user.id ? (
                          <Input
                            value={tempValues[user.id]?.github_username ?? ''}
                            onChange={(e) => handleInputChange(user.id, 'github_username', e.target.value)}
                            placeholder="Enter GitHub username"
                            className="w-full max-w-[200px]"
                          />
                        ) : (
                          <span className={user.github_username ? '' : 'text-muted-foreground'}>
                            {user.github_username || 'Not set'}
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        {editingUser === user.id ? (
                          <Input
                            value={tempValues[user.id]?.slack_id ?? ''}
                            onChange={(e) => handleInputChange(user.id, 'slack_id', e.target.value)}
                            placeholder="Enter Slack ID (e.g., U1234567)"
                            className="w-full max-w-[200px]"
                          />
                        ) : (
                          <span className={user.slack_id ? '' : 'text-muted-foreground'}>
                            {user.slack_id || 'Not set'}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {editingUser === user.id ? (
                          <div className="flex items-center justify-end gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleCancel(user.id)}
                              disabled={saving[user.id]}
                            >
                              Cancel
                            </Button>
                            <Button
                              size="sm"
                              onClick={() => handleSave(user.id)}
                              disabled={saving[user.id]}
                            >
                              {saving[user.id] ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Save className="h-4 w-4" />
                              )}
                              Save
                            </Button>
                          </div>
                        ) : (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleEdit(user.id)}
                          >
                            Edit
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          <div className="mt-4 text-sm text-muted-foreground">
            <p>
              <strong>GitHub Username:</strong> The user's GitHub username for commit analysis and integration
            </p>
            <p>
              <strong>Slack ID:</strong> The user's Slack member ID (e.g., U1234567) for direct messages and notifications
            </p>
            <p className="mt-2">
              To find a Slack ID, open Slack → Click on the user's profile → More → Copy member ID
            </p>
          </div>
        </CardContent>
      </Card>

      <Dialog open={!!confirmDialog} onOpenChange={() => setConfirmDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Clear {confirmDialog?.field === 'github' ? 'GitHub Username' : 'Slack ID'}?</DialogTitle>
            <DialogDescription>
              Are you sure you want to clear the {confirmDialog?.field === 'github' ? 'GitHub username' : 'Slack ID'} for this user? 
              This may affect integrations and notifications.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDialog(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (confirmDialog) {
                  performSave(confirmDialog.userId);
                  setConfirmDialog(null);
                }
              }}
            >
              Clear
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};