/**
 * Store module exports - Normalized data stores for GolfDaddy
 */

// Core stores
export { useTaskStore } from './taskStore';
export { useUserStore } from './userStore';

// Store provider and context
export { StoreProvider, useStoreContext, useAppStore } from './StoreProvider';

// Advanced selectors
export {
  useTaskSelectors,
  useUserSelectors,
  useCombinedSelectors,
  useDashboardSelectors,
} from './selectors';

// Store utilities
export * from './utils/normalization';
export * from './utils/performance';
export * from './utils/sync';

// Store types
export type {
  NormalizedState,
  CacheConfig,
  StoreOperationResult,
  QueryState,
} from './types';

// Re-export entity types for convenience
export type { Task, TaskStatus, CreateTaskPayload, CreateTaskResponse } from '@/types/entities';
export type { UserResponse, UserRole } from '@/types/user';

// Store event constants
export { STORE_EVENTS, storeEvents } from './utils/sync';

// Performance monitoring
export { StorePerformanceMonitor } from './utils/performance';
export { OptimisticUpdateManager } from './utils/sync';