/**
 * Optimistic updates management with automatic rollback and conflict resolution
 */

import React from 'react';
import { OptimisticUpdate, StoreError } from '../types';
import { storeEvents } from './sync';

export interface OptimisticUpdateConfig {
  timeout: number; // Auto-rollback timeout in milliseconds
  enableConflictResolution: boolean;
  maxConcurrentUpdates: number;
}

export const defaultOptimisticConfig: OptimisticUpdateConfig = {
  timeout: 10000, // 10 seconds
  enableConflictResolution: true,
  maxConcurrentUpdates: 50,
};

export class OptimisticUpdateManager<T> {
  private pendingUpdates: Map<string, OptimisticUpdate<T>> = new Map();
  private timeouts: Map<string, NodeJS.Timeout> = new Map();
  private config: OptimisticUpdateConfig;
  private entityType: string;

  constructor(entityType: string, config: OptimisticUpdateConfig = defaultOptimisticConfig) {
    this.entityType = entityType;
    this.config = config;
  }

  // Add optimistic update with automatic rollback
  addUpdate(
    id: string,
    type: OptimisticUpdate<T>['type'],
    optimisticData: T,
    originalData?: T,
    onRollback?: (id: string) => void
  ): void {
    // Check concurrent update limit
    if (this.pendingUpdates.size >= this.config.maxConcurrentUpdates) {
      console.warn(`OptimisticUpdateManager: Max concurrent updates (${this.config.maxConcurrentUpdates}) reached`);
      return;
    }

    // Cancel existing timeout if update exists
    this.cancelTimeout(id);

    const update: OptimisticUpdate<T> = {
      id,
      type,
      optimisticData,
      originalData,
      timestamp: Date.now(),
      confirmed: false,
    };

    this.pendingUpdates.set(id, update);

    // Set auto-rollback timeout
    const timeout = setTimeout(() => {
      console.warn(`OptimisticUpdateManager: Auto-rolling back update ${id} after timeout`);
      this.rollback(id, onRollback);
      storeEvents.emit('optimistic-update-timeout', { entityType: this.entityType, id });
    }, this.config.timeout);

    this.timeouts.set(id, timeout);

    // Emit event for tracking
    storeEvents.emit('optimistic-update-added', { entityType: this.entityType, id, type });
  }

  // Confirm optimistic update (operation succeeded)
  confirm(id: string): boolean {
    const update = this.pendingUpdates.get(id);
    if (!update) return false;

    this.cancelTimeout(id);
    this.pendingUpdates.delete(id);

    storeEvents.emit('optimistic-update-confirmed', { entityType: this.entityType, id });
    return true;
  }

  // Rollback optimistic update (operation failed)
  rollback(id: string, onRollback?: (id: string) => void): T | null {
    const update = this.pendingUpdates.get(id);
    if (!update) return null;

    this.cancelTimeout(id);
    this.pendingUpdates.delete(id);

    // Execute rollback callback
    if (onRollback) {
      onRollback(id);
    }

    storeEvents.emit('optimistic-update-rolled-back', { entityType: this.entityType, id });
    return update.originalData || null;
  }

  // Get pending update
  getUpdate(id: string): OptimisticUpdate<T> | null {
    return this.pendingUpdates.get(id) || null;
  }

  // Check if entity has pending updates
  hasPendingUpdate(id: string): boolean {
    return this.pendingUpdates.has(id);
  }

  // Get all pending updates
  getAllPendingUpdates(): OptimisticUpdate<T>[] {
    return Array.from(this.pendingUpdates.values());
  }

  // Get pending update IDs
  getPendingUpdateIds(): string[] {
    return Array.from(this.pendingUpdates.keys());
  }

  // Rollback all pending updates
  rollbackAll(onRollback?: (id: string) => void): T[] {
    const rolledBackData: T[] = [];
    const updates = Array.from(this.pendingUpdates.values());

    updates.forEach(update => {
      const data = this.rollback(update.id, onRollback);
      if (data) rolledBackData.push(data);
    });

    return rolledBackData;
  }

  // Clean up expired updates
  cleanup(): void {
    const now = Date.now();
    const expiredIds: string[] = [];

    this.pendingUpdates.forEach((update, id) => {
      if (now - update.timestamp > this.config.timeout) {
        expiredIds.push(id);
      }
    });

    expiredIds.forEach(id => {
      console.warn(`OptimisticUpdateManager: Cleaning up expired update ${id}`);
      this.rollback(id);
    });
  }

  // Get statistics
  getStats(): {
    pending: number;
    oldestUpdateAge: number;
    averageUpdateAge: number;
  } {
    const now = Date.now();
    const updates = Array.from(this.pendingUpdates.values());
    
    if (updates.length === 0) {
      return { pending: 0, oldestUpdateAge: 0, averageUpdateAge: 0 };
    }

    const ages = updates.map(update => now - update.timestamp);
    const averageAge = ages.reduce((sum, age) => sum + age, 0) / ages.length;
    const oldestAge = Math.max(...ages);

    return {
      pending: updates.length,
      oldestUpdateAge: oldestAge,
      averageUpdateAge: averageAge,
    };
  }

  // Destroy manager and clean up
  destroy(): void {
    this.timeouts.forEach(timeout => clearTimeout(timeout));
    this.timeouts.clear();
    this.pendingUpdates.clear();
  }

  private cancelTimeout(id: string): void {
    const timeout = this.timeouts.get(id);
    if (timeout) {
      clearTimeout(timeout);
      this.timeouts.delete(id);
    }
  }
}

// Conflict resolution strategies
export enum ConflictResolutionStrategy {
  CLIENT_WINS = 'client_wins',
  SERVER_WINS = 'server_wins',
  MERGE = 'merge',
  PROMPT_USER = 'prompt_user',
}

export interface ConflictResolution<T> {
  strategy: ConflictResolutionStrategy;
  resolve: (clientData: T, serverData: T) => T;
}

// Default conflict resolution
export const createDefaultConflictResolution = <T>(): ConflictResolution<T> => ({
  strategy: ConflictResolutionStrategy.SERVER_WINS,
  resolve: (clientData: T, serverData: T) => serverData,
});

// Merge conflict resolution for objects
export const createMergeConflictResolution = <T extends Record<string, any>>(): ConflictResolution<T> => ({
  strategy: ConflictResolutionStrategy.MERGE,
  resolve: (clientData: T, serverData: T) => ({
    ...clientData,
    ...serverData,
    // Prefer server data for critical fields
    id: serverData.id,
    created_at: serverData.created_at,
    updated_at: serverData.updated_at,
  }),
});

// Optimistic update wrapper for store operations
export const withOptimisticUpdate = async <T, R>(
  manager: OptimisticUpdateManager<T>,
  entityId: string,
  optimisticData: T,
  operation: () => Promise<R>,
  originalData?: T,
  onRollback?: (id: string) => void
): Promise<R> => {
  // Add optimistic update
  manager.addUpdate(entityId, 'update', optimisticData, originalData, onRollback);

  try {
    // Execute operation
    const result = await operation();
    
    // Confirm optimistic update on success
    manager.confirm(entityId);
    
    return result;
  } catch (error) {
    // Rollback on failure
    manager.rollback(entityId, onRollback);
    throw error;
  }
};

// Batch optimistic updates
export const withBatchOptimisticUpdates = async <T, R>(
  manager: OptimisticUpdateManager<T>,
  updates: Array<{
    entityId: string;
    optimisticData: T;
    originalData?: T;
  }>,
  operation: () => Promise<R>,
  onRollback?: (ids: string[]) => void
): Promise<R> => {
  const entityIds = updates.map(update => update.entityId);

  // Add all optimistic updates
  updates.forEach(({ entityId, optimisticData, originalData }) => {
    manager.addUpdate(entityId, 'update', optimisticData, originalData);
  });

  try {
    // Execute operation
    const result = await operation();
    
    // Confirm all optimistic updates on success
    entityIds.forEach(id => manager.confirm(id));
    
    return result;
  } catch (error) {
    // Rollback all on failure
    entityIds.forEach(id => manager.rollback(id));
    
    if (onRollback) {
      onRollback(entityIds);
    }
    
    throw error;
  }
};

// React hook for optimistic updates
export const useOptimisticManager = <T>(entityType: string, config?: Partial<OptimisticUpdateConfig>) => {
  const manager = new OptimisticUpdateManager<T>(entityType, { ...defaultOptimisticConfig, ...config });

  // Cleanup on unmount
  React.useEffect(() => {
    return () => manager.destroy();
  }, [manager]);

  return {
    addUpdate: manager.addUpdate.bind(manager),
    confirm: manager.confirm.bind(manager),
    rollback: manager.rollback.bind(manager),
    hasPendingUpdate: manager.hasPendingUpdate.bind(manager),
    getUpdate: manager.getUpdate.bind(manager),
    getAllPendingUpdates: manager.getAllPendingUpdates.bind(manager),
    rollbackAll: manager.rollbackAll.bind(manager),
    getStats: manager.getStats.bind(manager),
    withOptimisticUpdate: (
      entityId: string,
      optimisticData: T,
      operation: () => Promise<any>,
      originalData?: T,
      onRollback?: (id: string) => void
    ) => withOptimisticUpdate(manager, entityId, optimisticData, operation, originalData, onRollback),
  };
};