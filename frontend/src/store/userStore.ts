/**
 * Normalized User Store with caching and optimistic updates
 */

import { create } from 'zustand';
import { devtools, subscribeWithSelector } from 'zustand/middleware';
import { UserResponse, UserRole } from '@/types/user';
import { NormalizedState, CacheConfig, StoreOperationResult } from './types';
import {
  createNormalizedState,
  updateNormalizedState,
  updateEntity,
  removeEntity,
  isCacheValid,
  filterEntities,
  sortEntities,
  denormalizeEntities,
} from './utils/normalization';
import api from '@/services/api';

// Cache configuration for users
const USER_CACHE_CONFIG: CacheConfig = {
  ttl: 5 * 60 * 1000, // 5 minutes
  maxAge: 30 * 60 * 1000, // 30 minutes
  maxSize: 1000, // Maximum 1000 users in cache
};

interface UserStoreState {
  // Normalized user data
  users: NormalizedState<UserResponse>;
  
  // Current user profile cache
  currentUserProfile: UserResponse | null;
  
  // Team relationships
  teamMembers: Record<string, string[]>; // teamId -> userIds
  
  // Search and filtering
  searchQuery: string;
  roleFilter: UserRole | null;
  teamFilter: string | null;
  
  // Actions
  fetchUsers: (force?: boolean) => Promise<StoreOperationResult<UserResponse[]>>;
  fetchUser: (userId: string, force?: boolean) => Promise<StoreOperationResult<UserResponse>>;
  fetchCurrentUserProfile: (force?: boolean) => Promise<StoreOperationResult<UserResponse>>;
  updateUser: (userId: string, updates: Partial<UserResponse>) => Promise<StoreOperationResult<UserResponse>>;
  createUser: (userData: Omit<UserResponse, 'id' | 'created_at' | 'updated_at'>) => Promise<StoreOperationResult<UserResponse>>;
  deleteUser: (userId: string) => Promise<StoreOperationResult<boolean>>;
  
  // Optimistic updates
  optimisticUpdateUser: (userId: string, updates: Partial<UserResponse>) => void;
  revertOptimisticUpdate: (userId: string, originalData: UserResponse) => void;
  
  // Cache management
  invalidateCache: () => void;
  preloadUsers: (userIds: string[]) => Promise<void>;
  
  // Filtering and searching
  setSearchQuery: (query: string) => void;
  setRoleFilter: (role: UserRole | null) => void;
  setTeamFilter: (teamId: string | null) => void;
  clearFilters: () => void;
  
  // Selectors (computed)
  getUserById: (userId: string) => UserResponse | undefined;
  getUsersByRole: (role: UserRole) => UserResponse[];
  getUsersByTeam: (teamId: string) => UserResponse[];
  getTeamMembers: (teamId: string) => UserResponse[];
  getFilteredUsers: () => UserResponse[];
  getSearchResults: () => UserResponse[];
  getUserStats: () => { total: number; byRole: Record<string, number>; byTeam: Record<string, number> };
  isUserCached: (userId: string) => boolean;
  getCacheStatus: () => { size: number; lastFetch: number | null; isValid: boolean };
  teams: Record<string, string[]>;
}

export const useUserStore = create<UserStoreState>()(
  devtools(
    subscribeWithSelector((set, get) => ({
      // Initial state
      users: createNormalizedState<UserResponse>(),
      currentUserProfile: null,
      teamMembers: {},
      teams: {},
      searchQuery: '',
      roleFilter: null,
      teamFilter: null,

      // Fetch all users with caching
      fetchUsers: async (force = false) => {
        const state = get();
        
        // Check cache validity
        if (!force && isCacheValid(state.users.lastFetch, USER_CACHE_CONFIG.ttl)) {
          return {
            success: true,
            data: denormalizeEntities(state.users.byId, state.users.allIds),
            cached: true,
          };
        }

        set(state => ({
          users: { ...state.users, loading: true, error: null },
        }));

        try {
          const users = await api.users.getUsers();

          set(state => ({
            users: updateNormalizedState(state.users, users),
          }));

          return { success: true, data: users };
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to fetch users';
          
          set(state => ({
            users: { ...state.users, loading: false, error: errorMessage },
          }));

          return { success: false, error: errorMessage };
        }
      },

      // Fetch single user with caching
      fetchUser: async (userId: string, force = false) => {
        const state = get();
        const cachedUser = state.users.byId[userId];
        
        // Return cached user if valid
        if (!force && cachedUser && isCacheValid(state.users.lastFetch, USER_CACHE_CONFIG.ttl)) {
          return { success: true, data: cachedUser, cached: true };
        }

        try {
          const user = await api.users.get(userId);

          set(state => ({
            users: updateEntity(state.users, user),
          }));

          return { success: true, data: user };
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to fetch user';
          return { success: false, error: errorMessage };
        }
      },

      // Fetch current user profile
      fetchCurrentUserProfile: async (force = false) => {
        const state = get();
        
        if (!force && state.currentUserProfile && isCacheValid(state.users.lastFetch, USER_CACHE_CONFIG.ttl)) {
          return { success: true, data: state.currentUserProfile, cached: true };
        }

        try {
          const profile = await api.users.getCurrentUserProfile();

          set(state => ({
            currentUserProfile: profile,
            users: updateEntity(state.users, profile),
          }));

          return { success: true, data: profile };
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to fetch profile';
          return { success: false, error: errorMessage };
        }
      },

      // Update user with optimistic updates
      updateUser: async (userId: string, updates: Partial<UserResponse>) => {
        const state = get();
        const originalUser = state.users.byId[userId];
        
        if (!originalUser) {
          return { success: false, error: 'User not found' };
        }

        // Optimistic update
        const optimisticUser = { ...originalUser, ...updates };
        set(state => ({
          users: updateEntity(state.users, optimisticUser),
          currentUserProfile: state.currentUserProfile?.id === userId 
            ? optimisticUser 
            : state.currentUserProfile,
        }));

        try {
          const updatedUser = await api.users.updateUser(userId, updates);

          set(state => ({
            users: updateEntity(state.users, updatedUser),
            currentUserProfile: state.currentUserProfile?.id === userId 
              ? updatedUser 
              : state.currentUserProfile,
          }));

          return { success: true, data: updatedUser };
        } catch (error) {
          // Revert optimistic update on error
          set(state => ({
            users: updateEntity(state.users, originalUser),
            currentUserProfile: state.currentUserProfile?.id === userId 
              ? originalUser 
              : state.currentUserProfile,
          }));

          const errorMessage = error instanceof Error ? error.message : 'Failed to update user';
          return { success: false, error: errorMessage };
        }
      },

      // Create new user
      createUser: async (userData) => {
        try {
          const newUser = await api.users.createUser(userData);

          set(state => ({
            users: updateEntity(state.users, newUser),
          }));

          return { success: true, data: newUser };
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to create user';
          return { success: false, error: errorMessage };
        }
      },

      // Delete user
      deleteUser: async (userId: string) => {
        const state = get();
        const userToDelete = state.users.byId[userId];
        
        if (!userToDelete) {
          return { success: false, error: 'User not found' };
        }

        // Optimistic removal
        set(state => ({
          users: removeEntity(state.users, userId),
        }));

        try {
          await api.users.deleteUser(userId);
          return { success: true, data: true };
        } catch (error) {
          // Revert on error
          set(state => ({
            users: updateEntity(state.users, userToDelete),
          }));

          const errorMessage = error instanceof Error ? error.message : 'Failed to delete user';
          return { success: false, error: errorMessage };
        }
      },

      // Optimistic update (for UI responsiveness)
      optimisticUpdateUser: (userId: string, updates: Partial<UserResponse>) => {
        set(state => {
          const user = state.users.byId[userId];
          if (!user) return state;

          const updatedUser = { ...user, ...updates };
          return {
            users: updateEntity(state.users, updatedUser),
            currentUserProfile: state.currentUserProfile?.id === userId 
              ? updatedUser 
              : state.currentUserProfile,
          };
        });
      },

      // Revert optimistic update
      revertOptimisticUpdate: (userId: string, originalData: UserResponse) => {
        set(state => ({
          users: updateEntity(state.users, originalData),
          currentUserProfile: state.currentUserProfile?.id === userId 
            ? originalData 
            : state.currentUserProfile,
        }));
      },

      // Cache management
      invalidateCache: () => {
        set(state => ({
          users: { ...state.users, lastFetch: null },
          currentUserProfile: null,
        }));
      },

      // Preload specific users
      preloadUsers: async (userIds: string[]) => {
        const state = get();
        const uncachedIds = userIds.filter(id => !state.users.byId[id]);
        
        if (uncachedIds.length === 0) return;

        const requests = uncachedIds.map(id => get().fetchUser(id));
        await Promise.allSettled(requests);
      },

      // Filtering and search
      setSearchQuery: (query: string) => set({ searchQuery: query }),
      setRoleFilter: (role: UserRole | null) => set({ roleFilter: role }),
      setTeamFilter: (teamId: string | null) => set({ teamFilter: teamId }),
      clearFilters: () => set({ searchQuery: '', roleFilter: null, teamFilter: null }),

      // Selectors
      getUserById: (userId: string) => {
        return get().users.byId[userId];
      },

      getUsersByRole: (role: UserRole) => {
        const state = get();
        return filterEntities(state.users, user => user.role === role);
      },

      getUsersByTeam: (teamId: string) => {
        const state = get();
        return filterEntities(state.users, user => user.team_id === teamId);
      },

      getTeamMembers: (teamId: string) => {
        const state = get();
        const memberIds = state.teams[teamId] || [];
        return memberIds.map(id => state.users.byId[id]).filter(Boolean) as UserResponse[];
      },

      getUserStats: () => {
        const state = get();
        const users = denormalizeEntities(state.users.byId, state.users.allIds);
        
        const byRole: Record<string, number> = {};
        const byTeam: Record<string, number> = {};
        
        users.forEach(user => {
          // Count by role
          if (user.role) {
            byRole[user.role] = (byRole[user.role] || 0) + 1;
          }
          
          // Count by team
          if (user.team_id) {
            byTeam[user.team_id] = (byTeam[user.team_id] || 0) + 1;
          }
        });
        
        return {
          total: users.length,
          byRole,
          byTeam,
        };
      },

      getFilteredUsers: () => {
        const state = get();
        let users = denormalizeEntities(state.users.byId, state.users.allIds);

        // Apply role filter
        if (state.roleFilter) {
          users = users.filter(user => user.role === state.roleFilter);
        }

        // Apply team filter
        if (state.teamFilter) {
          users = users.filter(user => user.team_id === state.teamFilter);
        }

        // Apply search query
        if (state.searchQuery) {
          const query = state.searchQuery.toLowerCase();
          users = users.filter(user => 
            user.name?.toLowerCase().includes(query) ||
            user.email?.toLowerCase().includes(query) ||
            user.github_username?.toLowerCase().includes(query)
          );
        }

        return sortEntities(users, 'name' as keyof UserResponse, 'asc');
      },

      getSearchResults: () => {
        const state = get();
        if (!state.searchQuery) return [];
        return get().getFilteredUsers();
      },

      isUserCached: (userId: string) => {
        const state = get();
        return userId in state.users.byId && isCacheValid(state.users.lastFetch, USER_CACHE_CONFIG.ttl);
      },

      getCacheStatus: () => {
        const state = get();
        return {
          size: state.users.allIds.length,
          lastFetch: state.users.lastFetch,
          isValid: isCacheValid(state.users.lastFetch, USER_CACHE_CONFIG.ttl),
        };
      },
    })),
    {
      name: 'user-store',
      partialize: (state) => ({
        users: state.users,
        currentUserProfile: state.currentUserProfile,
        teamMembers: state.teamMembers,
        teams: state.teams,
      }),
    }
  )
);