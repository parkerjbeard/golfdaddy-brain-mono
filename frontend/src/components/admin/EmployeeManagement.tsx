import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/use-toast";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { UserCog, UserCheck, UserX, Mail, Users, Github, Slack, Edit, Trash2, UserPlus } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { UserResponse, UserRole, UserUpdateByAdminPayload } from '@/types/user';
import api from '@/services/api/endpoints';
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

export const EmployeeManagement = () => {
  const { session } = useAuth();
  const token = session?.access_token || null;
  
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [isLoadingUsers, setIsLoadingUsers] = useState<boolean>(false);
  const [errorUsers, setErrorUsers] = useState<string | null>(null);
  
  const [selectedUser, setSelectedUser] = useState<UserResponse | null>(null);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  
  // Edit form state
  const [editFormData, setEditFormData] = useState<UserUpdateByAdminPayload>({});
  
  // Add form state
  const [addFormData, setAddFormData] = useState<{
    name: string;
    email: string;
    role: UserRole;
    team: string;
    slack_id: string;
    github_username: string;
  }>({
    name: '',
    email: '',
    role: UserRole.USER,
    team: '',
    slack_id: '',
    github_username: ''
  });

  // Fetch users - same pattern as manager dashboard
  useEffect(() => {
    const fetchUsersList = async () => {
      setIsLoadingUsers(true);
      setErrorUsers(null);
      try {
        if (!token) {
          setErrorUsers('Authentication token not found.');
          setIsLoadingUsers(false);
          return;
        }
        const fetchedUsers = await api.users.getUsers();
        setUsers(fetchedUsers);
      } catch (err) {
        setErrorUsers(err instanceof Error ? err.message : 'Failed to fetch users.');
        console.error('Error fetching users:', err);
      }
      setIsLoadingUsers(false);
    };
    fetchUsersList();
  }, [token]);

  // Filter users by status
  const activeUsers = users.filter(user => user.is_active !== false);
  const pendingUsers = users.filter(user => user.is_active === false);

  const handleEditUser = (user: UserResponse) => {
    setSelectedUser(user);
    setEditFormData({
      name: user.name || '',
      email: user.email || '',
      role: user.role,
      team: user.team || '',
      slack_id: user.slack_id || '',
      github_username: user.github_username || '',
      is_active: user.is_active
    });
    setIsEditDialogOpen(true);
  };

  const handleSaveUser = async () => {
    if (!selectedUser || !token) return;
    
    try {
      await api.users.updateUser(selectedUser.id, editFormData);
      
      // Update local state
      setUsers(users.map(u => 
        u.id === selectedUser.id 
          ? { ...u, ...editFormData }
          : u
      ));
      
      toast({
        title: "User Updated",
        description: `${editFormData.name || selectedUser.email} has been updated successfully.`
      });
      
      setIsEditDialogOpen(false);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to update user.",
        variant: "destructive"
      });
    }
  };

  const handleAddUser = async () => {
    if (!token || !addFormData.email) {
      toast({
        title: "Error",
        description: "Email is required to create a new user.",
        variant: "destructive"
      });
      return;
    }
    
    try {
      const newUser = await api.users.createUser({
        ...addFormData,
        is_active: true
      });
      
      // Update local state
      setUsers([...users, newUser]);
      
      toast({
        title: "User Created",
        description: `${addFormData.name || addFormData.email} has been added successfully.`
      });
      
      // Reset form and close dialog
      setAddFormData({
        name: '',
        email: '',
        role: UserRole.USER,
        team: '',
        slack_id: '',
        github_username: ''
      });
      setIsAddDialogOpen(false);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to create user. They may need to sign up first.",
        variant: "destructive"
      });
    }
  };

  const handleDeleteUser = async () => {
    if (!selectedUser || !token) return;
    
    try {
      await api.users.deleteUser(selectedUser.id);
      
      // Update local state
      setUsers(users.filter(u => u.id !== selectedUser.id));
      
      toast({
        title: "User Deleted",
        description: `${selectedUser.name || selectedUser.email} has been removed from the system.`
      });
      
      setIsDeleteDialogOpen(false);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete user.",
        variant: "destructive"
      });
    }
  };

  const handleApproveUser = async (user: UserResponse) => {
    try {
      await api.users.updateUser(user.id, { is_active: true });
      
      // Update local state
      setUsers(users.map(u => 
        u.id === user.id 
          ? { ...u, is_active: true }
          : u
      ));
      
      toast({
        title: "User Approved",
        description: `${user.name || user.email} has been approved and activated.`
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to approve user.",
        variant: "destructive"
      });
    }
  };

  const getRoleBadgeVariant = (role: UserRole) => {
    switch (role) {
      case UserRole.ADMIN:
        return "destructive";
      case UserRole.MANAGER:
      case UserRole.LEAD:
        return "default";
      case UserRole.DEVELOPER:
        return "secondary";
      default:
        return "outline";
    }
  };

  if (isLoadingUsers) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center h-64">
          <p className="text-muted-foreground">Loading employees...</p>
        </CardContent>
      </Card>
    );
  }

  if (errorUsers) {
    return (
      <Card className="border-destructive">
        <CardHeader>
          <CardTitle className="text-destructive">Error Loading Employees</CardTitle>
        </CardHeader>
        <CardContent>
          <p>{errorUsers}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Pending Users Section */}
      {pendingUsers.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              Pending Approvals
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pendingUsers.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <Avatar className="h-8 w-8">
                            <AvatarImage src={user.avatar_url || undefined} alt={user.name || user.email || ''} />
                            <AvatarFallback>{(user.name || user.email || '?').charAt(0).toUpperCase()}</AvatarFallback>
                          </Avatar>
                          <div>
                            <p className="font-medium">{user.name || 'No name'}</p>
                            <p className="text-xs text-muted-foreground">ID: {user.id.substring(0, 8)}...</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>{user.email || 'No email'}</TableCell>
                      <TableCell>
                        <Badge variant={getRoleBadgeVariant(user.role)}>
                          {user.role}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          <Button 
                            size="sm" 
                            variant="outline" 
                            className="flex items-center gap-1"
                            onClick={() => handleApproveUser(user)}
                          >
                            <UserCheck className="h-4 w-4" />
                            Approve
                          </Button>
                          <Button 
                            size="sm" 
                            variant="outline" 
                            className="flex items-center gap-1 text-destructive hover:text-destructive"
                            onClick={() => {
                              setSelectedUser(user);
                              setIsDeleteDialogOpen(true);
                            }}
                          >
                            <UserX className="h-4 w-4" />
                            Reject
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Active Users Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <UserCog className="h-5 w-5" />
              Active Employees
            </CardTitle>
            <Button 
              onClick={() => setIsAddDialogOpen(true)}
              className="flex items-center gap-2"
            >
              <UserPlus className="h-4 w-4" />
              Add Employee
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Employee</TableHead>
                  <TableHead>Contact</TableHead>
                  <TableHead>Team</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {activeUsers.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <Avatar className="h-8 w-8">
                          <AvatarImage src={user.avatar_url || undefined} alt={user.name || user.email || ''} />
                          <AvatarFallback>{(user.name || user.email || '?').charAt(0).toUpperCase()}</AvatarFallback>
                        </Avatar>
                        <div>
                          <p className="font-medium">{user.name || 'No name'}</p>
                          <p className="text-xs text-muted-foreground">ID: {user.id.substring(0, 8)}...</p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        {user.email && (
                          <div className="flex items-center gap-1 text-sm">
                            <Mail className="h-3 w-3" />
                            {user.email}
                          </div>
                        )}
                        {user.slack_id && (
                          <div className="flex items-center gap-1 text-sm text-muted-foreground">
                            <Slack className="h-3 w-3" />
                            {user.slack_id}
                          </div>
                        )}
                        {user.github_username && (
                          <div className="flex items-center gap-1 text-sm text-muted-foreground">
                            <Github className="h-3 w-3" />
                            {user.github_username}
                          </div>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>{user.team || 'Not assigned'}</TableCell>
                    <TableCell>
                      <Badge variant={getRoleBadgeVariant(user.role)}>
                        {user.role}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="bg-green-50">
                        Active
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button 
                          size="sm" 
                          variant="ghost"
                          onClick={() => handleEditUser(user)}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button 
                          size="sm" 
                          variant="ghost"
                          className="text-destructive hover:text-destructive"
                          onClick={() => {
                            setSelectedUser(user);
                            setIsDeleteDialogOpen(true);
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Edit Employee</DialogTitle>
            <DialogDescription>
              Update employee information and permissions
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="name">Name</Label>
                <Input 
                  id="name"
                  value={editFormData.name || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="email">Email</Label>
                <Input 
                  id="email"
                  type="email"
                  value={editFormData.email || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, email: e.target.value })}
                />
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="role">Role</Label>
                <Select 
                  value={editFormData.role} 
                  onValueChange={(value) => setEditFormData({ ...editFormData, role: value as UserRole })}
                >
                  <SelectTrigger id="role">
                    <SelectValue placeholder="Select role" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={UserRole.USER}>User</SelectItem>
                    <SelectItem value={UserRole.VIEWER}>Viewer</SelectItem>
                    <SelectItem value={UserRole.DEVELOPER}>Developer</SelectItem>
                    <SelectItem value={UserRole.LEAD}>Lead</SelectItem>
                    <SelectItem value={UserRole.MANAGER}>Manager</SelectItem>
                    <SelectItem value={UserRole.ADMIN}>Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="team">Team</Label>
                <Input 
                  id="team"
                  value={editFormData.team || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, team: e.target.value })}
                  placeholder="e.g., Engineering, Product, Sales"
                />
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="slack_id">Slack ID</Label>
                <Input 
                  id="slack_id"
                  value={editFormData.slack_id || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, slack_id: e.target.value })}
                  placeholder="@username"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="github_username">GitHub Username</Label>
                <Input 
                  id="github_username"
                  value={editFormData.github_username || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, github_username: e.target.value })}
                  placeholder="username"
                />
              </div>
            </div>
            
            <div className="grid gap-2">
              <Label htmlFor="status">Status</Label>
              <Select 
                value={editFormData.is_active ? 'active' : 'inactive'} 
                onValueChange={(value) => setEditFormData({ ...editFormData, is_active: value === 'active' })}
              >
                <SelectTrigger id="status">
                  <SelectValue placeholder="Select status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveUser}>Save Changes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add User Dialog */}
      <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Add New Employee</DialogTitle>
            <DialogDescription>
              Create a new employee account. They will receive an invitation to set up their password.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="add-name">Name *</Label>
                <Input 
                  id="add-name"
                  value={addFormData.name}
                  onChange={(e) => setAddFormData({ ...addFormData, name: e.target.value })}
                  placeholder="John Doe"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="add-email">Email *</Label>
                <Input 
                  id="add-email"
                  type="email"
                  value={addFormData.email}
                  onChange={(e) => setAddFormData({ ...addFormData, email: e.target.value })}
                  placeholder="john@company.com"
                  required
                />
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="add-role">Role</Label>
                <Select 
                  value={addFormData.role} 
                  onValueChange={(value) => setAddFormData({ ...addFormData, role: value as UserRole })}
                >
                  <SelectTrigger id="add-role">
                    <SelectValue placeholder="Select role" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={UserRole.USER}>User</SelectItem>
                    <SelectItem value={UserRole.VIEWER}>Viewer</SelectItem>
                    <SelectItem value={UserRole.DEVELOPER}>Developer</SelectItem>
                    <SelectItem value={UserRole.LEAD}>Lead</SelectItem>
                    <SelectItem value={UserRole.MANAGER}>Manager</SelectItem>
                    <SelectItem value={UserRole.ADMIN}>Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="add-team">Team</Label>
                <Input 
                  id="add-team"
                  value={addFormData.team}
                  onChange={(e) => setAddFormData({ ...addFormData, team: e.target.value })}
                  placeholder="e.g., Engineering, Product, Sales"
                />
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="add-slack_id">Slack ID</Label>
                <Input 
                  id="add-slack_id"
                  value={addFormData.slack_id}
                  onChange={(e) => setAddFormData({ ...addFormData, slack_id: e.target.value })}
                  placeholder="@username"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="add-github_username">GitHub Username</Label>
                <Input 
                  id="add-github_username"
                  value={addFormData.github_username}
                  onChange={(e) => setAddFormData({ ...addFormData, github_username: e.target.value })}
                  placeholder="username"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddUser}>Create Employee</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Deletion</DialogTitle>
            <DialogDescription>
              Are you sure you want to remove {selectedUser?.name || selectedUser?.email} from the system? 
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteUser}>
              Delete User
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};