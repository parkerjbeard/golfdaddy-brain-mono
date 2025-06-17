/**
 * Loading state management utilities
 */

import { LoadingStates, ErrorStates, StoreError, OptimisticUpdate, OperationContext, RetryConfig } from '../types';

// Create initial loading states
export const createInitialLoadingStates = (): LoadingStates => ({
  fetching: false,
  creating: false,
  updating: {},
  deleting: {},
  bulkOperations: false,
});

// Create initial error states
export const createInitialErrorStates = (): ErrorStates => ({
  fetch: null,
  create: null,
  update: {},
  delete: {},
  bulkOperations: null,
});

// Loading state updaters
export const setFetchingState = (loading: LoadingStates, isFetching: boolean): LoadingStates => ({
  ...loading,
  fetching: isFetching,
});

export const setCreatingState = (loading: LoadingStates, isCreating: boolean): LoadingStates => ({
  ...loading,
  creating: isCreating,
});

export const setUpdatingState = (loading: LoadingStates, entityId: string, isUpdating: boolean): LoadingStates => ({
  ...loading,
  updating: isUpdating 
    ? { ...loading.updating, [entityId]: true }
    : { ...loading.updating, [entityId]: false },
});

export const setDeletingState = (loading: LoadingStates, entityId: string, isDeleting: boolean): LoadingStates => ({
  ...loading,
  deleting: isDeleting 
    ? { ...loading.deleting, [entityId]: true }
    : { ...loading.deleting, [entityId]: false },
});

export const setBulkOperationsState = (loading: LoadingStates, isBulkOperating: boolean): LoadingStates => ({
  ...loading,
  bulkOperations: isBulkOperating,
});

// Error state updaters
export const setFetchError = (errors: ErrorStates, error: string | null): ErrorStates => ({
  ...errors,
  fetch: error,
});

export const setCreateError = (errors: ErrorStates, error: string | null): ErrorStates => ({
  ...errors,
  create: error,
});

export const setUpdateError = (errors: ErrorStates, entityId: string, error: string | null): ErrorStates => ({
  ...errors,
  update: error 
    ? { ...errors.update, [entityId]: error }
    : { ...errors.update, [entityId]: undefined },
});

export const setDeleteError = (errors: ErrorStates, entityId: string, error: string | null): ErrorStates => ({
  ...errors,
  delete: error 
    ? { ...errors.delete, [entityId]: error }
    : { ...errors.delete, [entityId]: undefined },
});

export const setBulkOperationsError = (errors: ErrorStates, error: string | null): ErrorStates => ({
  ...errors,
  bulkOperations: error,
});

// Clear all errors
export const clearAllErrors = (): ErrorStates => createInitialErrorStates();

// Clear specific entity errors
export const clearEntityErrors = (errors: ErrorStates, entityId: string): ErrorStates => ({
  ...errors,
  update: { ...errors.update, [entityId]: undefined },
  delete: { ...errors.delete, [entityId]: undefined },
});

// Error creation utilities
export const createStoreError = (
  message: string,
  operation: string,
  options: {
    code?: string;
    statusCode?: number;
    entityId?: string;
    retryable?: boolean;
    context?: Record<string, any>;
  } = {}
): StoreError => ({
  message,
  operation,
  timestamp: Date.now(),
  retryable: options.retryable ?? true,
  ...options,
});

// Check if any loading state is active
export const isAnyLoading = (loading: LoadingStates): boolean => {
  return loading.fetching || 
         loading.creating || 
         loading.bulkOperations ||
         Object.values(loading.updating).some(Boolean) ||
         Object.values(loading.deleting).some(Boolean);
};

// Check if specific entity is loading
export const isEntityLoading = (loading: LoadingStates, entityId: string): boolean => {
  return loading.updating[entityId] || loading.deleting[entityId] || false;
};

// Check if any error exists
export const hasAnyError = (errors: ErrorStates): boolean => {
  return !!(errors.fetch || 
           errors.create || 
           errors.bulkOperations ||
           Object.values(errors.update).some(Boolean) ||
           Object.values(errors.delete).some(Boolean));
};

// Get all error messages
export const getAllErrorMessages = (errors: ErrorStates): string[] => {
  const messages: string[] = [];
  
  if (errors.fetch) messages.push(errors.fetch);
  if (errors.create) messages.push(errors.create);
  if (errors.bulkOperations) messages.push(errors.bulkOperations);
  
  Object.values(errors.update).forEach(error => {
    if (error) messages.push(error);
  });
  
  Object.values(errors.delete).forEach(error => {
    if (error) messages.push(error);
  });
  
  return messages;
};

// Operation context utilities
export const createOperationContext = (
  entityType: string,
  operation: OperationContext['operation'],
  entityId?: string,
  metadata?: Record<string, any>
): OperationContext => ({
  operationId: `${entityType}-${operation}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
  entityType,
  operation,
  entityId,
  startTime: Date.now(),
  metadata,
});

export const completeOperationContext = (context: OperationContext): OperationContext => ({
  ...context,
  endTime: Date.now(),
});

// Retry utilities
export const defaultRetryConfig: RetryConfig = {
  maxAttempts: 3,
  backoffMs: 1000,
  backoffMultiplier: 2,
  retryableErrors: ['NetworkError', 'TimeoutError', '500', '502', '503', '504'],
};

export const shouldRetry = (error: StoreError, attempt: number, config: RetryConfig = defaultRetryConfig): boolean => {
  if (attempt >= config.maxAttempts) return false;
  if (!error.retryable) return false;
  
  // Check if error code is in retryable list
  if (error.code && config.retryableErrors.includes(error.code)) return true;
  if (error.statusCode && config.retryableErrors.includes(error.statusCode.toString())) return true;
  
  return false;
};

export const calculateBackoffDelay = (attempt: number, config: RetryConfig = defaultRetryConfig): number => {
  return config.backoffMs * Math.pow(config.backoffMultiplier, attempt - 1);
};

// Optimistic update utilities
export const createOptimisticUpdate = <T>(
  id: string,
  type: OptimisticUpdate<T>['type'],
  optimisticData: T,
  originalData?: T
): OptimisticUpdate<T> => ({
  id,
  type,
  optimisticData,
  originalData,
  timestamp: Date.now(),
  confirmed: false,
});

export const confirmOptimisticUpdate = <T>(update: OptimisticUpdate<T>): OptimisticUpdate<T> => ({
  ...update,
  confirmed: true,
});

// Clean up expired optimistic updates
export const cleanupExpiredOptimisticUpdates = <T>(
  updates: Record<string, OptimisticUpdate<T>>,
  maxAge: number = 30000 // 30 seconds
): Record<string, OptimisticUpdate<T>> => {
  const now = Date.now();
  const cleaned: Record<string, OptimisticUpdate<T>> = {};
  
  Object.entries(updates).forEach(([id, update]) => {
    if (!update.confirmed && (now - update.timestamp) < maxAge) {
      cleaned[id] = update;
    }
  });
  
  return cleaned;
};

// Progress tracking for bulk operations
export interface BulkOperationProgress {
  total: number;
  completed: number;
  failed: number;
  inProgress: number;
  percentage: number;
}

export const createBulkOperationProgress = (total: number): BulkOperationProgress => ({
  total,
  completed: 0,
  failed: 0,
  inProgress: 0,
  percentage: 0,
});

export const updateBulkOperationProgress = (
  progress: BulkOperationProgress,
  completed: number,
  failed: number,
  inProgress: number
): BulkOperationProgress => {
  const total = Math.max(progress.total, completed + failed + inProgress);
  const percentage = total > 0 ? Math.round(((completed + failed) / total) * 100) : 0;
  
  return {
    total,
    completed,
    failed,
    inProgress,
    percentage,
  };
};