/**
 * Store synchronization utilities for cross-store data consistency
 */

import { useEffect, useCallback, useRef } from 'react';
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
  CACHE_INVALIDATED: 'cache:invalidated',
} as const;

// Hook for cross-store synchronization
export const useStoreSynchronization = () => {
  const userStore = useUserStore();

  useEffect(() => {
    // Cache invalidation should clear related caches
    const unsubCacheInvalidated = storeEvents.on(STORE_EVENTS.CACHE_INVALIDATED, (storeType: 'users' | 'all') => {
      switch (storeType) {
        case 'users':
          userStore.invalidateCache();
          break;
        case 'all':
          userStore.invalidateCache();
          break;
      }
    });

    return () => {
      unsubCacheInvalidated();
    };
  }, [userStore]);
};

// Real-time data synchronization hook
export const useRealTimeSync = (options: {
  enableUserSync?: boolean;
  pollInterval?: number;
} = {}) => {
  const {
    enableUserSync = true,
    pollInterval = 30000, // 30 seconds
  } = options;

  const userStore = useUserStore();
  const intervalRef = useRef<NodeJS.Timeout>();

  const syncData = useCallback(async () => {
    try {
      // Check if we have stale data and refresh if needed
      if (enableUserSync && !userStore.getCacheStatus().isValid) {
        await userStore.fetchUsers(true);
      }
    } catch (error) {
      console.warn('Real-time sync failed:', error);
    }
  }, [enableUserSync, userStore]);

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
  const userStore = useUserStore();

  const checkConsistency = useCallback(() => {
    const issues: string[] = [];

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
  }, [userStore]);

  const fixConsistencyIssues = useCallback(async () => {
    const { issues } = checkConsistency();
    const fixedCount = 0;

    // For now, just log issues as user duplicate IDs would need manual resolution
    for (const issue of issues) {
      console.warn('Consistency issue that needs manual resolution:', issue);
    }

    return { fixedCount };
  }, [checkConsistency]);

  return {
    checkConsistency,
    fixConsistencyIssues,
  };
};
