/**
 * Central store provider with initialization and global state management
 */

import React, { createContext, useContext, useEffect, ReactNode } from 'react';
import { useStoreSynchronization, useRealTimeSync, useDataConsistencyCheck } from './utils/sync';
import { useCacheWarming } from './utils/performance';
import { useUserStore } from './userStore';
import { useAuth } from '@/contexts/AuthContext';

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
  
  const userStore = useUserStore();
  
  // Initialize sync utilities
  useStoreSynchronization();
  
  const { manualSync } = useRealTimeSync({
    enableUserSync: true,
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
        () => userStore.fetchUsers(), // Fetch initial user set
        
        // Low priority: additional data for dashboard
        () => Promise.resolve(userStore.getUsersByRole(user.user_metadata?.role || 'user')), // This is a selector, not an async function
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
  }, [user, userStore, warmCache, checkConsistency, fixConsistencyIssues, enableDataConsistencyCheck]);

  // Refresh all data
  const refreshAllData = React.useCallback(async () => {
    try {
      await Promise.allSettled([
        userStore.fetchUsers(true), // force refresh
      ]);
    } catch (error) {
      console.error('Failed to refresh data:', error);
    }
  }, [userStore]);

  // Clear all caches
  const clearAllCaches = React.useCallback(() => {
    userStore.invalidateCache();
  }, [userStore]);

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
  const userStore = useUserStore();

  // Store status information
  const storeStatus = React.useMemo(() => {
    const userCacheStatus = userStore.getCacheStatus();

    return {
      isLoading: userStore.users.loading.fetching,
      hasErrors: !!(userStore.users.errors.fetch),
      errors: [userStore.users.errors.fetch].filter(Boolean),
      cacheStatus: {
        users: userCacheStatus,
      },
      dataFreshness: {
        users: userCacheStatus.isValid ? 'fresh' : 'stale',
      },
    };
  }, [
    userStore.users.loading.fetching,
    userStore.users.errors.fetch,
    userStore.getCacheStatus,
  ]);

  // Combined store actions
  const actions = React.useMemo(() => ({
    // User actions
    users: {
      fetch: userStore.fetchUsers,
      fetchById: userStore.fetchUser,
      fetchCurrentProfile: userStore.fetchCurrentUserProfile,
      create: userStore.createUser,
      update: userStore.updateUser,
      delete: userStore.deleteUser,
    },

    // Global actions
    global: {
      initialize: storeContext.initializeStores,
      refresh: storeContext.refreshAllData,
      clearCaches: storeContext.clearAllCaches,
    },
  }), [userStore, storeContext]);

  // Combined selectors
  const selectors = React.useMemo(() => ({
    // User selectors
    users: {
      getById: userStore.getUserById,
      getByRole: userStore.getUsersByRole,
      getByTeam: userStore.getUsersByTeam,
      getFiltered: userStore.getFilteredUsers,
      getSearchResults: userStore.getSearchResults,
    },
  }), [userStore]);

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
      user: userStore,
    },
  };
};