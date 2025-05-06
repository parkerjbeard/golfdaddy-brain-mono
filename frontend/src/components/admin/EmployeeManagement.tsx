import { useState } from 'react';
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/components/ui/use-toast";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { UserCog, UserCheck, UserX } from 'lucide-react';

interface Employee {
  id: string;
  name: string;
  email: string;
  role: string;
  department?: string;
  status: 'active' | 'pending';
}

export const EmployeeManagement = () => {
  const [employees, setEmployees] = useState<Employee[]>([
    {
      id: "1",
      name: "Alex Johnson",
      email: "alex@company.com",
      role: "leadership",
      department: "Engineering",
      status: "active"
    },
    {
      id: "2",
      name: "Emily Chen",
      email: "emily@company.com",
      role: "manager",
      department: "Product",
      status: "active"
    },
    {
      id: "3",
      name: "Michael Davis",
      email: "michael@company.com",
      role: "employee",
      department: "Marketing",
      status: "active"
    },
    {
      id: "4",
      name: "Sarah Williams",
      email: "sarah@company.com",
      role: "employee",
      status: "pending"
    },
    {
      id: "5",
      name: "David Brown",
      email: "david@company.com",
      role: "employee",
      status: "pending"
    }
  ]);

  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);
  const [isRoleDialogOpen, setIsRoleDialogOpen] = useState(false);
  const [newRole, setNewRole] = useState('');
  const [newDepartment, setNewDepartment] = useState('');

  const handleApproveEmployee = (employee: Employee) => {
    setSelectedEmployee(employee);
    setNewRole(employee.role);
    setNewDepartment(employee.department || '');
    setIsRoleDialogOpen(true);
  };

  const handleRejectEmployee = (employeeId: string) => {
    const updatedEmployees = employees.filter(emp => emp.id !== employeeId);
    setEmployees(updatedEmployees);
    
    toast({
      title: "Employee Rejected",
      description: "The employee request has been rejected."
    });
  };

  const handleSaveRole = () => {
    if (!selectedEmployee) return;
    
    const updatedEmployees = employees.map(emp => {
      if (emp.id === selectedEmployee.id) {
        return {
          ...emp,
          role: newRole,
          department: newDepartment || emp.department,
          status: 'active' as const
        };
      }
      return emp;
    });
    
    setEmployees(updatedEmployees);
    
    toast({
      title: "Role Updated",
      description: `${selectedEmployee.name}'s role has been updated to ${newRole}.`
    });
    
    setIsRoleDialogOpen(false);
  };

  const handleChangeRole = (employeeId: string, role: string) => {
    const updatedEmployees = employees.map(emp => {
      if (emp.id === employeeId) {
        return { ...emp, role };
      }
      return emp;
    });
    
    setEmployees(updatedEmployees);
    
    toast({
      title: "Role Updated",
      description: `Employee role has been updated to ${role}.`
    });
  };

  return (
    <div>
      <Card className="mb-6 p-6">
        <h2 className="text-xl font-medium mb-4">Pending Employees</h2>
        
        {employees.filter(emp => emp.status === 'pending').length === 0 ? (
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
                {employees
                  .filter(employee => employee.status === 'pending')
                  .map((employee) => (
                    <TableRow key={employee.id}>
                      <TableCell>
                        <div className="font-medium">{employee.name}</div>
                      </TableCell>
                      <TableCell>{employee.email}</TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          <Button 
                            size="sm" 
                            variant="outline" 
                            className="flex items-center gap-1"
                            onClick={() => handleApproveEmployee(employee)}
                          >
                            <UserCheck className="h-4 w-4" />
                            Approve
                          </Button>
                          <Button 
                            size="sm" 
                            variant="outline" 
                            className="flex items-center gap-1 text-red-500 hover:text-red-700"
                            onClick={() => handleRejectEmployee(employee.id)}
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
              {employees
                .filter(employee => employee.status === 'active')
                .map((employee) => (
                  <TableRow key={employee.id}>
                    <TableCell>
                      <div className="font-medium">{employee.name}</div>
                    </TableCell>
                    <TableCell>{employee.email}</TableCell>
                    <TableCell>{employee.department || 'Not assigned'}</TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {employee.role.charAt(0).toUpperCase() + employee.role.slice(1)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Select 
                        value={employee.role} 
                        onValueChange={(value) => handleChangeRole(employee.id, value)}
                      >
                        <SelectTrigger className="w-36">
                          <SelectValue placeholder="Change role" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="employee">Employee</SelectItem>
                          <SelectItem value="manager">Manager</SelectItem>
                          <SelectItem value="leadership">Leadership</SelectItem>
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
                onValueChange={setNewRole}
              >
                <SelectTrigger id="role">
                  <SelectValue placeholder="Select role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="employee">Employee</SelectItem>
                  <SelectItem value="manager">Manager</SelectItem>
                  <SelectItem value="leadership">Leadership</SelectItem>
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
