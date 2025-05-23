/**
 * Store synchronization utilities for cross-store data consistency
 */

import { useEffect, useCallback, useRef } from 'react';
import { useTaskStore } from '../taskStore';
import { useUserStore } from '../userStore';

// Event system for cross-store communication
class StoreEventEmitter {
  private listeners: Map<string, Set<Function>> = new Map();

  on(event: string, listener: Function) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(listener);

    // Return unsubscribe function
    return () => {
      this.listeners.get(event)?.delete(listener);
    };
  }

  emit(event: string, data?: any) {
    const listeners = this.listeners.get(event);
    if (listeners) {
      listeners.forEach(listener => listener(data));
    }
  }

  off(event: string, listener?: Function) {
    if (listener) {
      this.listeners.get(event)?.delete(listener);
    } else {
      this.listeners.delete(event);
    }
  }

  clear() {
    this.listeners.clear();
  }
}

// Global event emitter instance
export const storeEvents = new StoreEventEmitter();

// Store event types
export const STORE_EVENTS = {
  USER_UPDATED: 'user:updated',
  USER_DELETED: 'user:deleted',
  TASK_UPDATED: 'task:updated',
  TASK_DELETED: 'task:deleted',
  TASK_ASSIGNED: 'task:assigned',
  CACHE_INVALIDATED: 'cache:invalidated',
} as const;

// Hook for cross-store synchronization
export const useStoreSynchronization = () => {
  const taskStore = useTaskStore();
  const userStore = useUserStore();

  useEffect(() => {
    // User updates should refresh task relationships
    const unsubUserUpdated = storeEvents.on(STORE_EVENTS.USER_UPDATED, (userId: string) => {
      // Refresh tasks that might be affected by user changes
      const userTasks = taskStore.getTasksByAssignee(userId);
      if (userTasks.length > 0) {
        taskStore.refreshTaskRelationships();
      }
    });

    // User deletion should handle orphaned tasks
    const unsubUserDeleted = storeEvents.on(STORE_EVENTS.USER_DELETED, (userId: string) => {
      // Find tasks assigned to deleted user and mark as unassigned
      const orphanedTasks = taskStore.getTasksByAssignee(userId);
      orphanedTasks.forEach(task => {
        taskStore.optimisticUpdateTask(task.id, { assignee_id: null });
      });
    });

    // Task assignment changes should update user relationships
    const unsubTaskAssigned = storeEvents.on(STORE_EVENTS.TASK_ASSIGNED, ({ taskId, oldAssigneeId, newAssigneeId }) => {
      // Refresh user relationships if needed
      if (oldAssigneeId) {
        userStore.refreshUserRelationships(oldAssigneeId);
      }
      if (newAssigneeId) {
        userStore.refreshUserRelationships(newAssigneeId);
      }
    });

    // Cache invalidation should clear related caches
    const unsubCacheInvalidated = storeEvents.on(STORE_EVENTS.CACHE_INVALIDATED, (storeType: 'users' | 'tasks' | 'all') => {
      switch (storeType) {
        case 'users':
          userStore.invalidateCache();
          break;
        case 'tasks':
          taskStore.invalidateCache();
          break;
        case 'all':
          userStore.invalidateCache();
          taskStore.invalidateCache();
          break;
      }
    });

    return () => {
      unsubUserUpdated();
      unsubUserDeleted();
      unsubTaskAssigned();
      unsubCacheInvalidated();
    };
  }, [taskStore, userStore]);
};

// Real-time data synchronization hook
export const useRealTimeSync = (options: {
  enableUserSync?: boolean;
  enableTaskSync?: boolean;
  pollInterval?: number;
} = {}) => {
  const {
    enableUserSync = true,
    enableTaskSync = true,
    pollInterval = 30000, // 30 seconds
  } = options;

  const taskStore = useTaskStore();
  const userStore = useUserStore();
  const intervalRef = useRef<NodeJS.Timeout>();

  const syncData = useCallback(async () => {
    try {
      // Check if we have stale data and refresh if needed
      if (enableUserSync && !userStore.getCacheStatus().isValid) {
        await userStore.fetchUsers(true);
      }

      if (enableTaskSync && !taskStore.getCacheStatus().isValid) {
        await taskStore.fetchTasks({ force: true });
      }
    } catch (error) {
      console.warn('Real-time sync failed:', error);
    }
  }, [enableUserSync, enableTaskSync, userStore, taskStore]);

  useEffect(() => {
    if (pollInterval > 0) {
      intervalRef.current = setInterval(syncData, pollInterval);
      
      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
      };
    }
  }, [syncData, pollInterval]);

  // Manual sync function
  const manualSync = useCallback(() => {
    return syncData();
  }, [syncData]);

  return { manualSync };
};

// Optimistic update manager
export class OptimisticUpdateManager {
  private pendingUpdates: Map<string, { originalData: any; revertFn: () => void; timestamp: number }> = new Map();
  private readonly TIMEOUT = 10000; // 10 seconds

  addUpdate(id: string, originalData: any, revertFn: () => void) {
    this.pendingUpdates.set(id, {
      originalData,
      revertFn,
      timestamp: Date.now(),
    });

    // Auto-revert after timeout
    setTimeout(() => {
      if (this.pendingUpdates.has(id)) {
        console.warn(`Optimistic update ${id} timed out, reverting`);
        this.revert(id);
      }
    }, this.TIMEOUT);
  }

  confirm(id: string) {
    this.pendingUpdates.delete(id);
  }

  revert(id: string) {
    const update = this.pendingUpdates.get(id);
    if (update) {
      update.revertFn();
      this.pendingUpdates.delete(id);
    }
  }

  revertAll() {
    for (const [id, update] of this.pendingUpdates.entries()) {
      update.revertFn();
    }
    this.pendingUpdates.clear();
  }

  getPendingUpdates() {
    return Array.from(this.pendingUpdates.keys());
  }

  hasPendingUpdate(id: string) {
    return this.pendingUpdates.has(id);
  }

  clearExpired() {
    const now = Date.now();
    for (const [id, update] of this.pendingUpdates.entries()) {
      if (now - update.timestamp > this.TIMEOUT) {
        this.revert(id);
      }
    }
  }
}

// Hook for optimistic update management
export const useOptimisticUpdates = () => {
  const manager = useRef(new OptimisticUpdateManager());

  // Clean up expired updates periodically
  useEffect(() => {
    const interval = setInterval(() => {
      manager.current.clearExpired();
    }, 5000); // Check every 5 seconds

    return () => clearInterval(interval);
  }, []);

  return {
    addOptimisticUpdate: manager.current.addUpdate.bind(manager.current),
    confirmUpdate: manager.current.confirm.bind(manager.current),
    revertUpdate: manager.current.revert.bind(manager.current),
    revertAllUpdates: manager.current.revertAll.bind(manager.current),
    getPendingUpdates: manager.current.getPendingUpdates.bind(manager.current),
    hasPendingUpdate: manager.current.hasPendingUpdate.bind(manager.current),
  };
};

// Data consistency checker
export const useDataConsistencyCheck = () => {
  const taskStore = useTaskStore();
  const userStore = useUserStore();

  const checkConsistency = useCallback(() => {
    const issues: string[] = [];
    const tasks = taskStore.getFilteredTasks();
    
    // Check for orphaned task assignments
    tasks.forEach(task => {
      if (task.assignee_id && !userStore.getUserById(task.assignee_id)) {
        issues.push(`Task ${task.id} assigned to non-existent user ${task.assignee_id}`);
      }
      
      if (task.responsible_id && !userStore.getUserById(task.responsible_id)) {
        issues.push(`Task ${task.id} has non-existent responsible user ${task.responsible_id}`);
      }
      
      if (task.accountable_id && !userStore.getUserById(task.accountable_id)) {
        issues.push(`Task ${task.id} has non-existent accountable user ${task.accountable_id}`);
      }
    });

    // Check for duplicate task IDs
    const taskIds = tasks.map(t => t.id);
    const uniqueTaskIds = new Set(taskIds);
    if (taskIds.length !== uniqueTaskIds.size) {
      issues.push('Duplicate task IDs detected in store');
    }

    // Check for duplicate user IDs
    const users = userStore.getFilteredUsers();
    const userIds = users.map(u => u.id);
    const uniqueUserIds = new Set(userIds);
    if (userIds.length !== uniqueUserIds.size) {
      issues.push('Duplicate user IDs detected in store');
    }

    return {
      isConsistent: issues.length === 0,
      issues,
    };
  }, [taskStore, userStore]);

  const fixConsistencyIssues = useCallback(async () => {
    const { issues } = checkConsistency();
    let fixedCount = 0;

    for (const issue of issues) {
      try {
        if (issue.includes('assigned to non-existent user')) {
          const taskId = issue.match(/Task (\w+)/)?.[1];
          if (taskId) {
            await taskStore.updateTask(taskId, { assignee_id: null });
            fixedCount++;
          }
        }
        
        if (issue.includes('non-existent responsible user')) {
          const taskId = issue.match(/Task (\w+)/)?.[1];
          if (taskId) {
            await taskStore.updateTask(taskId, { responsible_id: null });
            fixedCount++;
          }
        }
        
        if (issue.includes('non-existent accountable user')) {
          const taskId = issue.match(/Task (\w+)/)?.[1];
          if (taskId) {
            await taskStore.updateTask(taskId, { accountable_id: null });
            fixedCount++;
          }
        }
      } catch (error) {
        console.error('Failed to fix consistency issue:', issue, error);
      }
    }

    return { fixedCount };
  }, [checkConsistency, taskStore]);

  return {
    checkConsistency,
    fixConsistencyIssues,
  };
};