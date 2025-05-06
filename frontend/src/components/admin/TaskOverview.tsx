
import { useState } from 'react';
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/components/ui/use-toast";
import { PlusCircle } from 'lucide-react';

interface Employee {
  id: string;
  name: string;
  role: string;
  department?: string;
  status: 'active' | 'pending';
}

interface Task {
  id: number;
  title: string;
  description: string;
  assigneeId: string;
  assigneeName: string;
  dueDate: string;
  status: string;
  category: string;
}

interface TaskOverviewProps {
  employees: Employee[];
}

export const TaskOverview = ({ employees }: TaskOverviewProps) => {
  const [tasks, setTasks] = useState<Task[]>([
    {
      id: 1,
      title: "Performance review preparation",
      description: "Prepare performance review documents for Q2",
      assigneeId: "1",
      assigneeName: "Alex Johnson",
      dueDate: "2023-07-15",
      status: "in-progress",
      category: "planning"
    },
    {
      id: 2,
      title: "Project timeline update",
      description: "Update timeline for the refactoring project",
      assigneeId: "2",
      assigneeName: "Emily Chen",
      dueDate: "2023-07-10",
      status: "open",
      category: "planning"
    }
  ]);
  
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [newTask, setNewTask] = useState<Partial<Task>>({
    title: '',
    description: '',
    assigneeId: '',
    assigneeName: '',
    dueDate: '',
    status: 'open',
    category: 'planning'
  });

  const handleAddTask = () => {
    // Find the employee name based on the selected assigneeId
    const selectedEmployee = employees.find(emp => emp.id === newTask.assigneeId);
    
    if (!selectedEmployee) {
      toast({
        title: "Error",
        description: "Please select a valid employee.",
        variant: "destructive"
      });
      return;
    }
    
    // In a real app, this would be an API call
    const taskToAdd = {
      ...newTask,
      id: Date.now(), // Generate a unique ID
      assigneeName: selectedEmployee.name,
    } as Task;
    
    setTasks([...tasks, taskToAdd]);
    
    toast({
      title: "Task Created",
      description: `"${taskToAdd.title}" has been assigned to ${taskToAdd.assigneeName}`
    });
    
    // Reset form and close dialog
    setNewTask({
      title: '',
      description: '',
      assigneeId: '',
      assigneeName: '',
      dueDate: '',
      status: 'open',
      category: 'planning'
    });
    setIsDialogOpen(false);
  };

  const handleSelectEmployee = (employeeId: string) => {
    setNewTask({
      ...newTask,
      assigneeId: employeeId
    });
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'open':
        return <Badge variant="outline">Open</Badge>;
      case 'in-progress':
        return <Badge variant="outline" className="bg-blue-100 text-blue-800 border-blue-300">In Progress</Badge>;
      case 'done':
        return <Badge variant="outline" className="bg-green-100 text-green-800 border-green-300">Done</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getCategoryBadge = (category: string) => {
    switch (category) {
      case 'planning':
        return <Badge variant="secondary">Planning</Badge>;
      case 'bug':
        return <Badge variant="destructive">Bug</Badge>;
      case 'review':
        return <Badge variant="outline">Review</Badge>;
      case 'people':
        return <Badge variant="secondary" className="bg-purple-100 text-purple-800 border-purple-300">People</Badge>;
      default:
        return <Badge>{category}</Badge>;
    }
  };

  return (
    <div>
      <Card className="p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-medium">Task Overview</h2>
          <Button onClick={() => setIsDialogOpen(true)}>
            <PlusCircle className="mr-2 h-4 w-4" />
            Create New Task
          </Button>
        </div>

        {tasks.length === 0 ? (
          <div className="text-center p-8 text-muted-foreground">
            No tasks have been created yet.
          </div>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Task</TableHead>
                  <TableHead>Assignee</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Due Date</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tasks.map((task) => (
                  <TableRow key={task.id}>
                    <TableCell>
                      <div>
                        <div className="font-medium">{task.title}</div>
                        <div className="text-sm text-muted-foreground">{task.description}</div>
                      </div>
                    </TableCell>
                    <TableCell>{task.assigneeName}</TableCell>
                    <TableCell>{getCategoryBadge(task.category)}</TableCell>
                    <TableCell>{new Date(task.dueDate).toLocaleDateString()}</TableCell>
                    <TableCell>{getStatusBadge(task.status)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Card>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Create New Task</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="title">Task Title</Label>
              <Input
                id="title"
                value={newTask.title}
                onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
                placeholder="Enter task title"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={newTask.description}
                onChange={(e) => setNewTask({ ...newTask, description: e.target.value })}
                placeholder="Describe the task details"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="assignee">Assignee</Label>
              <Select 
                value={newTask.assigneeId} 
                onValueChange={handleSelectEmployee}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select employee" />
                </SelectTrigger>
                <SelectContent>
                  {employees.filter(emp => emp.status === 'active').map((employee) => (
                    <SelectItem key={employee.id} value={employee.id}>
                      {employee.name} ({employee.department || 'No department'})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="category">Category</Label>
              <Select 
                value={newTask.category} 
                onValueChange={(value) => setNewTask({ ...newTask, category: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="planning">Planning</SelectItem>
                  <SelectItem value="bug">Bug</SelectItem>
                  <SelectItem value="review">Review</SelectItem>
                  <SelectItem value="people">People</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="dueDate">Due Date</Label>
              <Input
                id="dueDate"
                type="date"
                value={newTask.dueDate}
                onChange={(e) => setNewTask({ ...newTask, dueDate: e.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="status">Status</Label>
              <Select 
                value={newTask.status} 
                onValueChange={(value) => setNewTask({ ...newTask, status: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="open">Open</SelectItem>
                  <SelectItem value="in-progress">In Progress</SelectItem>
                  <SelectItem value="done">Done</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleAddTask}>Create Task</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
