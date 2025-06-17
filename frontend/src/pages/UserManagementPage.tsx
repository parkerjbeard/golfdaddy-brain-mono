import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';

import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogClose, // DialogTrigger is not used directly here, Dialog is controlled by state
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';

import { UserResponse, UserRole, UserUpdateByAdminPayload, UserListResponse } from '@/types/user';
import { useAuth } from '@/contexts/AuthContext'; // Import useAuth

// Placeholder for your actual auth token retrieval - THIS WILL BE REMOVED
/*
const getAuthToken = (): string | null => {
  return localStorage.getItem('authToken');
};
*/

const API_BASE_URL = '/api';

// API fetching functions
async function fetchUsers(token: string | null, page: number = 1, size: number = 20): Promise<UserListResponse> { // Added token argument
  // const token = getAuthToken(); // Old way
  if (!token) throw new Error('Authentication token not found');
  const response = await fetch(`${API_BASE_URL}/users?page=${page}&size=${size}`, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Network response was not ok' }));
    throw new Error(errorData.detail || 'Failed to fetch users');
  }
  return response.json();
}

async function updateUser(token: string | null, userId: string, data: UserUpdateByAdminPayload): Promise<UserResponse> { // Added token argument
  // const token = getAuthToken(); // Old way
  if (!token) throw new Error('Authentication token not found');
  const response = await fetch(`${API_BASE_URL}/users/${userId}`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Network response was not ok' }));
    throw new Error(errorData.detail || 'Failed to update user');
  }
  return response.json();
}

const userUpdateSchema = z.object({
  name: z.string().max(255, "Name too long").optional().nullable(),
  slack_id: z.string().max(50, "Slack ID too long").optional().nullable(),
  github_username: z.string().max(100, "GitHub username too long").optional().nullable(),
  role: z.nativeEnum(UserRole).optional().nullable(),
  team: z.string().max(100, "Team name too long").optional().nullable(),
  team_id: z.string().uuid("Invalid UUID format for Team ID").optional().nullable(),
  reports_to_id: z.string().uuid("Invalid UUID format for Reports To ID").optional().nullable(),
  is_active: z.boolean().optional().nullable(),
  // avatar_url, metadata, personal_mastery, preferences are not directly in this form for now
});

type UserUpdateFormData = z.infer<typeof userUpdateSchema>;

const UserManagementPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { session, loading: authLoading } = useAuth(); // Use useAuth hook
  const token = session?.access_token || null;
  const user = session?.user || null;
  const userRole = user?.user_metadata?.role || user?.app_metadata?.role;
  const isAdmin = userRole === UserRole.ADMIN || userRole === 'admin';
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserResponse | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const usersPerPage = 20;

  const { data: usersData, isLoading, error, refetch } = useQuery<UserListResponse, Error>({
    queryKey: ['users', currentPage, usersPerPage, token], // Add token to queryKey
    queryFn: () => fetchUsers(token, currentPage, usersPerPage), // Pass token to fetchUsers
    enabled: !!token && isAdmin, // Only run query if token exists and user is admin
    placeholderData: (previousData) => previousData, // Keep previous data while loading new data
  });

  const mutation = useMutation<UserResponse, Error, { userId: string; data: UserUpdateByAdminPayload }>({
    mutationFn: ({ userId, data }) => updateUser(token, userId, data), // Pass token to updateUser
    onSuccess: (updatedUser) => {
      toast.success(`User ${updatedUser.name || updatedUser.id} updated successfully!`);
      queryClient.invalidateQueries({ queryKey: ['users', currentPage, usersPerPage, token] }); // Invalidate specific page
      queryClient.invalidateQueries({ queryKey: ['users'] }); // Invalidate general users query if needed elsewhere
      setIsEditDialogOpen(false);
      setSelectedUser(null);
    },
    onError: (error) => {
      toast.error(`Failed to update user: ${error.message}`);
    },
  });

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    control, // For Shadcn Select with react-hook-form
    formState: { errors },
  } = useForm<UserUpdateFormData>({
    resolver: zodResolver(userUpdateSchema),
    defaultValues: { // Initialize with nulls or empty strings for better control
        name: null,
        slack_id: null,
        github_username: null,
        role: null,
        team: null,
        team_id: null,
        reports_to_id: null,
        is_active: null,
    }
  });

  useEffect(() => {
    // Re-fetch if token changes or if admin status is confirmed
    if (token && isAdmin) {
        refetch();
    }
  }, [token, isAdmin, refetch]);

  useEffect(() => {
    if (selectedUser) {
      reset({
        name: selectedUser.name || null,
        slack_id: selectedUser.slack_id || null,
        github_username: selectedUser.github_username || null,
        role: selectedUser.role || null,
        team: selectedUser.team || null,
        team_id: selectedUser.team_id || null,
        reports_to_id: selectedUser.reports_to_id || null,
        is_active: selectedUser.is_active === undefined ? null : selectedUser.is_active,
      });
    } else {
      reset({
        name: null,
        slack_id: null,
        github_username: null,
        role: null,
        team: null,
        team_id: null,
        reports_to_id: null,
        is_active: null,
      });
    }
  }, [selectedUser, reset]);

  const handleEditUser = (user: UserResponse) => {
    setSelectedUser(user);
    setIsEditDialogOpen(true);
  };

  const onSubmit = (data: UserUpdateFormData) => {
    if (selectedUser && token && isAdmin) { // Ensure token and admin status before submitting
      const payload: UserUpdateByAdminPayload = {};
      // Only include fields that have changed or are not null/empty
      if (data.name !== undefined && data.name !== null) payload.name = data.name.trim() === '' ? null : data.name.trim();
      if (data.slack_id !== undefined && data.slack_id !== null) payload.slack_id = data.slack_id.trim() === '' ? null : data.slack_id.trim();
      if (data.github_username !== undefined && data.github_username !== null) payload.github_username = data.github_username.trim() === '' ? null : data.github_username.trim();
      if (data.role !== undefined && data.role !== null) payload.role = data.role;
      if (data.team !== undefined && data.team !== null) payload.team = data.team.trim() === '' ? null : data.team.trim();
      if (data.team_id !== undefined && data.team_id !== null) payload.team_id = data.team_id.trim() === '' ? null : data.team_id.trim();
      if (data.reports_to_id !== undefined && data.reports_to_id !== null) payload.reports_to_id = data.reports_to_id.trim() === '' ? null : data.reports_to_id.trim();
      if (data.is_active !== undefined && data.is_active !== null) payload.is_active = data.is_active;

      // Check if there are actual changes compared to the selected user
      let hasChanges = false;
      if (payload.name !== (selectedUser.name || null)) hasChanges = true;
      if (payload.slack_id !== (selectedUser.slack_id || null)) hasChanges = true;
      if (payload.github_username !== (selectedUser.github_username || null)) hasChanges = true;
      if (payload.role !== (selectedUser.role || null)) hasChanges = true;
      if (payload.team !== (selectedUser.team || null)) hasChanges = true;
      if (payload.team_id !== (selectedUser.team_id || null)) hasChanges = true;
      if (payload.reports_to_id !== (selectedUser.reports_to_id || null)) hasChanges = true;
      if (payload.is_active !== (selectedUser.is_active === undefined ? null : selectedUser.is_active)) hasChanges = true;

      if (!hasChanges && Object.keys(payload).length > 0) {
         // This case means fields were filled but they are same as original
         // or some fields became empty and are treated as null.
         // To avoid unnecessary API calls if nothing effectively changed OR if only nullable fields were blanked out
         // we can compare with original values or simply check if any *non-null* value is being submitted where previously it was null
         // For simplicity, we'll allow submitting if any field is actively set, even if to its original value or null.
         // The backend payload.model_dump(exclude_unset=True) should handle not updating unchanged fields.
      }
      
      if (Object.keys(payload).length === 0 && !hasChanges) {
        toast.info("No changes to submit.");
        setIsEditDialogOpen(false);
        return;
      }

      mutation.mutate({ userId: selectedUser.id, data: payload });
    }
  };

  const totalPages = usersData ? Math.ceil(usersData.total / usersPerPage) : 0;

  if (authLoading) return <div className="container mx-auto py-10 px-4 md:px-6 text-center">Authenticating...</div>;

  if (!user && !authLoading) {
    // This case can be handled by a redirect in a ProtectedRoute component or here
    return <div className="container mx-auto py-10 px-4 md:px-6 text-center">Please log in to view this page.</div>;
  }

  if (!isAdmin && !authLoading) {
    return <div className="container mx-auto py-10 px-4 md:px-6 text-center">You do not have permission to view this page.</div>;
  }

  if (isLoading) return <div className="container mx-auto py-10 px-4 md:px-6 text-center">Loading users...</div>;
  if (error) return <div className="container mx-auto py-10 px-4 md:px-6 text-center">Error fetching users: {error.message}</div>;

  return (
    <div className="container mx-auto py-10 px-4 md:px-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">User Management</h1>
        {/* Add New User button can be added here if functionality is desired */}
      </div>

      {!isLoading && !error && usersData && (
        <>
          <div className="border rounded-md">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead className="hidden md:table-cell">Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead className="hidden sm:table-cell">Slack ID</TableHead>
                  <TableHead className="hidden sm:table-cell">GitHub</TableHead>
                  <TableHead className="hidden md:table-cell">Team</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {usersData.users.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center">No users found.</TableCell>
                  </TableRow>
                )}
                {usersData.users.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell className="font-medium">{user.name || 'N/A'}</TableCell>
                    <TableCell className="hidden md:table-cell">{user.email || 'N/A'}</TableCell>
                    <TableCell>{user.role}</TableCell>
                    <TableCell className="hidden sm:table-cell">{user.slack_id || 'N/A'}</TableCell>
                    <TableCell className="hidden sm:table-cell">{user.github_username || 'N/A'}</TableCell>
                    <TableCell className="hidden md:table-cell">{user.team || 'N/A'}</TableCell>
                    <TableCell>
                      <Button variant="outline" size="sm" onClick={() => handleEditUser(user)}>
                        Edit
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-end space-x-2 py-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                disabled={currentPage === 1}
              >
                Previous
              </Button>
              <span className="text-sm">
                Page {currentPage} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                disabled={currentPage === totalPages}
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}

      {/* Edit User Dialog */}
      {selectedUser && (
        <Dialog open={isEditDialogOpen} onOpenChange={(isOpen) => {
          if (!isOpen) {
            setSelectedUser(null); // Clear selected user when dialog closes
            reset(); // Reset form
          }
          setIsEditDialogOpen(isOpen);
        }}>
          <DialogContent className="sm:max-w-[480px]">
            <DialogHeader>
              <DialogTitle>Edit User: {selectedUser.name || selectedUser.email}</DialogTitle>
              <DialogDescription>
                Update user details. Click save when you're done.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit(onSubmit)} className="grid gap-6 py-4">
              <div className="grid gap-2">
                <Label htmlFor="name">Name</Label>
                <Input id="name" {...register('name')} />
                {errors.name && <p className="text-sm text-red-500">{errors.name.message}</p>}
              </div>
              
              <div className="grid gap-2">
                <Label htmlFor="slack_id">Slack ID</Label>
                <Input id="slack_id" {...register('slack_id')} />
                {errors.slack_id && <p className="text-sm text-red-500">{errors.slack_id.message}</p>}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="github_username">GitHub Username</Label>
                <Input id="github_username" {...register('github_username')} />
                {errors.github_username && <p className="text-sm text-red-500">{errors.github_username.message}</p>}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="team">Team</Label>
                <Input id="team" {...register('team')} />
                {errors.team && <p className="text-sm text-red-500">{errors.team.message}</p>}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="team_id">Team ID (UUID)</Label>
                <Input id="team_id" {...register('team_id')} placeholder="Optional: e.g., aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" />
                {errors.team_id && <p className="text-sm text-red-500">{errors.team_id.message}</p>}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="reports_to_id">Reports To ID (UUID)</Label>
                <Input id="reports_to_id" {...register('reports_to_id')} placeholder="Optional: e.g., aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" />
                {errors.reports_to_id && <p className="text-sm text-red-500">{errors.reports_to_id.message}</p>}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="role">Role</Label>
                <Select
                  onValueChange={(value) => setValue('role', value as UserRole, { shouldValidate: true })}
                  value={watch('role') || undefined}
                  name="role" // Name is important for react-hook-form to connect with Controller if used
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a role" />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.values(UserRole).map((role) => (
                      <SelectItem key={role} value={role}>
                        {role.charAt(0).toUpperCase() + role.slice(1).toLowerCase().replace(/_/g, ' ')}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.role && <p className="text-sm text-red-500">{errors.role.message}</p>}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="is_active">Status</Label>
                <Select
                    onValueChange={(value) => setValue('is_active', value === 'true' ? true : value === 'false' ? false : null, { shouldValidate: true })}
                    value={watch('is_active') === null || watch('is_active') === undefined ? '' : String(watch('is_active'))}
                    name="is_active"
                >
                    <SelectTrigger>
                        <SelectValue placeholder="Select status" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="true">Active</SelectItem>
                        <SelectItem value="false">Inactive</SelectItem>
                        <SelectItem value="">Not Set</SelectItem> {/* Option for null/undefined */} 
                    </SelectContent>
                </Select>
                {errors.is_active && <p className="text-sm text-red-500">{errors.is_active.message}</p>}
              </div>
              <DialogFooter className="mt-2">
                <DialogClose asChild>
                   <Button type="button" variant="outline">Cancel</Button>
                </DialogClose>
                <Button type="submit" disabled={mutation.isPending}>
                  {mutation.isPending ? 'Saving...' : 'Save changes'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};

export default UserManagementPage; 