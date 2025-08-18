// Mock data for development and demo purposes

export interface Employee {
  id: string;
  name: string;
  email: string;
  role: string;
  department: string;
  avatar?: string;
}

export interface Task {
  id: string;
  title: string;
  assignee: string;
  status: 'pending' | 'in-progress' | 'completed';
  priority: 'low' | 'medium' | 'high';
  dueDate: string;
  description?: string;
}

export interface DailyLog {
  id: string;
  employeeId: string;
  date: string;
  summary: string;
  hours: number;
  tasks: string[];
}

// Mock employees
export const employees: Employee[] = [
  {
    id: '1',
    name: 'John Doe',
    email: 'john.doe@company.com',
    role: 'Software Engineer',
    department: 'Engineering',
    avatar: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=32&h=32&fit=crop&crop=face'
  },
  {
    id: '2',
    name: 'Jane Smith',
    email: 'jane.smith@company.com',
    role: 'Product Manager',
    department: 'Product',
    avatar: 'https://images.unsplash.com/photo-1494790108755-2616b25a48de?w=32&h=32&fit=crop&crop=face'
  },
  {
    id: '3',
    name: 'Mike Johnson',
    email: 'mike.johnson@company.com',
    role: 'Designer',
    department: 'Design',
    avatar: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=32&h=32&fit=crop&crop=face'
  }
];

// Mock tasks
export const tasks: Task[] = [
  {
    id: '1',
    title: 'Implement user authentication',
    assignee: 'John Doe',
    status: 'in-progress',
    priority: 'high',
    dueDate: '2024-01-15',
    description: 'Set up user login and registration system'
  },
  {
    id: '2',
    title: 'Design landing page',
    assignee: 'Mike Johnson',
    status: 'completed',
    priority: 'medium',
    dueDate: '2024-01-10',
    description: 'Create new landing page design'
  },
  {
    id: '3',
    title: 'Product roadmap planning',
    assignee: 'Jane Smith',
    status: 'pending',
    priority: 'high',
    dueDate: '2024-01-20',
    description: 'Plan Q1 product roadmap'
  }
];

// Mock daily logs
export const dailyLogs: DailyLog[] = [
  {
    id: '1',
    employeeId: '1',
    date: '2024-01-10',
    summary: 'Worked on authentication system implementation',
    hours: 8,
    tasks: ['1']
  },
  {
    id: '2',
    employeeId: '2',
    date: '2024-01-10',
    summary: 'Product planning and stakeholder meetings',
    hours: 7.5,
    tasks: ['3']
  },
  {
    id: '3',
    employeeId: '3',
    date: '2024-01-10',
    summary: 'Completed landing page design and started user flow',
    hours: 8,
    tasks: ['2']
  }
];

// Teams data
export const teams = [
  {
    id: '1',
    name: 'Engineering',
    members: ['John Doe', 'Alice Brown'],
    description: 'Software development team'
  },
  {
    id: '2',
    name: 'Product',
    members: ['Jane Smith'],
    description: 'Product management and strategy'
  },
  {
    id: '3',
    name: 'Design',
    members: ['Mike Johnson'],
    description: 'UI/UX design team'
  }
];

// Export aliases for compatibility
export const mockTeams = teams;
export const mockUsers = employees;

export default {
  employees,
  tasks,
  dailyLogs,
  teams
};