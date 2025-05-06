
import { useState } from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Link, useNavigate } from "react-router-dom";
import { employees } from '@/data/mockData';

export const EmployeeList = () => {
  const navigate = useNavigate();

  return (
    <div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Employee</TableHead>
              <TableHead>Department</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Tasks</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {employees.map((employee) => (
              <TableRow key={employee.id}>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <Avatar className="h-8 w-8">
                      {employee.avatar ? (
                        <img src={employee.avatar} alt={employee.name} className="h-8 w-8 rounded-full object-cover" />
                      ) : (
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                          {employee.name.charAt(0)}
                        </div>
                      )}
                    </Avatar>
                    <div>
                      <Link to={`/profile/${employee.id}`} className="font-medium hover:underline">
                        {employee.name}
                      </Link>
                      <div className="text-sm text-muted-foreground">{employee.email}</div>
                    </div>
                  </div>
                </TableCell>
                <TableCell>{employee.department || 'N/A'}</TableCell>
                <TableCell>
                  <Badge variant="outline" className="capitalize">
                    {employee.role}
                  </Badge>
                </TableCell>
                <TableCell>{employee.taskCount || 0}</TableCell>
                <TableCell>
                  <Button variant="outline" size="sm" onClick={() => navigate(`/admin/employee/${employee.id}`)}>
                    Manage
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};
