import { Team, User } from '@/types'

export const mockUsers: User[] = [
  { id: '1', name: 'Alice Smith' },
  { id: '2', name: 'Bob Johnson' },
  { id: '3', name: 'Charlie Rose' },
]

export const mockTeams: Team[] = [
  { id: 'team-1', name: 'Developers', members: [mockUsers[0]] },
  { id: 'team-2', name: 'Designers', members: [mockUsers[1]] },
]

export const companyKpis = [
  { id: 'kpi-1', title: 'Revenue', value: '$500,000', target: '$450,000', trend: 'up', change: '+10%' },
  { id: 'kpi-2', title: 'New Customers', value: '1,200', target: '1,000', trend: 'up', change: '+20%' },
  { id: 'kpi-3', title: 'Customer Satisfaction', value: '95%', target: '92%', trend: 'up', change: '+3%' },
  { id: 'kpi-4', title: 'Employee Churn', value: '5%', target: '8%', trend: 'down', change: '-3%' },
];

export const departmentTaskCompletionData = [
  { name: 'Engineering', completed: 80, target: 90 },
  { name: 'Marketing', completed: 75, target: 80 },
  { name: 'Sales', completed: 90, target: 85 },
  { name: 'Support', completed: 85, target: 90 },
];

export const dailyLogTrendData = [
  { date: '2024-07-01', count: 150 },
  { date: '2024-07-02', count: 160 },
  { date: '2024-07-03', count: 155 },
  { date: '2024-07-04', count: 170 },
  { date: '2024-07-05', count: 165 },
];

export const achievements = [
  { id: 'ach-1', title: 'Launched New Product Feature X', department: 'Engineering', date: '2024-06-15' },
  { id: 'ach-2', title: 'Exceeded Q2 Sales Target by 15%', department: 'Sales', date: '2024-06-30' },
  { id: 'ach-3', title: 'Successful Marketing Campaign Y', department: 'Marketing', date: '2024-07-10' },
];

export const employees = [
  { id: '1', name: 'Alice Smith', role: 'developer', department: 'Engineering', avatar: '/avatars/alice.png' },
  { id: '2', name: 'Bob Johnson', role: 'designer', department: 'Design', avatar: '/avatars/bob.png' },
  { id: '3', name: 'Charlie Rose', role: 'manager', department: 'Product', avatar: '/avatars/charlie.png' },
];

export const tasks = [
  { id: 'task-1', title: 'Develop new login page', assignee: 'Alice Smith', status: 'in-progress', dueDate: '2024-08-01' },
  { id: 'task-2', title: 'Design user profile icons', assignee: 'Bob Johnson', status: 'completed', dueDate: '2024-07-20' },
  { id: 'task-3', title: 'Plan Q3 roadmap', assignee: 'Charlie Rose', status: 'pending', dueDate: '2024-07-25' },
];

export const dailyLogs = [
  { id: 'log-1', employeeId: '1', date: '2024-07-20', summary: 'Worked on login page implementation.' },
  { id: 'log-2', employeeId: '2', date: '2024-07-20', summary: 'Finalized profile icon designs.' },
  { id: 'log-3', employeeId: '1', date: '2024-07-21', summary: 'Refactored authentication logic.' },
];
