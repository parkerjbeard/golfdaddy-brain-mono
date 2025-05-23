/**
 * Types for normalized state management
 */

// Normalized store structure
export interface NormalizedState<T> {
  byId: Record<string, T>;
  allIds: string[];
  loading: boolean;
  error: string | null;
  lastFetch: number | null;
  hasMore: boolean;
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

// Store operation result
export interface StoreOperationResult<T> {
  success: boolean;
  data?: T;
  error?: string;
  cached?: boolean;
}