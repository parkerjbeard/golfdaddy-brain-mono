/**
 * Central store provider with initialization and global state management
 */

import React, { createContext, useContext, useEffect, ReactNode } from 'react';
import { useStoreSynchronization, useRealTimeSync, useDataConsistencyCheck } from './utils/sync';
import { useCacheWarming } from './utils/performance';
import { useTaskStore } from './taskStore';
import { useUserStore } from './userStore';
import { useAuth } from '@/hooks/useAuth';

interface StoreContextValue {
  isInitialized: boolean;
  initializeStores: () => Promise<void>;
  refreshAllData: () => Promise<void>;
  clearAllCaches: () => void;
}

const StoreContext = createContext<StoreContextValue | null>(null);

interface StoreProviderProps {
  children: ReactNode;
  enableRealTimeSync?: boolean;
  enableDataConsistencyCheck?: boolean;
  realTimeSyncInterval?: number;
}

export const StoreProvider: React.FC<StoreProviderProps> = ({
  children,
  enableRealTimeSync = true,
  enableDataConsistencyCheck = true,
  realTimeSyncInterval = 30000,
}) => {
  const [isInitialized, setIsInitialized] = React.useState(false);
  const { user } = useAuth();
  
  const taskStore = useTaskStore();
  const userStore = useUserStore();
  
  // Initialize sync utilities
  useStoreSynchronization();
  
  const { manualSync } = useRealTimeSync({
    enableUserSync: true,
    enableTaskSync: true,
    pollInterval: enableRealTimeSync ? realTimeSyncInterval : 0,
  });

  const { checkConsistency, fixConsistencyIssues } = useDataConsistencyCheck();
  const { warmCache } = useCacheWarming();

  // Initialize stores with essential data
  const initializeStores = React.useCallback(async () => {
    if (!user) return;

    try {
      // Warm cache with essential data in priority order
      await warmCache([
        // High priority: current user and their immediate data
        () => userStore.fetchCurrentUserProfile(),
        () => userStore.fetchUsers({ limit: 50 }), // Fetch initial user set
        
        // Medium priority: user's tasks and team data
        () => taskStore.fetchTasks({ assignee: user.id, limit: 20 }),
        () => taskStore.fetchTasks({ limit: 50 }), // Fetch initial task set
        
        // Low priority: additional data for dashboard
        () => userStore.fetchUsersByRole(user.role),
        () => taskStore.fetchTasks({ status: 'IN_PROGRESS', limit: 100 }),
      ]);

      // Check data consistency after initial load
      if (enableDataConsistencyCheck) {
        const consistencyResult = checkConsistency();
        if (!consistencyResult.isConsistent) {
          console.warn('Data consistency issues detected:', consistencyResult.issues);
          await fixConsistencyIssues();
        }
      }

      setIsInitialized(true);
    } catch (error) {
      console.error('Failed to initialize stores:', error);
      // Still mark as initialized to allow app to function
      setIsInitialized(true);
    }
  }, [user, userStore, taskStore, warmCache, checkConsistency, fixConsistencyIssues, enableDataConsistencyCheck]);

  // Refresh all data
  const refreshAllData = React.useCallback(async () => {
    try {
      await Promise.allSettled([
        userStore.fetchUsers({ force: true }),
        taskStore.fetchTasks({ force: true }),
      ]);
    } catch (error) {
      console.error('Failed to refresh data:', error);
    }
  }, [userStore, taskStore]);

  // Clear all caches
  const clearAllCaches = React.useCallback(() => {
    userStore.invalidateCache();
    taskStore.invalidateCache();
  }, [userStore, taskStore]);

  // Initialize stores when user is available
  useEffect(() => {
    if (user && !isInitialized) {
      initializeStores();
    }
  }, [user, isInitialized, initializeStores]);

  // Reset initialization when user changes
  useEffect(() => {
    setIsInitialized(false);
  }, [user?.id]);

  // Periodic data consistency check
  useEffect(() => {
    if (!enableDataConsistencyCheck || !isInitialized) return;

    const interval = setInterval(async () => {
      const consistencyResult = checkConsistency();
      if (!consistencyResult.isConsistent) {
        console.warn('Periodic consistency check failed:', consistencyResult.issues);
        await fixConsistencyIssues();
      }
    }, 5 * 60 * 1000); // Check every 5 minutes

    return () => clearInterval(interval);
  }, [enableDataConsistencyCheck, isInitialized, checkConsistency, fixConsistencyIssues]);

  const contextValue: StoreContextValue = {
    isInitialized,
    initializeStores,
    refreshAllData,
    clearAllCaches,
  };

  return (
    <StoreContext.Provider value={contextValue}>
      {children}
    </StoreContext.Provider>
  );
};

// Hook to access store context
export const useStoreContext = () => {
  const context = useContext(StoreContext);
  if (!context) {
    throw new Error('useStoreContext must be used within a StoreProvider');
  }
  return context;
};

// Enhanced hook that combines all store functionality
export const useAppStore = () => {
  const storeContext = useStoreContext();
  const taskStore = useTaskStore();
  const userStore = useUserStore();

  // Store status information
  const storeStatus = React.useMemo(() => {
    const taskCacheStatus = taskStore.getCacheStatus();
    const userCacheStatus = userStore.getCacheStatus();

    return {
      isLoading: taskStore.tasks.loading || userStore.users.loading,
      hasErrors: !!(taskStore.tasks.error || userStore.users.error),
      errors: [taskStore.tasks.error, userStore.users.error].filter(Boolean),
      cacheStatus: {
        tasks: taskCacheStatus,
        users: userCacheStatus,
      },
      dataFreshness: {
        tasks: taskCacheStatus.isValid ? 'fresh' : 'stale',
        users: userCacheStatus.isValid ? 'fresh' : 'stale',
      },
    };
  }, [
    taskStore.tasks.loading,
    taskStore.tasks.error,
    userStore.users.loading,
    userStore.users.error,
    taskStore.getCacheStatus,
    userStore.getCacheStatus,
  ]);

  // Combined store actions
  const actions = React.useMemo(() => ({
    // Task actions
    tasks: {
      fetch: taskStore.fetchTasks,
      fetchById: taskStore.fetchTask,
      create: taskStore.createTask,
      update: taskStore.updateTask,
      delete: taskStore.deleteTask,
      updateStatus: taskStore.updateTaskStatus,
      assign: taskStore.assignTask,
      bulkUpdate: taskStore.bulkUpdateTasks,
      bulkDelete: taskStore.bulkDeleteTasks,
    },
    
    // User actions
    users: {
      fetch: userStore.fetchUsers,
      fetchById: userStore.fetchUser,
      create: userStore.createUser,
      update: userStore.updateUser,
      delete: userStore.deleteUser,
      updateRole: userStore.updateUserRole,
      addToTeam: userStore.addUserToTeam,
      removeFromTeam: userStore.removeUserFromTeam,
    },

    // Global actions
    global: {
      initialize: storeContext.initializeStores,
      refresh: storeContext.refreshAllData,
      clearCaches: storeContext.clearAllCaches,
    },
  }), [taskStore, userStore, storeContext]);

  // Combined selectors
  const selectors = React.useMemo(() => ({
    // Task selectors
    tasks: {
      getById: taskStore.getTaskById,
      getByStatus: taskStore.getTasksByStatus,
      getByAssignee: taskStore.getTasksByAssignee,
      getByPriority: taskStore.getTasksByPriority,
      getOverdue: taskStore.getOverdueTasks,
      getDueToday: taskStore.getTasksDueToday,
      getDueThisWeek: taskStore.getTasksDueThisWeek,
      getFiltered: taskStore.getFilteredTasks,
      getStats: taskStore.getTaskStats,
      getUserStats: taskStore.getUserTaskStats,
    },
    
    // User selectors
    users: {
      getById: userStore.getUserById,
      getByRole: userStore.getUsersByRole,
      getByTeam: userStore.getUsersByTeam,
      getTeamMembers: userStore.getTeamMembers,
      getFiltered: userStore.getFilteredUsers,
      getStats: userStore.getUserStats,
    },
  }), [taskStore, userStore]);

  return {
    // Context
    ...storeContext,
    
    // Store status
    status: storeStatus,
    
    // Actions
    actions,
    
    // Selectors
    selectors,
    
    // Store instances (for advanced usage)
    stores: {
      task: taskStore,
      user: userStore,
    },
  };
};