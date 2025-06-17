/**
 * Types for normalized state management
 */

// Loading states for different operations
export interface LoadingStates {
  fetching: boolean;
  creating: boolean;
  updating: Record<string, boolean>; // entityId -> isUpdating
  deleting: Record<string, boolean>; // entityId -> isDeleting
  bulkOperations: boolean;
}

// Error states for different operations
export interface ErrorStates {
  fetch: string | null;
  create: string | null;
  update: Record<string, string>; // entityId -> error message
  delete: Record<string, string>; // entityId -> error message
  bulkOperations: string | null;
}

// Optimistic update tracking
export interface OptimisticUpdate<T> {
  id: string;
  type: 'create' | 'update' | 'delete';
  originalData?: T;
  optimisticData: T;
  timestamp: number;
  confirmed: boolean;
}

// Normalized store structure
export interface NormalizedState<T> {
  byId: Record<string, T>;
  allIds: string[];
  loading: LoadingStates;
  errors: ErrorStates;
  lastFetch: number | null;
  hasMore: boolean;
  optimisticUpdates: Record<string, OptimisticUpdate<T>>;
}

// Cache configuration
export interface CacheConfig {
  ttl: number; // Time to live in milliseconds
  maxAge: number; // Maximum age before forced refresh
  maxSize: number; // Maximum number of items to cache
}

// Store metadata for performance tracking
export interface StoreMetadata {
  lastUpdate: number;
  version: number;
  isDirty: boolean;
  fetchCount: number;
}

// Query state for pagination and filtering
export interface QueryState {
  page: number;
  limit: number;
  filters: Record<string, any>;
  sortBy: string | null;
  sortOrder: 'asc' | 'desc';
}

// Entity relationships for normalization
export interface EntityRelationships {
  [entityType: string]: {
    [relationKey: string]: string | string[];
  };
}

// Enhanced store operation result
export interface StoreOperationResult<T> {
  success: boolean;
  data?: T;
  error?: StoreError;
  cached?: boolean;
  optimistic?: boolean;
  retryable?: boolean;
}

// Comprehensive error information
export interface StoreError {
  message: string;
  code?: string;
  statusCode?: number;
  timestamp: number;
  operation: string;
  entityId?: string;
  retryable: boolean;
  context?: Record<string, any>;
}

// Operation context for tracking and debugging
export interface OperationContext {
  operationId: string;
  entityType: string;
  operation: 'fetch' | 'create' | 'update' | 'delete' | 'bulkUpdate' | 'bulkDelete';
  entityId?: string;
  startTime: number;
  endTime?: number;
  metadata?: Record<string, any>;
}

// Store health monitoring
export interface StoreHealth {
  isHealthy: boolean;
  errorRate: number;
  averageResponseTime: number;
  lastError?: StoreError;
  uptime: number;
}

// Retry configuration
export interface RetryConfig {
  maxAttempts: number;
  backoffMs: number;
  backoffMultiplier: number;
  retryableErrors: string[];
}