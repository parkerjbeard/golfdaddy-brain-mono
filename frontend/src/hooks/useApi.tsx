/**
 * React hooks for API integration with stores and error handling
 */

import React from 'react';
import { api, tokenManager } from '@/services/api';
import { useStoreState } from './useStoreState';
import { toast } from '@/components/ui/use-toast';
import type {
  User,
  Task,
  DailyReport,
  CreateTaskRequest,
  UpdateTaskRequest,
  CreateUserRequest,
  UpdateUserRequest,
  CreateDailyReportRequest,
  UpdateDailyReportRequest,
  TaskListParams,
  UserListParams,
  DailyReportListParams,
} from '@/types/api';

// ========== AUTHENTICATION HOOKS ==========

export const useAuth = () => {
  const [user, setUser] = React.useState<User | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const checkAuth = React.useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      const token = await tokenManager.getToken();
      if (!token) {
        setUser(null);
        return;
      }

      const currentUser = await api.auth.getCurrentUser();
      setUser(currentUser);
    } catch (err: any) {
      setError(err.message || 'Authentication check failed');
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const login = React.useCallback(async (email: string, password: string) => {
    try {
      setLoading(true);
      setError(null);

      const loginResponse = await api.auth.login({ email, password });
      await tokenManager.setTokenData(loginResponse);
      setUser(loginResponse.user);

      toast({
        title: 'Welcome back!',
        description: 'You have been successfully logged in.',
      });

      return loginResponse.user;
    } catch (err: any) {
      const errorMessage = err.message || 'Login failed';
      setError(errorMessage);
      
      toast({
        title: 'Login Failed',
        description: errorMessage,
        variant: 'destructive',
      });
      
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = React.useCallback(async () => {
    try {
      await api.auth.logout();
    } catch (err) {
      console.warn('Logout API call failed:', err);
    } finally {
      await tokenManager.clearToken();
      setUser(null);
      
      toast({
        title: 'Logged out',
        description: 'You have been successfully logged out.',
      });
    }
  }, []);

  const refreshAuth = React.useCallback(async () => {
    try {
      const newToken = await tokenManager.refreshToken();
      if (newToken) {
        const currentUser = await api.auth.getCurrentUser();
        setUser(currentUser);
        return true;
      }
      return false;
    } catch (err) {
      console.error('Auth refresh failed:', err);
      setUser(null);
      return false;
    }
  }, []);

  // Check auth on mount
  React.useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // Listen for token expiration events
  React.useEffect(() => {
    const handleTokenExpired = () => {
      setUser(null);
      setError('Your session has expired. Please log in again.');
    };

    window.addEventListener('auth-token-expired', handleTokenExpired);
    return () => window.removeEventListener('auth-token-expired', handleTokenExpired);
  }, []);

  return {
    user,
    loading,
    error,
    login,
    logout,
    refreshAuth,
    checkAuth,
    isAuthenticated: !!user,
  };
};

// ========== API HOOKS WITH STORE INTEGRATION ==========

export const useApiTasks = () => {
  const storeState = useStoreState({
    enableOptimisticUpdates: true,
    enableErrorToasts: true,
    enableSuccessToasts: true,
  });

  const fetchTasks = React.useCallback(async (params?: TaskListParams) => {
    return storeState.executeWithOptimism(
      'fetch-tasks',
      [], // Empty optimistic data for fetch
      async () => {
        const response = await api.tasks.getTasks(params);
        return { success: true, data: response.tasks };
      },
      { showSuccessToast: false }
    );
  }, [storeState]);

  const createTask = React.useCallback(async (taskData: CreateTaskRequest) => {
    const tempId = `temp-${Date.now()}`;
    const optimisticTask = {
      id: tempId,
      ...taskData,
      status: 'ASSIGNED' as const,
      blocked: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    return storeState.executeWithOptimism(
      tempId,
      optimisticTask,
      async () => {
        const response = await api.tasks.createTask(taskData);
        return { success: true, data: response.task };
      },
      {
        showSuccessToast: true,
        successMessage: 'Task created successfully!',
      }
    );
  }, [storeState]);

  const updateTask = React.useCallback(async (taskId: string, updates: UpdateTaskRequest) => {
    return storeState.executeWithOptimism(
      taskId,
      updates, // Use updates as optimistic data
      async () => {
        const task = await api.tasks.updateTask(taskId, updates);
        return { success: true, data: task };
      },
      {
        showSuccessToast: true,
        successMessage: 'Task updated successfully!',
      }
    );
  }, [storeState]);

  const deleteTask = React.useCallback(async (taskId: string) => {
    return storeState.executeWithOptimism(
      taskId,
      { id: taskId, deleted: true }, // Mark as deleted optimistically
      async () => {
        await api.tasks.deleteTask(taskId);
        return { success: true, data: true };
      },
      {
        showSuccessToast: true,
        successMessage: 'Task deleted successfully!',
      }
    );
  }, [storeState]);

  const bulkUpdateTasks = React.useCallback(async (taskIds: string[], updates: UpdateTaskRequest) => {
    const optimisticUpdates = taskIds.map(id => ({ entityId: id, optimisticData: updates }));

    return storeState.executeBatchWithOptimism(
      optimisticUpdates,
      async () => {
        const tasks = await api.tasks.bulkUpdateTasks(taskIds, updates);
        return { success: true, data: tasks };
      },
      {
        showProgressToast: true,
        showSuccessToast: true,
      }
    );
  }, [storeState]);

  return {
    fetchTasks,
    createTask,
    updateTask,
    deleteTask,
    bulkUpdateTasks,
    assignTask: (taskId: string, assigneeId: string) => 
      updateTask(taskId, { assignee_id: assigneeId }),
    updateTaskStatus: (taskId: string, status: string) => 
      updateTask(taskId, { status: status as any }),
    blockTask: (taskId: string, reason: string) => 
      updateTask(taskId, { blocked: true, blocked_reason: reason }),
    unblockTask: (taskId: string) => 
      updateTask(taskId, { blocked: false, blocked_reason: undefined }),
  };
};

export const useApiUsers = () => {
  const storeState = useStoreState({
    enableOptimisticUpdates: true,
    enableErrorToasts: true,
    enableSuccessToasts: true,
  });

  const fetchUsers = React.useCallback(async (params?: UserListParams) => {
    return storeState.executeWithOptimism(
      'fetch-users',
      [],
      async () => {
        const response = await api.users.getUsers(params);
        return { success: true, data: response.data };
      },
      { showSuccessToast: false }
    );
  }, [storeState]);

  const createUser = React.useCallback(async (userData: CreateUserRequest) => {
    const tempId = `temp-${Date.now()}`;
    const optimisticUser = {
      id: tempId,
      ...userData,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      is_active: true,
    };

    return storeState.executeWithOptimism(
      tempId,
      optimisticUser,
      async () => {
        const user = await api.users.createUser(userData);
        return { success: true, data: user };
      },
      {
        showSuccessToast: true,
        successMessage: 'User created successfully!',
      }
    );
  }, [storeState]);

  const updateUser = React.useCallback(async (userId: string, updates: UpdateUserRequest) => {
    return storeState.executeWithOptimism(
      userId,
      updates,
      async () => {
        const user = await api.users.updateUser(userId, updates);
        return { success: true, data: user };
      },
      {
        showSuccessToast: true,
        successMessage: 'User updated successfully!',
      }
    );
  }, [storeState]);

  const deleteUser = React.useCallback(async (userId: string) => {
    return storeState.executeWithOptimism(
      userId,
      { id: userId, deleted: true },
      async () => {
        await api.users.deleteUser(userId);
        return { success: true, data: true };
      },
      {
        showSuccessToast: true,
        successMessage: 'User deleted successfully!',
      }
    );
  }, [storeState]);

  return {
    fetchUsers,
    createUser,
    updateUser,
    deleteUser,
    getCurrentUser: api.users.getCurrentUserProfile,
    updateCurrentUser: api.users.updateCurrentUser,
    getUsersByRole: api.users.getUsersByRole,
    searchUsers: api.users.searchUsers,
  };
};

export const useApiReports = () => {
  const storeState = useStoreState({
    enableOptimisticUpdates: true,
    enableErrorToasts: true,
    enableSuccessToasts: true,
  });

  const fetchReports = React.useCallback(async (params?: DailyReportListParams) => {
    return storeState.executeWithOptimism(
      'fetch-reports',
      [],
      async () => {
        const response = await api.dailyReports.getReports(params);
        return { success: true, data: response.reports };
      },
      { showSuccessToast: false }
    );
  }, [storeState]);

  const createReport = React.useCallback(async (reportData: CreateDailyReportRequest) => {
    const tempId = `temp-${Date.now()}`;
    const optimisticReport = {
      id: tempId,
      ...reportData,
      user_id: 'current-user', // Will be set by backend
      linked_commit_ids: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    return storeState.executeWithOptimism(
      tempId,
      optimisticReport,
      async () => {
        const report = await api.dailyReports.createReport(reportData);
        return { success: true, data: report };
      },
      {
        showSuccessToast: true,
        successMessage: 'Daily report submitted successfully!',
      }
    );
  }, [storeState]);

  const updateReport = React.useCallback(async (reportId: string, updates: UpdateDailyReportRequest) => {
    return storeState.executeWithOptimism(
      reportId,
      updates,
      async () => {
        const report = await api.dailyReports.updateReport(reportId, updates);
        return { success: true, data: report };
      },
      {
        showSuccessToast: true,
        successMessage: 'Report updated successfully!',
      }
    );
  }, [storeState]);

  const deleteReport = React.useCallback(async (reportId: string) => {
    return storeState.executeWithOptimism(
      reportId,
      { id: reportId, deleted: true },
      async () => {
        await api.dailyReports.deleteReport(reportId);
        return { success: true, data: true };
      },
      {
        showSuccessToast: true,
        successMessage: 'Report deleted successfully!',
      }
    );
  }, [storeState]);

  return {
    fetchReports,
    createReport,
    updateReport,
    deleteReport,
    getMyReports: api.dailyReports.getMyReports,
    getReportByDate: api.dailyReports.getReportByDate,
    getReportsByUser: api.dailyReports.getReportsByUser,
    getReportsByDateRange: api.dailyReports.getReportsByDateRange,
  };
};

// ========== SYSTEM HOOKS ==========

export const useApiHealth = () => {
  const [health, setHealth] = React.useState<any>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const checkHealth = React.useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const healthData = await api.system.getHealthCheck();
      setHealth(healthData);
    } catch (err: any) {
      setError(err.message || 'Health check failed');
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    checkHealth();
    
    // Check health every 30 seconds
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  return {
    health,
    loading,
    error,
    checkHealth,
    isHealthy: health?.status === 'healthy',
  };
};

// ========== SEARCH HOOKS ==========

export const useApiSearch = () => {
  const [results, setResults] = React.useState<any[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const search = React.useCallback(async (query: string, params?: { types?: string[]; limit?: number }) => {
    if (!query.trim()) {
      setResults([]);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const searchResults = await api.search.globalSearch(query, params);
      setResults(searchResults);
    } catch (err: any) {
      setError(err.message || 'Search failed');
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const searchTasks = React.useCallback(async (query: string, params?: Partial<TaskListParams>) => {
    try {
      return await api.search.searchTasks(query, params);
    } catch (err: any) {
      toast({
        title: 'Search Failed',
        description: err.message || 'Task search failed',
        variant: 'destructive',
      });
      return [];
    }
  }, []);

  const searchUsers = React.useCallback(async (query: string, params?: Partial<UserListParams>) => {
    try {
      return await api.search.searchUsers(query, params);
    } catch (err: any) {
      toast({
        title: 'Search Failed',
        description: err.message || 'User search failed',
        variant: 'destructive',
      });
      return [];
    }
  }, []);

  return {
    results,
    loading,
    error,
    search,
    searchTasks,
    searchUsers,
  };
};

// ========== COMBINED API HOOK ==========

export const useApi = () => {
  const auth = useAuth();
  const tasks = useApiTasks();
  const users = useApiUsers();
  const reports = useApiReports();
  const health = useApiHealth();
  const search = useApiSearch();

  return {
    auth,
    tasks,
    users,
    reports,
    health,
    search,
    
    // Direct API access for advanced usage
    api,
    tokenManager,
  };
};