/**
 * Utility functions for data normalization and denormalization
 */

import { NormalizedState, EntityRelationships, LoadingStates, ErrorStates, OptimisticUpdate } from '../types';
import { createInitialLoadingStates, createInitialErrorStates } from './loading';

/**
 * Normalize an array of entities by their ID
 */
export function normalizeEntities<T extends { id: string }>(
  entities: T[]
): { byId: Record<string, T>; allIds: string[] } {
  const byId: Record<string, T> = {};
  const allIds: string[] = [];

  entities.forEach(entity => {
    byId[entity.id] = entity;
    allIds.push(entity.id);
  });

  return { byId, allIds };
}

/**
 * Denormalize entities back to an array
 */
export function denormalizeEntities<T>(
  byId: Record<string, T>,
  allIds: string[]
): T[] {
  return allIds.map(id => byId[id]).filter(Boolean);
}

/**
 * Create initial normalized state
 */
export function createNormalizedState<T>(): NormalizedState<T> {
  return {
    byId: {},
    allIds: [],
    loading: createInitialLoadingStates(),
    errors: createInitialErrorStates(),
    lastFetch: null,
    hasMore: true,
    optimisticUpdates: {},
  };
}

/**
 * Update normalized state with new entities
 */
export function updateNormalizedState<T extends { id: string }>(
  state: NormalizedState<T>,
  entities: T[],
  append = false
): NormalizedState<T> {
  const { byId: newById, allIds: newAllIds } = normalizeEntities(entities);
  
  if (append) {
    // Append new entities, avoiding duplicates
    const existingIds = new Set(state.allIds);
    const uniqueNewIds = newAllIds.filter(id => !existingIds.has(id));
    
    return {
      ...state,
      byId: { ...state.byId, ...newById },
      allIds: [...state.allIds, ...uniqueNewIds],
      lastFetch: Date.now(),
      loading: {
        ...state.loading,
        fetching: false,
      },
      errors: {
        ...state.errors,
        fetch: null,
      },
    };
  } else {
    // Replace all entities
    return {
      ...state,
      byId: newById,
      allIds: newAllIds,
      lastFetch: Date.now(),
      loading: {
        ...state.loading,
        fetching: false,
      },
      errors: {
        ...state.errors,
        fetch: null,
      },
    };
  }
}

/**
 * Update a single entity in normalized state
 */
export function updateEntity<T extends { id: string }>(
  state: NormalizedState<T>,
  entity: T
): NormalizedState<T> {
  const exists = entity.id in state.byId;
  
  return {
    ...state,
    byId: {
      ...state.byId,
      [entity.id]: entity,
    },
    allIds: exists ? state.allIds : [...state.allIds, entity.id],
  };
}

/**
 * Remove an entity from normalized state
 */
export function removeEntity<T>(
  state: NormalizedState<T>,
  entityId: string
): NormalizedState<T> {
  const { [entityId]: removed, ...byId } = state.byId;
  const allIds = state.allIds.filter(id => id !== entityId);
  
  return {
    ...state,
    byId,
    allIds,
  };
}

/**
 * Check if cache is valid based on TTL
 */
export function isCacheValid(
  lastFetch: number | null,
  ttl: number
): boolean {
  if (!lastFetch) return false;
  return Date.now() - lastFetch < ttl;
}

/**
 * Populate entity relationships
 */
export function populateRelationships<T>(
  entity: T,
  relationships: EntityRelationships,
  stores: Record<string, NormalizedState<any>>
): T {
  const populated = { ...entity };
  
  Object.entries(relationships).forEach(([entityType, relations]) => {
    Object.entries(relations).forEach(([relationKey, relationIds]) => {
      const store = stores[entityType];
      if (!store) return;

      if (Array.isArray(relationIds)) {
        // One-to-many relationship
        (populated as any)[relationKey] = relationIds
          .map(id => store.byId[id])
          .filter(Boolean);
      } else {
        // One-to-one relationship
        (populated as any)[relationKey] = store.byId[relationIds];
      }
    });
  });
  
  return populated;
}

/**
 * Filter entities by predicate
 */
export function filterEntities<T>(
  state: NormalizedState<T>,
  predicate: (entity: T) => boolean
): T[] {
  return state.allIds
    .map(id => state.byId[id])
    .filter(Boolean)
    .filter(predicate);
}

/**
 * Sort entities by key
 */
export function sortEntities<T>(
  entities: T[],
  sortBy: keyof T,
  sortOrder: 'asc' | 'desc' = 'asc'
): T[] {
  return [...entities].sort((a, b) => {
    const aVal = a[sortBy];
    const bVal = b[sortBy];
    
    if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1;
    if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1;
    return 0;
  });
}

/**
 * Paginate entities
 */
export function paginateEntities<T>(
  entities: T[],
  page: number,
  limit: number
): T[] {
  const startIndex = (page - 1) * limit;
  const endIndex = startIndex + limit;
  return entities.slice(startIndex, endIndex);
}