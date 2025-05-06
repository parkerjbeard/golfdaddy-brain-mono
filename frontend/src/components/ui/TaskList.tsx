
import { forwardRef, HTMLAttributes, useState } from 'react';
import { Card } from './card';
import { cn } from '@/lib/utils';
import { CheckCircle, Circle, Clock, ChevronDown } from 'lucide-react';
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuTrigger 
} from '@/components/ui/dropdown-menu';

interface Task {
  id: number;
  title: string;
  description?: string;
  assignee?: string;
  dueDate?: string;
  status?: string;
  category?: string;
}

interface TaskListProps {
  tasks: Task[];
  onStatusChange?: (taskId: number, newStatus: string) => void;
  className?: string;
}

export function TaskList({ tasks, onStatusChange, className }: TaskListProps) {
  // Format date to more readable form
  const formatDate = (dateString?: string) => {
    if (!dateString) return '';
    const options: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };
    return new Date(dateString).toLocaleDateString('en-US', options);
  };

  // Determine if a task is overdue
  const isOverdue = (dateString?: string) => {
    if (!dateString) return false;
    const dueDate = new Date(dateString);
    const today = new Date();
    return dueDate < today && dueDate.toDateString() !== today.toDateString();
  };

  // Get status badge styling
  const getStatusBadge = (status?: string) => {
    if (!status) return 'bg-gray-100 text-gray-800';
    
    switch (status) {
      case 'done':
        return 'bg-green-100 text-green-800';
      case 'in-progress':
        return 'bg-blue-100 text-blue-800';
      case 'open':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  // Get category badge styling
  const getCategoryBadge = (category?: string) => {
    if (!category) return 'bg-gray-100 text-gray-800';
    
    switch (category) {
      case 'bug':
        return 'bg-red-100 text-red-800';
      case 'planning':
        return 'bg-purple-100 text-purple-800';
      case 'review':
        return 'bg-yellow-100 text-yellow-800';
      case 'people':
        return 'bg-indigo-100 text-indigo-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  // Helper to safely capitalize the first letter of a string
  const capitalize = (str?: string) => {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
  };

  // Helper to get status display text
  const getStatusDisplayText = (status?: string) => {
    if (!status) return '';
    return status === 'in-progress' ? 'In Progress' : capitalize(status);
  };

  // Status options for the dropdown
  const statusOptions = [
    { value: 'open', label: 'Open' },
    { value: 'in-progress', label: 'In Progress' },
    { value: 'done', label: 'Done' }
  ];

  return (
    <Card className={`p-0 overflow-hidden ${className}`}>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-secondary/50">
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Task</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Status</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Category</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Due Date</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {tasks.map((task) => (
              <tr key={task.id} className="group transition-colors hover:bg-secondary/30">
                <td className="px-4 py-3">
                  <div>
                    <p className="font-medium">{task.title}</p>
                    <p className="mt-1 text-sm text-muted-foreground line-clamp-1">{task.description || ''}</p>
                  </div>
                </td>
                <td className="px-4 py-3">
                  {onStatusChange ? (
                    <DropdownMenu>
                      <DropdownMenuTrigger className="focus:outline-none">
                        <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${getStatusBadge(task.status)} cursor-pointer hover:opacity-80`}>
                          {task.status === 'done' ? (
                            <CheckCircle className="h-3 w-3" />
                          ) : task.status === 'in-progress' ? (
                            <Clock className="h-3 w-3" />
                          ) : (
                            <Circle className="h-3 w-3" />
                          )}
                          {getStatusDisplayText(task.status)}
                          <ChevronDown className="h-3 w-3 ml-1" />
                        </span>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="start" className="bg-popover p-1 shadow-md">
                        {statusOptions.map((option) => (
                          <DropdownMenuItem 
                            key={option.value}
                            className={`text-xs flex items-center gap-1.5 cursor-pointer ${task.status === option.value ? 'bg-secondary' : ''}`}
                            onClick={() => onStatusChange(task.id, option.value)}
                          >
                            {option.value === 'done' ? (
                              <CheckCircle className="h-3 w-3" />
                            ) : option.value === 'in-progress' ? (
                              <Clock className="h-3 w-3" />
                            ) : (
                              <Circle className="h-3 w-3" />
                            )}
                            {option.label}
                          </DropdownMenuItem>
                        ))}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  ) : (
                    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${getStatusBadge(task.status)}`}>
                      {task.status === 'done' ? (
                        <CheckCircle className="h-3 w-3" />
                      ) : task.status === 'in-progress' ? (
                        <Clock className="h-3 w-3" />
                      ) : (
                        <Circle className="h-3 w-3" />
                      )}
                      {getStatusDisplayText(task.status)}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {task.category && (
                    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${getCategoryBadge(task.category)}`}>
                      {capitalize(task.category)}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {task.dueDate && (
                    <span className={`text-sm ${isOverdue(task.dueDate) ? 'text-red-600 font-medium' : ''}`}>
                      {formatDate(task.dueDate)}
                      {isOverdue(task.dueDate) && " (Overdue)"}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {/* We've made the status dropdown our primary action, so we don't need these buttons anymore */}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
