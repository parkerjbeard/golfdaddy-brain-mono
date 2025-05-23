/**
 * Comprehensive hook for managing store states, loading, errors, and optimistic updates
 */

import React from 'react';
import { useAppStore } from '@/store';
import { useErrorHandler } from '@/store/utils/errorHandling';
import { useOptimisticManager } from '@/store/utils/optimistic';
import { LoadingStates, ErrorStates, StoreOperationResult } from '@/store/types';
import { toast } from '@/components/ui/use-toast';

export interface UseStoreStateOptions {
  enableOptimisticUpdates?: boolean;
  enableErrorToasts?: boolean;
  enableSuccessToasts?: boolean;
  autoRetry?: boolean;
  maxRetries?: number;
  silentErrors?: string[];
}

export interface StoreStateResult {
  // Loading states
  isLoading: boolean;
  isFetching: boolean;
  isCreating: boolean;
  isBulkOperating: boolean;
  isEntityLoading: (entityId: string) => boolean;
  isEntityUpdating: (entityId: string) => boolean;
  isEntityDeleting: (entityId: string) => boolean;

  // Error states
  hasErrors: boolean;
  fetchError: string | null;
  createError: string | null;
  bulkError: string | null;
  getEntityError: (entityId: string, operation: 'update' | 'delete') => string | null;
  getAllErrors: () => string[];

  // Optimistic updates
  hasPendingUpdates: boolean;
  isEntityOptimistic: (entityId: string) => boolean;
  getPendingUpdateIds: () => string[];
  rollbackAllUpdates: () => void;
  rollbackEntityUpdate: (entityId: string) => void;

  // Enhanced operations with automatic error handling and optimistic updates
  executeWithOptimism: <T>(
    entityId: string,
    optimisticData: T,
    operation: () => Promise<StoreOperationResult<T>>,
    options?: {
      showSuccessToast?: boolean;
      successMessage?: string;
      showErrorToast?: boolean;
      onSuccess?: (result: T) => void;
      onError?: (error: string) => void;
    }
  ) => Promise<StoreOperationResult<T>>;

  executeBatchWithOptimism: <T>(
    updates: Array<{ entityId: string; optimisticData: T }>,
    operation: () => Promise<StoreOperationResult<T[]>>,
    options?: {
      showProgressToast?: boolean;
      showSuccessToast?: boolean;
      onProgress?: (completed: number, total: number) => void;
      onSuccess?: (results: T[]) => void;
      onError?: (error: string) => void;
    }
  ) => Promise<StoreOperationResult<T[]>>;

  // Utility functions
  clearAllErrors: () => void;
  clearEntityErrors: (entityId: string) => void;
  retryLastOperation: () => Promise<void>;
}

export const useStoreState = (options: UseStoreStateOptions = {}): StoreStateResult => {
  const {
    enableOptimisticUpdates = true,
    enableErrorToasts = true,
    enableSuccessToasts = false,
    autoRetry = false,
    maxRetries = 3,
    silentErrors = [],
  } = options;

  const { status, actions } = useAppStore();
  const { handleError, reportError } = useErrorHandler();
  const optimisticManager = useOptimisticManager('mixed', {
    timeout: 10000,
    enableConflictResolution: true,
    maxConcurrentUpdates: 20,
  });

  // Store last operation for retry functionality
  const [lastOperation, setLastOperation] = React.useState<(() => Promise<any>) | null>(null);

  // Loading state helpers
  const isLoading = React.useMemo(() => {
    return status.isLoading;
  }, [status.isLoading]);

  const isFetching = React.useMemo(() => {
    // This would need to be implemented based on your actual store structure
    return status.isLoading; // Placeholder
  }, [status.isLoading]);

  const isEntityLoading = React.useCallback((entityId: string) => {
    // This would check specific entity loading states from your stores
    return false; // Placeholder
  }, []);

  const isEntityUpdating = React.useCallback((entityId: string) => {
    return false; // Placeholder - implement based on your store structure
  }, []);

  const isEntityDeleting = React.useCallback((entityId: string) => {
    return false; // Placeholder - implement based on your store structure
  }, []);

  // Error state helpers
  const hasErrors = React.useMemo(() => {
    return status.hasErrors;
  }, [status.hasErrors]);

  const getAllErrors = React.useCallback(() => {
    return status.errors;
  }, [status.errors]);

  const getEntityError = React.useCallback((entityId: string, operation: 'update' | 'delete') => {
    // This would get specific entity errors from your stores
    return null; // Placeholder
  }, []);

  // Clear error functions
  const clearAllErrors = React.useCallback(() => {
    // This would clear all errors in your stores
    console.log('Clearing all errors');
  }, []);

  const clearEntityErrors = React.useCallback((entityId: string) => {
    // This would clear specific entity errors
    console.log('Clearing errors for entity:', entityId);
  }, []);

  // Optimistic update helpers
  const hasPendingUpdates = React.useMemo(() => {
    return optimisticManager.getAllPendingUpdates().length > 0;
  }, [optimisticManager]);

  const isEntityOptimistic = React.useCallback((entityId: string) => {
    return optimisticManager.hasPendingUpdate(entityId);
  }, [optimisticManager]);

  const getPendingUpdateIds = React.useCallback(() => {
    return optimisticManager.getAllPendingUpdates().map(update => update.id);
  }, [optimisticManager]);

  const rollbackAllUpdates = React.useCallback(() => {
    optimisticManager.rollbackAll();
    if (enableErrorToasts) {
      toast({
        title: 'Changes Reverted',
        description: 'All pending changes have been rolled back.',
      });
    }
  }, [optimisticManager, enableErrorToasts]);

  const rollbackEntityUpdate = React.useCallback((entityId: string) => {
    optimisticManager.rollback(entityId);
    if (enableErrorToasts) {
      toast({
        title: 'Change Reverted',
        description: 'The pending change has been rolled back.',
      });
    }
  }, [optimisticManager, enableErrorToasts]);

  // Enhanced operation with optimistic updates
  const executeWithOptimism = React.useCallback(async <T,>(
    entityId: string,
    optimisticData: T,
    operation: () => Promise<StoreOperationResult<T>>,
    operationOptions: {
      showSuccessToast?: boolean;
      successMessage?: string;
      showErrorToast?: boolean;
      onSuccess?: (result: T) => void;
      onError?: (error: string) => void;
    } = {}
  ): Promise<StoreOperationResult<T>> => {
    const {
      showSuccessToast = enableSuccessToasts,
      successMessage = 'Operation completed successfully',
      showErrorToast = enableErrorToasts,
      onSuccess,
      onError,
    } = operationOptions;

    // Store operation for retry
    setLastOperation(() => operation);

    try {
      if (enableOptimisticUpdates) {
        return await optimisticManager.withOptimisticUpdate(
          entityId,
          optimisticData,
          operation,
          undefined,
          (id) => {
            if (showErrorToast) {
              toast({
                title: 'Operation Failed',
                description: 'Changes have been reverted.',
                variant: 'destructive',
              });
            }
          }
        );
      } else {
        const result = await operation();
        
        if (result.success && result.data) {
          if (showSuccessToast) {
            toast({
              title: 'Success',
              description: successMessage,
            });
          }
          if (onSuccess) {
            onSuccess(result.data);
          }
        }
        
        return result;
      }
    } catch (error: any) {
      const enhancedError = handleError(error, 'optimistic-operation', entityId);
      
      if (showErrorToast && !silentErrors.includes(enhancedError.code || '')) {
        toast({
          title: 'Operation Failed',
          description: enhancedError.userMessage || enhancedError.message,
          variant: 'destructive',
        });
      }
      
      if (onError) {
        onError(enhancedError.message);
      }
      
      return {
        success: false,
        error: enhancedError,
      };
    }
  }, [
    enableOptimisticUpdates,
    enableSuccessToasts,
    enableErrorToasts,
    silentErrors,
    optimisticManager,
    handleError,
  ]);

  // Batch operations with progress tracking
  const executeBatchWithOptimism = React.useCallback(async <T,>(
    updates: Array<{ entityId: string; optimisticData: T }>,
    operation: () => Promise<StoreOperationResult<T[]>>,
    operationOptions: {
      showProgressToast?: boolean;
      showSuccessToast?: boolean;
      onProgress?: (completed: number, total: number) => void;
      onSuccess?: (results: T[]) => void;
      onError?: (error: string) => void;
    } = {}
  ): Promise<StoreOperationResult<T[]>> => {
    const {
      showProgressToast = false,
      showSuccessToast = enableSuccessToasts,
      onProgress,
      onSuccess,
      onError,
    } = operationOptions;

    // Store operation for retry
    setLastOperation(() => operation);

    let progressToastId: string | undefined;

    try {
      if (showProgressToast) {
        progressToastId = Math.random().toString(36);
        toast({
          title: 'Processing...',
          description: `Processing ${updates.length} items...`,
        });
      }

      if (enableOptimisticUpdates) {
        // Add all optimistic updates
        updates.forEach(({ entityId, optimisticData }) => {
          optimisticManager.addUpdate(entityId, 'update', optimisticData);
        });

        try {
          const result = await operation();
          
          if (result.success) {
            // Confirm all updates
            updates.forEach(({ entityId }) => {
              optimisticManager.confirm(entityId);
            });
            
            if (showSuccessToast) {
              toast({
                title: 'Batch Operation Complete',
                description: `Successfully processed ${updates.length} items.`,
              });
            }
            
            if (onSuccess && result.data) {
              onSuccess(result.data);
            }
          } else {
            // Rollback all updates
            updates.forEach(({ entityId }) => {
              optimisticManager.rollback(entityId);
            });
          }
          
          return result;
        } catch (error) {
          // Rollback all updates on error
          updates.forEach(({ entityId }) => {
            optimisticManager.rollback(entityId);
          });
          throw error;
        }
      } else {
        return await operation();
      }
    } catch (error: any) {
      const enhancedError = handleError(error, 'batch-operation');
      
      if (enableErrorToasts) {
        toast({
          title: 'Batch Operation Failed',
          description: enhancedError.userMessage || enhancedError.message,
          variant: 'destructive',
        });
      }
      
      if (onError) {
        onError(enhancedError.message);
      }
      
      return {
        success: false,
        error: enhancedError,
      };
    }
  }, [
    enableOptimisticUpdates,
    enableSuccessToasts,
    enableErrorToasts,
    optimisticManager,
    handleError,
  ]);

  // Retry last operation
  const retryLastOperation = React.useCallback(async () => {
    if (!lastOperation) {
      toast({
        title: 'No Operation to Retry',
        description: 'There is no previous operation to retry.',
        variant: 'destructive',
      });
      return;
    }

    try {
      await lastOperation();
      toast({
        title: 'Retry Successful',
        description: 'The operation completed successfully.',
      });
    } catch (error: any) {
      const enhancedError = handleError(error, 'retry-operation');
      toast({
        title: 'Retry Failed',
        description: enhancedError.userMessage || enhancedError.message,
        variant: 'destructive',
      });
    }
  }, [lastOperation, handleError]);

  return {
    // Loading states
    isLoading,
    isFetching,
    isCreating: false, // Placeholder
    isBulkOperating: false, // Placeholder
    isEntityLoading,
    isEntityUpdating,
    isEntityDeleting,

    // Error states
    hasErrors,
    fetchError: null, // Placeholder
    createError: null, // Placeholder
    bulkError: null, // Placeholder
    getEntityError,
    getAllErrors,

    // Optimistic updates
    hasPendingUpdates,
    isEntityOptimistic,
    getPendingUpdateIds,
    rollbackAllUpdates,
    rollbackEntityUpdate,

    // Enhanced operations
    executeWithOptimism,
    executeBatchWithOptimism,

    // Utility functions
    clearAllErrors,
    clearEntityErrors,
    retryLastOperation,
  };
};