import React, { useEffect, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
// import { getAllRaciTasks } from '@/lib/apiService'; // Will be uncommented later
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";

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
  const { token, loading: authLoading } = useAuth();
  const [tasks, setTasks] = useState<RaciTask[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) {
      return; // Wait for auth loading to complete
    }

    if (!token) {
      setError("Authentication token not available. Cannot fetch tasks.");
      setIsLoading(false);
      return;
    }

    const fetchTasks = async () => {
      setIsLoading(true);
      setError(null);
      try {
        // const fetchedTasks = await getAllRaciTasks(token); // Real call
        const fetchedTasks = await mockGetAllRaciTasks(token); // Mock call
        setTasks(fetchedTasks);
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "An unknown error occurred";
        setError(`Failed to fetch RACI tasks: ${errorMessage}`);
        console.error("Error fetching RACI tasks:", err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchTasks();
  }, [token, authLoading]);

  const getStatusBadgeVariant = (status: RaciTask['status']) => {
    switch (status) {
      case 'OPEN':
        return 'outline';
      case 'IN_PROGRESS':
        return 'default'; // Or a specific color like "bg-blue-500 text-white"
      case 'COMPLETED':
        return 'secondary'; // Or "bg-green-500 text-white"
      case 'CANCELLED':
        return 'destructive';
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


  if (authLoading || isLoading) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-8 w-1/4" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive" className="m-4">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="p-1"> {/* Reduced padding if Card already has it */}
      {tasks.length === 0 ? (
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
              {tasks.map((task) => (
                <TableRow key={task.id}>
                  <TableCell className="font-medium max-w-xs truncate" title={task.title}>{task.title}</TableCell>
                  <TableCell>{task.assignee?.name || 'N/A'}</TableCell>
                  <TableCell>{task.responsible?.name || 'N/A'}</TableCell>
                  <TableCell>{task.accountable?.name || 'N/A'}</TableCell>
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
                    <Button variant="outline" size="sm" onClick={() => console.log('Edit task:', task.id)}>
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