import React, { useEffect, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";
import { useTaskSelectors, useAppStore } from '@/store';
import { TaskStatus } from '@/types/entities';

// Mock User and RaciTask types - these should ideally come from @/types/entities
interface User {
  id: string;
  name: string;
  email?: string;
}

interface RaciTask {
  id: string;
  title: string;
  description?: string;
  assignee: User | null;
  responsible: User | null;
  accountable: User | null;
  // consulted: User[];
  // informed: User[];
  // creator: User;
  due_date: string | null;
  status: 'OPEN' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED'; // Example statuses
  priority?: string | null;
  task_type?: string | null;
  created_at?: string;
  updated_at?: string;
}

// Mock API function - replace with actual apiService call
const mockGetAllRaciTasks = (token: string): Promise<RaciTask[]> => {
  console.log("mockGetAllRaciTasks called with token:", token ? "present" : "absent");
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve([
        {
          id: "task1",
          title: "Develop Feature X",
          assignee: { id: "user1", name: "Alice Wonderland" },
          responsible: { id: "user1", name: "Alice Wonderland" },
          accountable: { id: "user2", name: "Bob The Builder" },
          due_date: "2024-08-15T00:00:00.000Z",
          status: "IN_PROGRESS",
          priority: "High",
        },
        {
          id: "task2",
          title: "Write Documentation for Feature X",
          assignee: { id: "user3", name: "Charlie Brown" },
          responsible: { id: "user3", name: "Charlie Brown" },
          accountable: { id: "user2", name: "Bob The Builder" },
          due_date: "2024-08-20T00:00:00.000Z",
          status: "OPEN",
          priority: "Medium",
        },
        {
          id: "task3",
          title: "Review UI Mockups",
          assignee: { id: "user4", name: "Diana Prince" },
          responsible: null,
          accountable: { id: "user5", name: "Eve Moneypenny" },
          due_date: null,
          status: "COMPLETED",
        },
      ]);
    }, 1500);
  });
};


export const RaciTaskDashboard: React.FC = () => {
  const { user } = useAuth();
  const { filteredTasks, taskStats } = useTaskSelectors();
  const { actions, status } = useAppStore();

  useEffect(() => {
    // Load tasks on component mount
    actions.tasks.fetch();
  }, [actions.tasks]);

  const getStatusBadgeVariant = (status: TaskStatus) => {
    switch (status) {
      case TaskStatus.OPEN:
        return 'outline';
      case TaskStatus.ASSIGNED:
        return 'outline';
      case TaskStatus.IN_PROGRESS:
        return 'default';
      case TaskStatus.UNDER_REVIEW:
        return 'default';
      case TaskStatus.DONE:
        return 'secondary';
      case TaskStatus.BLOCKED:
        return 'destructive';
      case TaskStatus.ARCHIVED:
        return 'secondary';
      default:
        return 'outline';
    }
  };
  
  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch (e) {
      return 'Invalid Date';
    }
  };


  if (status.isLoading) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-8 w-1/4" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  if (status.hasErrors) {
    return (
      <Alert variant="destructive" className="m-4">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{status.errors.join(', ')}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="p-1">
      {filteredTasks.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          No RACI tasks found.
        </div>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead>Assignee</TableHead>
                <TableHead>Responsible</TableHead>
                <TableHead>Accountable</TableHead>
                <TableHead>Due Date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredTasks.map((task) => (
                <TableRow key={task.id}>
                  <TableCell className="font-medium max-w-xs truncate" title={task.title}>{task.title}</TableCell>
                  <TableCell>{task.assignee ? `${task.assignee.first_name} ${task.assignee.last_name}` : 'N/A'}</TableCell>
                  <TableCell>{task.responsible ? `${task.responsible.first_name} ${task.responsible.last_name}` : 'N/A'}</TableCell>
                  <TableCell>{task.accountable ? `${task.accountable.first_name} ${task.accountable.last_name}` : 'N/A'}</TableCell>
                  <TableCell>{formatDate(task.due_date)}</TableCell>
                  <TableCell>
                    <Badge variant={getStatusBadgeVariant(task.status)}>
                      {task.status.replace('_', ' ')}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="outline" size="sm" className="mr-2" onClick={() => console.log('Review task:', task.id)}>
                      Review
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => actions.tasks.update(task.id, { status: TaskStatus.IN_PROGRESS })}>
                      Edit
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}; 