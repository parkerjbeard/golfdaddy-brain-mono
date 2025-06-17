/**
 * Example component demonstrating comprehensive API integration
 */

import React from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  LoadingSpinner, 
  TableLoading,
  OptimisticUpdateIndicator 
} from '@/components/ui/LoadingStates';
import { ErrorAlert } from '@/components/ui/ErrorStates';
import { useApi } from '@/hooks/useApi';
import { 
  User, 
  Task, 
  DailyReport,
  TaskPriority,
  UserRole 
} from '@/types/api';
import { 
  UserPlus, 
  Plus, 
  FileText, 
  Search, 
  RefreshCw,
  Activity,
  Users,
  CheckCircle,
  AlertCircle
} from 'lucide-react';

export const ApiIntegrationExample: React.FC = () => {
  const { auth, tasks, users, reports, health, search } = useApi();
  
  // State for different operations
  const [selectedTab, setSelectedTab] = React.useState('auth');
  const [taskData, setTaskData] = React.useState({
    title: '',
    description: '',
    priority: TaskPriority.MEDIUM,
  });
  const [userData, setUserData] = React.useState({
    name: '',
    email: '',
    role: UserRole.USER,
  });
  const [reportData, setReportData] = React.useState({
    report_date: new Date().toISOString().split('T')[0],
    raw_text_input: '',
  });
  const [searchQuery, setSearchQuery] = React.useState('');

  // Demo data
  const [demoTasks, setDemoTasks] = React.useState<Task[]>([]);
  const [demoUsers, setDemoUsers] = React.useState<User[]>([]);
  const [demoReports, setDemoReports] = React.useState<DailyReport[]>([]);

  // Load demo data
  React.useEffect(() => {
    const loadDemoData = async () => {
      try {
        const [tasksResponse, usersResponse, reportsResponse] = await Promise.allSettled([
          tasks.fetchTasks({ limit: 5 }),
          users.fetchUsers({ limit: 5 }),
          reports.fetchReports({ limit: 5 }),
        ]);

        if (tasksResponse.status === 'fulfilled' && tasksResponse.value.success) {
          setDemoTasks(tasksResponse.value.data || []);
        }
        if (usersResponse.status === 'fulfilled' && usersResponse.value.success) {
          setDemoUsers(usersResponse.value.data || []);
        }
        if (reportsResponse.status === 'fulfilled' && reportsResponse.value.success) {
          setDemoReports(reportsResponse.value.data || []);
        }
      } catch (error) {
        console.error('Failed to load demo data:', error);
      }
    };

    if (auth.isAuthenticated) {
      loadDemoData();
    }
  }, [auth.isAuthenticated, tasks, users, reports]);

  // Handle operations
  const handleCreateTask = async () => {
    if (!taskData.title.trim()) return;

    try {
      const result = await tasks.createTask({
        title: taskData.title,
        description: taskData.description,
        priority: taskData.priority,
      });

      if (result.success && result.data) {
        setDemoTasks(prev => [result.data!, ...prev]);
        setTaskData({ title: '', description: '', priority: TaskPriority.MEDIUM });
      }
    } catch (error) {
      console.error('Failed to create task:', error);
    }
  };

  const handleCreateUser = async () => {
    if (!userData.email.trim()) return;

    try {
      const result = await users.createUser({
        name: userData.name,
        email: userData.email,
        role: userData.role,
      });

      if (result.success && result.data) {
        setDemoUsers(prev => [result.data!, ...prev]);
        setUserData({ name: '', email: '', role: UserRole.USER });
      }
    } catch (error) {
      console.error('Failed to create user:', error);
    }
  };

  const handleCreateReport = async () => {
    if (!reportData.raw_text_input.trim()) return;

    try {
      const result = await reports.createReport({
        report_date: reportData.report_date,
        raw_text_input: reportData.raw_text_input,
      });

      if (result.success && result.data) {
        setDemoReports(prev => [result.data!, ...prev]);
        setReportData({ 
          report_date: new Date().toISOString().split('T')[0], 
          raw_text_input: '' 
        });
      }
    } catch (error) {
      console.error('Failed to create report:', error);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    try {
      await search.search(searchQuery, { limit: 10 });
    } catch (error) {
      console.error('Search failed:', error);
    }
  };

  const handleUpdateTaskStatus = async (taskId: string, status: string) => {
    try {
      const result = await tasks.updateTaskStatus(taskId, status);
      if (result.success && result.data) {
        setDemoTasks(prev => 
          prev.map(task => 
            task.id === taskId 
              ? { ...task, status: status as any }
              : task
          )
        );
      }
    } catch (error) {
      console.error('Failed to update task status:', error);
    }
  };

  const renderAuthTab = () => (
    <div className="space-y-6">
      <Card className="p-4">
        <h3 className="font-medium mb-4 flex items-center gap-2">
          <Activity className="h-4 w-4" />
          Authentication Status
        </h3>
        
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Badge variant={auth.isAuthenticated ? 'default' : 'outline'}>
              {auth.isAuthenticated ? 'Authenticated' : 'Not Authenticated'}
            </Badge>
            {auth.loading && <LoadingSpinner size="sm" />}
          </div>
          
          {auth.user && (
            <div className="space-y-2">
              <p><strong>Name:</strong> {auth.user.name || 'Not provided'}</p>
              <p><strong>Email:</strong> {auth.user.email}</p>
              <p><strong>Role:</strong> {auth.user.role}</p>
              <p><strong>Active:</strong> {auth.user.is_active ? 'Yes' : 'No'}</p>
            </div>
          )}
          
          {auth.error && (
            <ErrorAlert 
              error={auth.error} 
              onRetry={auth.checkAuth}
            />
          )}
        </div>
        
        <div className="flex gap-2 mt-4">
          <Button onClick={auth.checkAuth} size="sm" variant="outline">
            <RefreshCw className="h-3 w-3 mr-1" />
            Refresh Auth
          </Button>
          {auth.isAuthenticated && (
            <Button onClick={auth.logout} size="sm" variant="outline">
              Logout
            </Button>
          )}
        </div>
      </Card>

      <Card className="p-4">
        <h3 className="font-medium mb-4 flex items-center gap-2">
          <Activity className="h-4 w-4" />
          System Health
        </h3>
        
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Badge variant={health.isHealthy ? 'default' : 'destructive'}>
              {health.isHealthy ? 'Healthy' : 'Unhealthy'}
            </Badge>
            {health.loading && <LoadingSpinner size="sm" />}
          </div>
          
          {health.health && (
            <div className="space-y-2 text-sm">
              <p><strong>Status:</strong> {health.health.status}</p>
              <p><strong>Version:</strong> {health.health.version}</p>
              <div>
                <strong>Services:</strong>
                <ul className="list-disc list-inside ml-2">
                  {Object.entries(health.health.services || {}).map(([service, status]) => (
                    <li key={service} className="flex items-center gap-2">
                      <span>{service}:</span>
                      <Badge variant={status === 'up' ? 'default' : 'destructive'} className="text-xs">
                        {status}
                      </Badge>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
          
          {health.error && (
            <ErrorAlert error={health.error} onRetry={health.checkHealth} />
          )}
        </div>
      </Card>
    </div>
  );

  const renderTasksTab = () => (
    <div className="space-y-6">
      <Card className="p-4">
        <h3 className="font-medium mb-4 flex items-center gap-2">
          <Plus className="h-4 w-4" />
          Create Task
        </h3>
        
        <div className="space-y-3">
          <div>
            <Label htmlFor="task-title">Title</Label>
            <Input
              id="task-title"
              value={taskData.title}
              onChange={(e) => setTaskData(prev => ({ ...prev, title: e.target.value }))}
              placeholder="Enter task title..."
            />
          </div>
          
          <div>
            <Label htmlFor="task-description">Description</Label>
            <Textarea
              id="task-description"
              value={taskData.description}
              onChange={(e) => setTaskData(prev => ({ ...prev, description: e.target.value }))}
              placeholder="Enter task description..."
            />
          </div>
          
          <div>
            <Label htmlFor="task-priority">Priority</Label>
            <select
              id="task-priority"
              value={taskData.priority}
              onChange={(e) => setTaskData(prev => ({ ...prev, priority: e.target.value as TaskPriority }))}
              className="w-full p-2 border rounded"
            >
              <option value={TaskPriority.LOW}>Low</option>
              <option value={TaskPriority.MEDIUM}>Medium</option>
              <option value={TaskPriority.HIGH}>High</option>
              <option value={TaskPriority.URGENT}>Urgent</option>
            </select>
          </div>
          
          <Button onClick={handleCreateTask} disabled={!taskData.title.trim()}>
            Create Task
          </Button>
        </div>
      </Card>

      <Card className="p-4">
        <h3 className="font-medium mb-4">Recent Tasks</h3>
        
        {demoTasks.length === 0 ? (
          <TableLoading rows={3} columns={4} />
        ) : (
          <div className="space-y-2">
            {demoTasks.map((task) => (
              <OptimisticUpdateIndicator 
                key={task.id} 
                isPending={task.id.startsWith('temp-')}
              >
                <div className="border rounded p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="font-medium">{task.title}</h4>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{task.priority}</Badge>
                      <Badge variant={task.status === 'COMPLETED' ? 'default' : 'outline'}>
                        {task.status}
                      </Badge>
                    </div>
                  </div>
                  
                  {task.description && (
                    <p className="text-sm text-muted-foreground">{task.description}</p>
                  )}
                  
                  <div className="flex gap-2">
                    <Button 
                      size="sm" 
                      variant="outline"
                      onClick={() => handleUpdateTaskStatus(task.id, 'IN_PROGRESS')}
                      disabled={task.status === 'IN_PROGRESS'}
                    >
                      Start
                    </Button>
                    <Button 
                      size="sm" 
                      variant="outline"
                      onClick={() => handleUpdateTaskStatus(task.id, 'COMPLETED')}
                      disabled={task.status === 'COMPLETED'}
                    >
                      <CheckCircle className="h-3 w-3 mr-1" />
                      Complete
                    </Button>
                  </div>
                </div>
              </OptimisticUpdateIndicator>
            ))}
          </div>
        )}
      </Card>
    </div>
  );

  const renderUsersTab = () => (
    <div className="space-y-6">
      <Card className="p-4">
        <h3 className="font-medium mb-4 flex items-center gap-2">
          <UserPlus className="h-4 w-4" />
          Create User
        </h3>
        
        <div className="space-y-3">
          <div>
            <Label htmlFor="user-name">Name</Label>
            <Input
              id="user-name"
              value={userData.name}
              onChange={(e) => setUserData(prev => ({ ...prev, name: e.target.value }))}
              placeholder="Enter user name..."
            />
          </div>
          
          <div>
            <Label htmlFor="user-email">Email</Label>
            <Input
              id="user-email"
              type="email"
              value={userData.email}
              onChange={(e) => setUserData(prev => ({ ...prev, email: e.target.value }))}
              placeholder="Enter user email..."
            />
          </div>
          
          <div>
            <Label htmlFor="user-role">Role</Label>
            <select
              id="user-role"
              value={userData.role}
              onChange={(e) => setUserData(prev => ({ ...prev, role: e.target.value as UserRole }))}
              className="w-full p-2 border rounded"
            >
              <option value={UserRole.USER}>User</option>
              <option value={UserRole.DEVELOPER}>Developer</option>
              <option value={UserRole.MANAGER}>Manager</option>
              <option value={UserRole.ADMIN}>Admin</option>
            </select>
          </div>
          
          <Button onClick={handleCreateUser} disabled={!userData.email.trim()}>
            Create User
          </Button>
        </div>
      </Card>

      <Card className="p-4">
        <h3 className="font-medium mb-4 flex items-center gap-2">
          <Users className="h-4 w-4" />
          Recent Users
        </h3>
        
        {demoUsers.length === 0 ? (
          <TableLoading rows={3} columns={3} />
        ) : (
          <div className="space-y-2">
            {demoUsers.map((user) => (
              <OptimisticUpdateIndicator 
                key={user.id} 
                isPending={user.id.startsWith('temp-')}
              >
                <div className="border rounded p-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-medium">{user.name || 'Unnamed User'}</h4>
                      <p className="text-sm text-muted-foreground">{user.email}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{user.role}</Badge>
                      <Badge variant={user.is_active ? 'default' : 'destructive'}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </div>
                  </div>
                </div>
              </OptimisticUpdateIndicator>
            ))}
          </div>
        )}
      </Card>
    </div>
  );

  const renderSearchTab = () => (
    <div className="space-y-6">
      <Card className="p-4">
        <h3 className="font-medium mb-4 flex items-center gap-2">
          <Search className="h-4 w-4" />
          Global Search
        </h3>
        
        <div className="flex gap-2">
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search tasks, users, reports..."
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
          />
          <Button onClick={handleSearch} disabled={!searchQuery.trim()}>
            {search.loading ? <LoadingSpinner size="sm" /> : <Search className="h-4 w-4" />}
          </Button>
        </div>
        
        {search.error && (
          <ErrorAlert error={search.error} onRetry={handleSearch} />
        )}
        
        {search.results.length > 0 && (
          <div className="mt-4 space-y-2">
            <h4 className="font-medium">Search Results ({search.results.length})</h4>
            {search.results.map((result, index) => (
              <div key={index} className="border rounded p-3">
                <pre className="text-xs text-muted-foreground">
                  {JSON.stringify(result, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );

  if (!auth.isAuthenticated) {
    return (
      <div className="p-6">
        <Card className="p-6 text-center">
          <AlertCircle className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          <h2 className="text-lg font-semibold mb-2">Authentication Required</h2>
          <p className="text-muted-foreground mb-4">
            Please log in to access the API integration demo.
          </p>
          {auth.loading && <LoadingSpinner />}
          {auth.error && <ErrorAlert error={auth.error} />}
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-2">API Integration Demo</h2>
        <p className="text-muted-foreground">
          Comprehensive demonstration of the API integration with error handling, optimistic updates, and real-time feedback.
        </p>
      </div>

      <Tabs value={selectedTab} onValueChange={setSelectedTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="auth">Authentication</TabsTrigger>
          <TabsTrigger value="tasks">Tasks</TabsTrigger>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="search">Search</TabsTrigger>
        </TabsList>

        <TabsContent value="auth">{renderAuthTab()}</TabsContent>
        <TabsContent value="tasks">{renderTasksTab()}</TabsContent>
        <TabsContent value="users">{renderUsersTab()}</TabsContent>
        <TabsContent value="search">{renderSearchTab()}</TabsContent>
      </Tabs>
    </div>
  );
};