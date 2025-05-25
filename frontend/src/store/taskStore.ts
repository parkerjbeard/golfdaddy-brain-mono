/**
 * Normalized Task Store with relationships and advanced caching
 */

import { create } from 'zustand';
import { devtools, subscribeWithSelector } from 'zustand/middleware';
import { Task, TaskStatus, CreateTaskPayload, CreateTaskResponse } from '@/types/entities';
import { UserResponse } from '@/types/user';
import { NormalizedState, CacheConfig, StoreOperationResult, QueryState } from './types';
import {
  createNormalizedState,
  updateNormalizedState,
  updateEntity,
  removeEntity,
  isCacheValid,
  filterEntities,
  sortEntities,
  denormalizeEntities,
  populateRelationships,
} from './utils/normalization';
import { tasksApi } from '@/services/api';
import { useUserStore } from './userStore';

// Cache configuration for tasks
const TASK_CACHE_CONFIG: CacheConfig = {
  ttl: 2 * 60 * 1000, // 2 minutes (tasks change more frequently)
  maxAge: 15 * 60 * 1000, // 15 minutes
  maxSize: 500, // Maximum 500 tasks in cache
};

interface TaskStoreState {
  // Normalized task data
  tasks: NormalizedState<Task>;
  
  // Query state for pagination and filtering
  query: QueryState;
  
  // Filtering and search
  statusFilter: TaskStatus | null;
  assigneeFilter: string | null;
  dueDateFilter: 'overdue' | 'today' | 'thisWeek' | 'thisMonth' | null;
  priorityFilter: string | null;
  searchQuery: string;
  
  // Task relationships cache
  tasksByUser: Record<string, string[]>; // userId -> taskIds
  tasksByStatus: Record<TaskStatus, string[]>; // status -> taskIds
  
  // Actions
  fetchTasks: (params?: {
    page?: number;
    limit?: number;
    status?: TaskStatus;
    assignee?: string;
    append?: boolean;
    force?: boolean;
  }) => Promise<StoreOperationResult<Task[]>>;
  
  fetchTask: (taskId: string, force?: boolean) => Promise<StoreOperationResult<Task>>;
  
  createTask: (taskData: CreateTaskPayload) => Promise<StoreOperationResult<CreateTaskResponse>>;
  
  updateTask: (taskId: string, updates: Partial<Task>) => Promise<StoreOperationResult<Task>>;
  
  deleteTask: (taskId: string) => Promise<StoreOperationResult<boolean>>;
  
  updateTaskStatus: (taskId: string, status: TaskStatus) => Promise<StoreOperationResult<Task>>;
  
  assignTask: (taskId: string, assigneeId: string) => Promise<StoreOperationResult<Task>>;
  
  // Bulk operations
  bulkUpdateTasks: (taskIds: string[], updates: Partial<Task>) => Promise<StoreOperationResult<Task[]>>;
  
  bulkDeleteTasks: (taskIds: string[]) => Promise<StoreOperationResult<boolean>>;
  
  // Optimistic updates
  optimisticUpdateTask: (taskId: string, updates: Partial<Task>) => void;
  revertOptimisticUpdate: (taskId: string, originalData: Task) => void;
  
  // Cache and data management
  invalidateCache: () => void;
  preloadTasks: (taskIds: string[]) => Promise<void>;
  hydrateTaskRelationships: (task: Task) => Task;
  refreshTaskRelationships: () => void;
  
  // Filtering and search
  setStatusFilter: (status: TaskStatus | null) => void;
  setAssigneeFilter: (assigneeId: string | null) => void;
  setDueDateFilter: (filter: 'overdue' | 'today' | 'thisWeek' | 'thisMonth' | null) => void;
  setPriorityFilter: (priority: string | null) => void;
  setSearchQuery: (query: string) => void;
  clearFilters: () => void;
  
  // Query management
  setPage: (page: number) => void;
  setLimit: (limit: number) => void;
  setSorting: (sortBy: string, sortOrder: 'asc' | 'desc') => void;
  
  // Selectors (computed)
  getTaskById: (taskId: string) => Task | undefined;
  getTasksByStatus: (status: TaskStatus) => Task[];
  getTasksByAssignee: (assigneeId: string) => Task[];
  getTasksByPriority: (priority: string) => Task[];
  getOverdueTasks: () => Task[];
  getTasksDueToday: () => Task[];
  getTasksDueThisWeek: () => Task[];
  getFilteredTasks: () => Task[];
  getSearchResults: () => Task[];
  getUserTaskStats: (userId: string) => {
    total: number;
    byStatus: Record<TaskStatus, number>;
    overdue: number;
  };
  getTaskStats: () => {
    total: number;
    byStatus: Record<TaskStatus, number>;
    byPriority: Record<string, number>;
    overdue: number;
  };
  isTaskCached: (taskId: string) => boolean;
  getCacheStatus: () => { size: number; lastFetch: number | null; isValid: boolean };
}

export const useTaskStore = create<TaskStoreState>()(
  devtools(
    subscribeWithSelector((set, get) => ({
      // Initial state
      tasks: createNormalizedState<Task>(),
      query: {
        page: 1,
        limit: 20,
        filters: {},
        sortBy: 'updated_at',
        sortOrder: 'desc',
      },
      statusFilter: null,
      assigneeFilter: null,
      dueDateFilter: null,
      priorityFilter: null,
      searchQuery: '',
      tasksByUser: {},
      tasksByStatus: {} as Record<TaskStatus, string[]>,

      // Fetch tasks with advanced filtering and pagination
      fetchTasks: async (params = {}) => {
        const state = get();
        const {
          page = state.query.page,
          limit = state.query.limit,
          status,
          assignee,
          append = false,
          force = false,
        } = params;

        // Check cache validity for exact same query
        const cacheKey = JSON.stringify({ page, limit, status, assignee });
        if (!force && isCacheValid(state.tasks.lastFetch, TASK_CACHE_CONFIG.ttl)) {
          const cachedTasks = denormalizeEntities(state.tasks.byId, state.tasks.allIds);
          return { success: true, data: cachedTasks, cached: true };
        }

        set(state => ({
          tasks: { ...state.tasks, loading: true, error: null },
        }));

        try {
          const queryParams: Record<string, any> = {
            page,
            limit,
            sort_by: state.query.sortBy,
            sort_order: state.query.sortOrder,
          };

          if (status) queryParams.status = status;
          if (assignee) queryParams.assignee_id = assignee;

          const response = await tasksApi.getTasks(queryParams);
          const tasks = response.tasks;

          // Update task relationships
          const tasksByUser: Record<string, string[]> = {};
          const tasksByStatus: Record<TaskStatus, string[]> = {};

          tasks.forEach(task => {
            // Group by assignee
            if (task.assignee_id) {
              if (!tasksByUser[task.assignee_id]) tasksByUser[task.assignee_id] = [];
              tasksByUser[task.assignee_id].push(task.id);
            }

            // Group by status
            if (!tasksByStatus[task.status]) tasksByStatus[task.status] = [];
            tasksByStatus[task.status].push(task.id);
          });

          set(state => ({
            tasks: updateNormalizedState(state.tasks, tasks, append),
            tasksByUser: append ? { ...state.tasksByUser, ...tasksByUser } : tasksByUser,
            tasksByStatus: append ? { ...state.tasksByStatus, ...tasksByStatus } : tasksByStatus,
            query: { ...state.query, page, limit },
          }));

          return { success: true, data: tasks };
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to fetch tasks';
          
          set(state => ({
            tasks: { ...state.tasks, loading: false, error: errorMessage },
          }));

          return { success: false, error: errorMessage };
        }
      },

      // Fetch single task
      fetchTask: async (taskId: string, force = false) => {
        const state = get();
        const cachedTask = state.tasks.byId[taskId];
        
        if (!force && cachedTask && isCacheValid(state.tasks.lastFetch, TASK_CACHE_CONFIG.ttl)) {
          return { success: true, data: cachedTask, cached: true };
        }

        try {
          const task = await tasksApi.getTask(taskId);

          set(state => ({
            tasks: updateEntity(state.tasks, task),
          }));

          return { success: true, data: task };
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to fetch task';
          return { success: false, error: errorMessage };
        }
      },

      // Create new task
      createTask: async (taskData: CreateTaskPayload) => {
        try {
          const response = await tasksApi.createTask(taskData);
          const { task, warnings } = response;

          set(state => ({
            tasks: updateEntity(state.tasks, task),
          }));

          // Update relationships
          get().refreshTaskRelationships();

          return { success: true, data: { task, warnings } };
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to create task';
          return { success: false, error: errorMessage };
        }
      },

      // Update task with optimistic updates
      updateTask: async (taskId: string, updates: Partial<Task>) => {
        const state = get();
        const originalTask = state.tasks.byId[taskId];
        
        if (!originalTask) {
          return { success: false, error: 'Task not found' };
        }

        // Optimistic update
        const optimisticTask = { ...originalTask, ...updates };
        set(state => ({
          tasks: updateEntity(state.tasks, optimisticTask),
        }));

        try {
          const updatedTask = await tasksApi.updateTask(taskId, updates);

          set(state => ({
            tasks: updateEntity(state.tasks, updatedTask),
          }));

          // Update relationships if assignee or status changed
          if (updates.assignee_id || updates.status) {
            get().refreshTaskRelationships();
          }

          return { success: true, data: updatedTask };
        } catch (error) {
          // Revert optimistic update on error
          set(state => ({
            tasks: updateEntity(state.tasks, originalTask),
          }));

          const errorMessage = error instanceof Error ? error.message : 'Failed to update task';
          return { success: false, error: errorMessage };
        }
      },

      // Delete task
      deleteTask: async (taskId: string) => {
        const state = get();
        const taskToDelete = state.tasks.byId[taskId];
        
        if (!taskToDelete) {
          return { success: false, error: 'Task not found' };
        }

        // Optimistic removal
        set(state => ({
          tasks: removeEntity(state.tasks, taskId),
        }));

        try {
          await tasksApi.deleteTask(taskId);
          get().refreshTaskRelationships();
          return { success: true, data: true };
        } catch (error) {
          // Revert on error
          set(state => ({
            tasks: updateEntity(state.tasks, taskToDelete),
          }));

          const errorMessage = error instanceof Error ? error.message : 'Failed to delete task';
          return { success: false, error: errorMessage };
        }
      },

      // Quick status update
      updateTaskStatus: async (taskId: string, status: TaskStatus) => {
        return get().updateTask(taskId, { status });
      },

      // Quick assignment
      assignTask: async (taskId: string, assigneeId: string) => {
        return get().updateTask(taskId, { assignee_id: assigneeId });
      },

      // Bulk operations
      bulkUpdateTasks: async (taskIds: string[], updates: Partial<Task>) => {
        try {
          const updatedTasks = await tasksApi.bulkUpdateTasks(taskIds, updates);

          set(state => {
            let newTasks = { ...state.tasks };
            updatedTasks.forEach(task => {
              newTasks = updateEntity(newTasks, task);
            });
            return { tasks: newTasks };
          });

          get().refreshTaskRelationships();
          return { success: true, data: updatedTasks };
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to bulk update tasks';
          return { success: false, error: errorMessage };
        }
      },

      bulkDeleteTasks: async (taskIds: string[]) => {
        const state = get();
        const tasksToDelete = taskIds.map(id => state.tasks.byId[id]).filter(Boolean);
        
        // Optimistic removal
        set(state => {
          let newTasks = { ...state.tasks };
          taskIds.forEach(id => {
            newTasks = removeEntity(newTasks, id);
          });
          return { tasks: newTasks };
        });

        try {
          await tasksApi.bulkDeleteTasks(taskIds);
          get().refreshTaskRelationships();
          return { success: true, data: true };
        } catch (error) {
          // Revert on error
          set(state => {
            let newTasks = { ...state.tasks };
            tasksToDelete.forEach(task => {
              newTasks = updateEntity(newTasks, task);
            });
            return { tasks: newTasks };
          });

          const errorMessage = error instanceof Error ? error.message : 'Failed to bulk delete tasks';
          return { success: false, error: errorMessage };
        }
      },

      // Optimistic updates
      optimisticUpdateTask: (taskId: string, updates: Partial<Task>) => {
        set(state => {
          const task = state.tasks.byId[taskId];
          if (!task) return state;

          const updatedTask = { ...task, ...updates };
          return { tasks: updateEntity(state.tasks, updatedTask) };
        });
      },

      revertOptimisticUpdate: (taskId: string, originalData: Task) => {
        set(state => ({
          tasks: updateEntity(state.tasks, originalData),
        }));
      },

      // Cache management
      invalidateCache: () => {
        set(state => ({
          tasks: { ...state.tasks, lastFetch: null },
        }));
      },

      preloadTasks: async (taskIds: string[]) => {
        const state = get();
        const uncachedIds = taskIds.filter(id => !state.tasks.byId[id]);
        
        if (uncachedIds.length === 0) return;

        const requests = uncachedIds.map(id => get().fetchTask(id));
        await Promise.allSettled(requests);
      },

      // Hydrate task with user relationships
      hydrateTaskRelationships: (task: Task) => {
        const userStore = useUserStore.getState();
        const hydratedTask = { ...task };

        // Populate user relationships
        if (task.assignee_id) {
          hydratedTask.assignee = userStore.getUserById(task.assignee_id);
        }
        if (task.responsible_id) {
          hydratedTask.responsible = userStore.getUserById(task.responsible_id);
        }
        if (task.accountable_id) {
          hydratedTask.accountable = userStore.getUserById(task.accountable_id);
        }
        if (task.creator_id) {
          hydratedTask.creator = userStore.getUserById(task.creator_id);
        }
        if (task.consulted_ids) {
          hydratedTask.consulted = task.consulted_ids
            .map(id => userStore.getUserById(id))
            .filter(Boolean) as UserResponse[];
        }
        if (task.informed_ids) {
          hydratedTask.informed = task.informed_ids
            .map(id => userStore.getUserById(id))
            .filter(Boolean) as UserResponse[];
        }

        return hydratedTask;
      },

      refreshTaskRelationships: () => {
        const state = get();
        const tasks = denormalizeEntities(state.tasks.byId, state.tasks.allIds);
        
        const tasksByUser: Record<string, string[]> = {};
        const tasksByStatus: Record<TaskStatus, string[]> = {};

        tasks.forEach(task => {
          if (task.assignee_id) {
            if (!tasksByUser[task.assignee_id]) tasksByUser[task.assignee_id] = [];
            tasksByUser[task.assignee_id].push(task.id);
          }

          if (!tasksByStatus[task.status]) tasksByStatus[task.status] = [];
          tasksByStatus[task.status].push(task.id);
        });

        set({ tasksByUser, tasksByStatus });
      },

      // Filtering and search
      setStatusFilter: (status: TaskStatus | null) => set({ statusFilter: status }),
      setAssigneeFilter: (assigneeId: string | null) => set({ assigneeFilter: assigneeId }),
      setDueDateFilter: (filter) => set({ dueDateFilter: filter }),
      setPriorityFilter: (priority: string | null) => set({ priorityFilter: priority }),
      setSearchQuery: (query: string) => set({ searchQuery: query }),
      clearFilters: () => set({
        statusFilter: null,
        assigneeFilter: null,
        dueDateFilter: null,
        priorityFilter: null,
        searchQuery: '',
      }),

      // Query management
      setPage: (page: number) => set(state => ({ query: { ...state.query, page } })),
      setLimit: (limit: number) => set(state => ({ query: { ...state.query, limit } })),
      setSorting: (sortBy: string, sortOrder: 'asc' | 'desc') => 
        set(state => ({ query: { ...state.query, sortBy, sortOrder } })),

      // Selectors
      getTaskById: (taskId: string) => {
        const task = get().tasks.byId[taskId];
        return task ? get().hydrateTaskRelationships(task) : undefined;
      },

      getTasksByStatus: (status: TaskStatus) => {
        const state = get();
        return filterEntities(state.tasks, task => task.status === status)
          .map(task => get().hydrateTaskRelationships(task));
      },

      getTasksByAssignee: (assigneeId: string) => {
        const state = get();
        return filterEntities(state.tasks, task => task.assignee_id === assigneeId)
          .map(task => get().hydrateTaskRelationships(task));
      },

      getTasksByPriority: (priority: string) => {
        const state = get();
        return filterEntities(state.tasks, task => task.priority === priority)
          .map(task => get().hydrateTaskRelationships(task));
      },

      getOverdueTasks: () => {
        const state = get();
        const now = new Date();
        return filterEntities(state.tasks, task => {
          if (!task.due_date) return false;
          return new Date(task.due_date) < now && task.status !== TaskStatus.DONE;
        }).map(task => get().hydrateTaskRelationships(task));
      },

      getTasksDueToday: () => {
        const state = get();
        const today = new Date().toDateString();
        return filterEntities(state.tasks, task => {
          if (!task.due_date) return false;
          return new Date(task.due_date).toDateString() === today;
        }).map(task => get().hydrateTaskRelationships(task));
      },

      getTasksDueThisWeek: () => {
        const state = get();
        const now = new Date();
        const weekFromNow = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
        
        return filterEntities(state.tasks, task => {
          if (!task.due_date) return false;
          const dueDate = new Date(task.due_date);
          return dueDate >= now && dueDate <= weekFromNow;
        }).map(task => get().hydrateTaskRelationships(task));
      },

      getFilteredTasks: () => {
        const state = get();
        let tasks = denormalizeEntities(state.tasks.byId, state.tasks.allIds);

        // Apply filters
        if (state.statusFilter) {
          tasks = tasks.filter(task => task.status === state.statusFilter);
        }
        if (state.assigneeFilter) {
          tasks = tasks.filter(task => task.assignee_id === state.assigneeFilter);
        }
        if (state.priorityFilter) {
          tasks = tasks.filter(task => task.priority === state.priorityFilter);
        }
        if (state.dueDateFilter) {
          const now = new Date();
          const today = now.toDateString();
          const weekFromNow = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
          
          tasks = tasks.filter(task => {
            if (!task.due_date) return false;
            const dueDate = new Date(task.due_date);
            
            switch (state.dueDateFilter) {
              case 'overdue':
                return dueDate < now && task.status !== TaskStatus.DONE;
              case 'today':
                return dueDate.toDateString() === today;
              case 'thisWeek':
                return dueDate >= now && dueDate <= weekFromNow;
              case 'thisMonth':
                return dueDate.getMonth() === now.getMonth() && dueDate.getFullYear() === now.getFullYear();
              default:
                return true;
            }
          });
        }

        // Apply search
        if (state.searchQuery) {
          const query = state.searchQuery.toLowerCase();
          tasks = tasks.filter(task =>
            task.title.toLowerCase().includes(query) ||
            task.description.toLowerCase().includes(query) ||
            task.tags?.some(tag => tag.toLowerCase().includes(query))
          );
        }

        // Sort and hydrate
        const sortedTasks = sortEntities(tasks, state.query.sortBy as keyof Task, state.query.sortOrder);
        return sortedTasks.map(task => get().hydrateTaskRelationships(task));
      },

      getSearchResults: () => {
        const state = get();
        if (!state.searchQuery) return [];
        return get().getFilteredTasks();
      },

      getUserTaskStats: (userId: string) => {
        const state = get();
        const userTasks = filterEntities(state.tasks, task => 
          task.assignee_id === userId || 
          task.responsible_id === userId || 
          task.accountable_id === userId
        );

        const byStatus: Record<TaskStatus, number> = {} as Record<TaskStatus, number>;
        Object.values(TaskStatus).forEach(status => {
          byStatus[status] = 0;
        });

        let overdue = 0;
        const now = new Date();

        userTasks.forEach(task => {
          byStatus[task.status]++;
          if (task.due_date && new Date(task.due_date) < now && task.status !== TaskStatus.DONE) {
            overdue++;
          }
        });

        return {
          total: userTasks.length,
          byStatus,
          overdue,
        };
      },

      getTaskStats: () => {
        const state = get();
        const tasks = denormalizeEntities(state.tasks.byId, state.tasks.allIds);

        const byStatus: Record<TaskStatus, number> = {} as Record<TaskStatus, number>;
        Object.values(TaskStatus).forEach(status => {
          byStatus[status] = 0;
        });

        const byPriority: Record<string, number> = {};
        let overdue = 0;
        const now = new Date();

        tasks.forEach(task => {
          byStatus[task.status]++;
          
          if (task.priority) {
            byPriority[task.priority] = (byPriority[task.priority] || 0) + 1;
          }

          if (task.due_date && new Date(task.due_date) < now && task.status !== TaskStatus.DONE) {
            overdue++;
          }
        });

        return {
          total: tasks.length,
          byStatus,
          byPriority,
          overdue,
        };
      },

      isTaskCached: (taskId: string) => {
        const state = get();
        return taskId in state.tasks.byId && isCacheValid(state.tasks.lastFetch, TASK_CACHE_CONFIG.ttl);
      },

      getCacheStatus: () => {
        const state = get();
        return {
          size: state.tasks.allIds.length,
          lastFetch: state.tasks.lastFetch,
          isValid: isCacheValid(state.tasks.lastFetch, TASK_CACHE_CONFIG.ttl),
        };
      },
    })),
    {
      name: 'task-store',
      partialize: (state) => ({
        tasks: state.tasks,
        tasksByUser: state.tasksByUser,
        tasksByStatus: state.tasksByStatus,
        query: state.query,
      }),
    }
  )
);