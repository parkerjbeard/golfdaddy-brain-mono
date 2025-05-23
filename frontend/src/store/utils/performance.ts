/**
 * Performance optimization utilities for store operations
 */

import { useCallback, useRef, useMemo } from 'react';
import { debounce, throttle } from 'lodash-es';

// Debounced store actions for performance
export const useDebouncedStoreActions = () => {
  // Create stable debounced functions
  const debouncedSearch = useCallback(
    debounce((searchFn: (query: string) => void, query: string) => {
      searchFn(query);
    }, 300),
    []
  );

  const debouncedFilter = useCallback(
    debounce((filterFn: (filters: any) => void, filters: any) => {
      filterFn(filters);
    }, 200),
    []
  );

  const debouncedSave = useCallback(
    debounce((saveFn: (data: any) => Promise<void>, data: any) => {
      saveFn(data);
    }, 1000),
    []
  );

  return {
    debouncedSearch,
    debouncedFilter,
    debouncedSave,
  };
};

// Throttled store actions for high-frequency updates
export const useThrottledStoreActions = () => {
  const throttledScroll = useCallback(
    throttle((scrollFn: (position: number) => void, position: number) => {
      scrollFn(position);
    }, 100),
    []
  );

  const throttledResize = useCallback(
    throttle((resizeFn: (dimensions: { width: number; height: number }) => void, dimensions: { width: number; height: number }) => {
      resizeFn(dimensions);
    }, 250),
    []
  );

  return {
    throttledScroll,
    throttledResize,
  };
};

// Memoization utilities for expensive computations
export const useMemoizedSelectors = <T>(
  selector: () => T,
  dependencies: any[]
): T => {
  return useMemo(selector, dependencies);
};

// Virtual scrolling helper for large lists
export const useVirtualScrolling = (
  itemCount: number,
  itemHeight: number,
  containerHeight: number
) => {
  const scrollTop = useRef(0);
  
  const visibleRange = useMemo(() => {
    const visibleCount = Math.ceil(containerHeight / itemHeight);
    const startIndex = Math.floor(scrollTop.current / itemHeight);
    const endIndex = Math.min(startIndex + visibleCount + 2, itemCount - 1); // +2 for buffer
    
    return {
      startIndex: Math.max(0, startIndex - 1), // -1 for buffer
      endIndex,
      visibleCount: endIndex - startIndex + 1,
    };
  }, [itemCount, itemHeight, containerHeight, scrollTop.current]);

  const onScroll = useCallback((event: React.UIEvent<HTMLDivElement>) => {
    scrollTop.current = event.currentTarget.scrollTop;
  }, []);

  return {
    visibleRange,
    onScroll,
    totalHeight: itemCount * itemHeight,
  };
};

// Batch operations for store updates
export class BatchManager {
  private pending: Array<() => void> = [];
  private timeoutId: NodeJS.Timeout | null = null;

  add(operation: () => void) {
    this.pending.push(operation);
    
    if (this.timeoutId) {
      clearTimeout(this.timeoutId);
    }
    
    this.timeoutId = setTimeout(() => {
      this.flush();
    }, 16); // Next frame
  }

  flush() {
    if (this.pending.length === 0) return;
    
    const operations = [...this.pending];
    this.pending = [];
    this.timeoutId = null;
    
    // Execute all operations in a single batch
    operations.forEach(operation => operation());
  }

  clear() {
    this.pending = [];
    if (this.timeoutId) {
      clearTimeout(this.timeoutId);
      this.timeoutId = null;
    }
  }
}

// Hook for batch management
export const useBatchManager = () => {
  const batchManager = useRef(new BatchManager());
  
  return {
    addToBatch: batchManager.current.add.bind(batchManager.current),
    flushBatch: batchManager.current.flush.bind(batchManager.current),
    clearBatch: batchManager.current.clear.bind(batchManager.current),
  };
};

// Performance monitoring for store operations
export class StorePerformanceMonitor {
  private metrics: Map<string, { count: number; totalTime: number; averageTime: number }> = new Map();

  measure<T>(operationName: string, operation: () => T): T {
    const startTime = performance.now();
    const result = operation();
    const endTime = performance.now();
    const duration = endTime - startTime;

    this.recordMetric(operationName, duration);
    return result;
  }

  async measureAsync<T>(operationName: string, operation: () => Promise<T>): Promise<T> {
    const startTime = performance.now();
    const result = await operation();
    const endTime = performance.now();
    const duration = endTime - startTime;

    this.recordMetric(operationName, duration);
    return result;
  }

  private recordMetric(operationName: string, duration: number) {
    const existing = this.metrics.get(operationName);
    
    if (existing) {
      existing.count++;
      existing.totalTime += duration;
      existing.averageTime = existing.totalTime / existing.count;
    } else {
      this.metrics.set(operationName, {
        count: 1,
        totalTime: duration,
        averageTime: duration,
      });
    }
  }

  getMetrics() {
    return Object.fromEntries(this.metrics);
  }

  getSlowOperations(threshold = 100) {
    return Object.fromEntries(
      Array.from(this.metrics.entries()).filter(
        ([_, metric]) => metric.averageTime > threshold
      )
    );
  }

  clear() {
    this.metrics.clear();
  }
}

// Hook for performance monitoring
export const useStorePerformanceMonitor = () => {
  const monitor = useRef(new StorePerformanceMonitor());
  
  return {
    measure: monitor.current.measure.bind(monitor.current),
    measureAsync: monitor.current.measureAsync.bind(monitor.current),
    getMetrics: monitor.current.getMetrics.bind(monitor.current),
    getSlowOperations: monitor.current.getSlowOperations.bind(monitor.current),
    clearMetrics: monitor.current.clear.bind(monitor.current),
  };
};

// Cache warming utilities
export const useCacheWarming = () => {
  const warmCache = useCallback(async (
    preloadFunctions: Array<() => Promise<any>>,
    batchSize = 3
  ) => {
    // Process preloads in batches to avoid overwhelming the network
    for (let i = 0; i < preloadFunctions.length; i += batchSize) {
      const batch = preloadFunctions.slice(i, i + batchSize);
      await Promise.allSettled(batch.map(fn => fn()));
      
      // Small delay between batches
      if (i + batchSize < preloadFunctions.length) {
        await new Promise(resolve => setTimeout(resolve, 100));
      }
    }
  }, []);

  return { warmCache };
};

// Memory usage monitoring
export const useMemoryMonitoring = () => {
  const getMemoryUsage = useCallback(() => {
    if ('memory' in performance) {
      return (performance as any).memory;
    }
    return null;
  }, []);

  const checkMemoryPressure = useCallback(() => {
    const memory = getMemoryUsage();
    if (!memory) return false;
    
    // Check if we're using more than 80% of available memory
    const usageRatio = memory.usedJSHeapSize / memory.jsHeapSizeLimit;
    return usageRatio > 0.8;
  }, [getMemoryUsage]);

  return {
    getMemoryUsage,
    checkMemoryPressure,
  };
};