import { useState, useEffect } from 'react';
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/components/ui/use-toast";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { UserCog, UserCheck, UserX } from 'lucide-react';
import { useUserSelectors, useAppStore } from '@/store';
import { UserResponse, UserRole } from '@/types/user';

interface Employee {
  id: string;
  name: string;
  email: string;
  role: string;
  team?: string;
  status: 'active' | 'pending';
}

export const EmployeeManagement = () => {
  // Use the new store system
  const { filteredUsers } = useUserSelectors();
  const { actions } = useAppStore();
  
  const [selectedEmployee, setSelectedEmployee] = useState<UserResponse | null>(null);
  const [isRoleDialogOpen, setIsRoleDialogOpen] = useState(false);
  const [newRole, setNewRole] = useState<UserRole>(UserRole.USER);
  const [newDepartment, setNewDepartment] = useState('');

  // Filter users by status (assuming we have an is_active field or similar)
  const activeUsers = filteredUsers.filter(user => user.is_active !== false);
  const pendingUsers = filteredUsers.filter(user => user.is_active === false);

  // Load users on component mount
  useEffect(() => {
    actions.users.fetch();
  }, [actions.users]);

  const handleApproveEmployee = (user: UserResponse) => {
    setSelectedEmployee(user);
    setNewRole(user.role);
    setNewDepartment(user.team || '');
    setIsRoleDialogOpen(true);
  };

  const handleRejectEmployee = async (userId: string) => {
    try {
      await actions.users.delete(userId);
      toast({
        title: "Employee Rejected",
        description: "The employee request has been rejected."
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to reject employee request.",
        variant: "destructive"
      });
    }
  };

  const handleSaveRole = async () => {
    if (!selectedEmployee) return;
    
    try {
      await actions.users.update(selectedEmployee.id, {
        role: newRole,
        team: newDepartment || selectedEmployee.team,
        is_active: true
      });
      
      toast({
        title: "Role Updated",
        description: `${selectedEmployee.name || selectedEmployee.email}'s role has been updated to ${newRole}.`
      });
      
      setIsRoleDialogOpen(false);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to update employee role.",
        variant: "destructive"
      });
    }
  };

  const handleChangeRole = async (userId: string, role: UserRole) => {
    try {
      await actions.users.update(userId, { role });
      
      toast({
        title: "Role Updated",
        description: `Employee role has been updated to ${role}.`
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to update employee role.",
        variant: "destructive"
      });
    }
  };

  return (
    <div>
      <Card className="mb-6 p-6">
        <h2 className="text-xl font-medium mb-4">Pending Employees</h2>
        
        {pendingUsers.length === 0 ? (
          <div className="text-center p-4 text-muted-foreground">
            No pending employee requests.
          </div>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pendingUsers.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell>
                      <div className="font-medium">{user.name || user.email}</div>
                    </TableCell>
                    <TableCell>{user.email}</TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button 
                          size="sm" 
                          variant="outline" 
                          className="flex items-center gap-1"
                          onClick={() => handleApproveEmployee(user)}
                        >
                          <UserCheck className="h-4 w-4" />
                          Approve
                        </Button>
                        <Button 
                          size="sm" 
                          variant="outline" 
                          className="flex items-center gap-1 text-red-500 hover:text-red-700"
                          onClick={() => handleRejectEmployee(user.id)}
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
        )}
      </Card>

      <Card className="p-6">
        <h2 className="text-xl font-medium mb-4">Active Employees</h2>
        
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Department</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {activeUsers.map((user) => (
                <TableRow key={user.id}>
                  <TableCell>
                    <div className="font-medium">{user.name || user.email}</div>
                  </TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell>{user.team || 'Not assigned'}</TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {user.role.charAt(0).toUpperCase() + user.role.slice(1).toLowerCase()}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Select 
                      value={user.role} 
                      onValueChange={(value) => handleChangeRole(user.id, value as UserRole)}
                    >
                      <SelectTrigger className="w-36">
                        <SelectValue placeholder="Change role" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value={UserRole.USER}>User</SelectItem>
                        <SelectItem value={UserRole.DEVELOPER}>Developer</SelectItem>
                        <SelectItem value={UserRole.MANAGER}>Manager</SelectItem>
                        <SelectItem value={UserRole.ADMIN}>Admin</SelectItem>
                      </SelectContent>
                    </Select>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Card>

      <Dialog open={isRoleDialogOpen} onOpenChange={setIsRoleDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Assign Role & Department</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <label className="text-sm font-medium" htmlFor="role">
                Role
              </label>
              <Select 
                value={newRole} 
                onValueChange={(value) => setNewRole(value as UserRole)}
              >
                <SelectTrigger id="role">
                  <SelectValue placeholder="Select role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={UserRole.USER}>User</SelectItem>
                  <SelectItem value={UserRole.DEVELOPER}>Developer</SelectItem>
                  <SelectItem value={UserRole.MANAGER}>Manager</SelectItem>
                  <SelectItem value={UserRole.ADMIN}>Admin</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <label className="text-sm font-medium" htmlFor="department">
                Department
              </label>
              <Select 
                value={newDepartment} 
                onValueChange={setNewDepartment}
              >
                <SelectTrigger id="department">
                  <SelectValue placeholder="Select department" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Engineering">Engineering</SelectItem>
                  <SelectItem value="Product">Product</SelectItem>
                  <SelectItem value="Marketing">Marketing</SelectItem>
                  <SelectItem value="Sales">Sales</SelectItem>
                  <SelectItem value="HR">HR</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsRoleDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveRole}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
