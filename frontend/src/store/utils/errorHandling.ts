/**
 * Comprehensive error handling utilities for store operations
 */

import React from 'react';
import { StoreError, RetryConfig, OperationContext } from '../types';
import { storeEvents } from './sync';

// Error classification
export enum ErrorSeverity {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical',
}

export enum ErrorCategory {
  NETWORK = 'network',
  VALIDATION = 'validation',
  AUTHORIZATION = 'authorization',
  SERVER = 'server',
  CLIENT = 'client',
  TIMEOUT = 'timeout',
  UNKNOWN = 'unknown',
}

// Enhanced error information
export interface EnhancedStoreError extends StoreError {
  severity: ErrorSeverity;
  category: ErrorCategory;
  userMessage: string;
  technicalDetails?: string;
  suggestions?: string[];
  correlationId?: string;
}

// Error handler configuration
export interface ErrorHandlerConfig {
  enableAutoRetry: boolean;
  enableUserNotification: boolean;
  enableErrorReporting: boolean;
  maxRetries: number;
  retryDelay: number;
  silentErrors: string[];
}

export const defaultErrorHandlerConfig: ErrorHandlerConfig = {
  enableAutoRetry: true,
  enableUserNotification: true,
  enableErrorReporting: true,
  maxRetries: 3,
  retryDelay: 1000,
  silentErrors: ['404', 'AbortError'],
};

// Error classification utility
export const classifyError = (error: any): { category: ErrorCategory; severity: ErrorSeverity } => {
  // Network errors
  if (error.name === 'NetworkError' || error.message?.includes('network')) {
    return { category: ErrorCategory.NETWORK, severity: ErrorSeverity.MEDIUM };
  }

  // Timeout errors
  if (error.name === 'TimeoutError' || error.code === 'TIMEOUT') {
    return { category: ErrorCategory.TIMEOUT, severity: ErrorSeverity.MEDIUM };
  }

  // HTTP status code classification
  if (error.statusCode || error.status) {
    const status = error.statusCode || error.status;
    
    if (status >= 400 && status < 500) {
      if (status === 401 || status === 403) {
        return { category: ErrorCategory.AUTHORIZATION, severity: ErrorSeverity.HIGH };
      }
      if (status === 422 || status === 400) {
        return { category: ErrorCategory.VALIDATION, severity: ErrorSeverity.LOW };
      }
      return { category: ErrorCategory.CLIENT, severity: ErrorSeverity.MEDIUM };
    }
    
    if (status >= 500) {
      return { category: ErrorCategory.SERVER, severity: ErrorSeverity.HIGH };
    }
  }

  return { category: ErrorCategory.UNKNOWN, severity: ErrorSeverity.MEDIUM };
};

// Create enhanced error
export const createEnhancedError = (
  error: any,
  operation: string,
  entityId?: string,
  context?: Record<string, any>
): EnhancedStoreError => {
  const { category, severity } = classifyError(error);
  
  const baseError: StoreError = {
    message: error.message || 'An unexpected error occurred',
    code: error.code || error.name,
    statusCode: error.statusCode || error.status,
    timestamp: Date.now(),
    operation,
    entityId,
    retryable: isRetryableError(error),
    context,
  };

  return {
    ...baseError,
    severity,
    category,
    userMessage: generateUserMessage(category, operation),
    technicalDetails: error.stack || JSON.stringify(error),
    suggestions: generateSuggestions(category, severity),
    correlationId: generateCorrelationId(),
  };
};

// Check if error is retryable
export const isRetryableError = (error: any): boolean => {
  // Network errors are retryable
  if (error.name === 'NetworkError' || error.name === 'TimeoutError') {
    return true;
  }

  // Server errors (5xx) are retryable
  const status = error.statusCode || error.status;
  if (status >= 500 && status < 600) {
    return true;
  }

  // Rate limiting is retryable
  if (status === 429) {
    return true;
  }

  // Specific error codes that are retryable
  const retryableCodes = ['ECONNRESET', 'ENOTFOUND', 'ECONNREFUSED'];
  if (retryableCodes.includes(error.code)) {
    return true;
  }

  return false;
};

// Generate user-friendly error messages
export const generateUserMessage = (category: ErrorCategory, operation: string): string => {
  const operationName = operation.toLowerCase();
  
  switch (category) {
    case ErrorCategory.NETWORK:
      return `Unable to ${operationName} due to a network issue. Please check your connection and try again.`;
    
    case ErrorCategory.AUTHORIZATION:
      return `You don't have permission to ${operationName}. Please contact your administrator.`;
    
    case ErrorCategory.VALIDATION:
      return `The information provided is invalid. Please check your input and try again.`;
    
    case ErrorCategory.SERVER:
      return `Server error occurred while trying to ${operationName}. Please try again later.`;
    
    case ErrorCategory.TIMEOUT:
      return `The ${operationName} operation timed out. Please try again.`;
    
    default:
      return `An error occurred while trying to ${operationName}. Please try again.`;
  }
};

// Generate helpful suggestions
export const generateSuggestions = (category: ErrorCategory, severity: ErrorSeverity): string[] => {
  const suggestions: string[] = [];
  
  switch (category) {
    case ErrorCategory.NETWORK:
      suggestions.push('Check your internet connection');
      suggestions.push('Try refreshing the page');
      suggestions.push('Contact IT support if the problem persists');
      break;
    
    case ErrorCategory.AUTHORIZATION:
      suggestions.push('Log out and log back in');
      suggestions.push('Contact your administrator for access');
      break;
    
    case ErrorCategory.VALIDATION:
      suggestions.push('Double-check all required fields');
      suggestions.push('Ensure data formats are correct');
      break;
    
    case ErrorCategory.SERVER:
      suggestions.push('Try again in a few minutes');
      suggestions.push('Contact support if the issue continues');
      break;
    
    case ErrorCategory.TIMEOUT:
      suggestions.push('Try again with a more stable connection');
      suggestions.push('Reduce the amount of data being processed');
      break;
  }
  
  if (severity === ErrorSeverity.CRITICAL) {
    suggestions.push('Contact support immediately');
  }
  
  return suggestions;
};

// Generate correlation ID for error tracking
export const generateCorrelationId = (): string => {
  return `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
};

// Error reporter
export class ErrorReporter {
  private config: ErrorHandlerConfig;
  private errorQueue: EnhancedStoreError[] = [];
  private reportingInterval: NodeJS.Timer | null = null;

  constructor(config: ErrorHandlerConfig = defaultErrorHandlerConfig) {
    this.config = config;
    
    if (config.enableErrorReporting) {
      this.startErrorReporting();
    }
  }

  reportError(error: EnhancedStoreError): void {
    // Add to queue for batch reporting
    this.errorQueue.push(error);
    
    // Emit event for immediate handling
    storeEvents.emit('store-error', error);
    
    // Critical errors should be reported immediately
    if (error.severity === ErrorSeverity.CRITICAL) {
      this.flushErrorQueue();
    }
  }

  private startErrorReporting(): void {
    // Report errors every 30 seconds
    this.reportingInterval = setInterval(() => {
      this.flushErrorQueue();
    }, 30000);
  }

  private flushErrorQueue(): void {
    if (this.errorQueue.length === 0) return;
    
    const errors = [...this.errorQueue];
    this.errorQueue = [];
    
    // Send to error reporting service
    this.sendToErrorService(errors);
  }

  private async sendToErrorService(errors: EnhancedStoreError[]): Promise<void> {
    try {
      // In a real implementation, this would send to an error reporting service
      console.group('🚨 Store Errors Report');
      errors.forEach(error => {
        console.error(`[${error.severity.toUpperCase()}] ${error.operation}:`, {
          message: error.message,
          category: error.category,
          correlationId: error.correlationId,
          entityId: error.entityId,
          technicalDetails: error.technicalDetails,
        });
      });
      console.groupEnd();
      
      // Example: Send to external service
      // await fetch('/api/errors', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify(errors),
      // });
    } catch (reportingError) {
      console.error('Failed to report errors:', reportingError);
    }
  }

  destroy(): void {
    if (this.reportingInterval) {
      clearInterval(this.reportingInterval);
    }
    this.flushErrorQueue();
  }
}

// Retry mechanism with exponential backoff
export class RetryManager {
  private config: RetryConfig;

  constructor(config: RetryConfig) {
    this.config = config;
  }

  async executeWithRetry<T>(
    operation: () => Promise<T>,
    context: OperationContext,
    onRetry?: (attempt: number, error: EnhancedStoreError) => void
  ): Promise<T> {
    let lastError: EnhancedStoreError | null = null;
    
    for (let attempt = 1; attempt <= this.config.maxAttempts; attempt++) {
      try {
        return await operation();
      } catch (error) {
        lastError = createEnhancedError(error, context.operation, context.entityId);
        
        // Don't retry if not retryable or on last attempt
        if (!lastError.retryable || attempt === this.config.maxAttempts) {
          throw lastError;
        }
        
        // Calculate delay
        const delay = this.config.backoffMs * Math.pow(this.config.backoffMultiplier, attempt - 1);
        
        // Notify about retry
        if (onRetry) {
          onRetry(attempt, lastError);
        }
        
        storeEvents.emit('operation-retry', {
          attempt,
          delay,
          error: lastError,
          context,
        });
        
        // Wait before retry
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
    
    throw lastError;
  }
}

// Global error handler instance
export const globalErrorReporter = new ErrorReporter();

// Cleanup on app unmount
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    globalErrorReporter.destroy();
  });
}

// Hook for error handling in components
export const useErrorHandler = (config?: Partial<ErrorHandlerConfig>) => {
  const effectiveConfig = { ...defaultErrorHandlerConfig, ...config };
  const reporter = React.useMemo(() => new ErrorReporter(effectiveConfig), [effectiveConfig]);
  
  React.useEffect(() => {
    return () => reporter.destroy();
  }, [reporter]);

  const handleError = React.useCallback((error: any, operation: string, entityId?: string) => {
    const enhancedError = createEnhancedError(error, operation, entityId);
    reporter.reportError(enhancedError);
    return enhancedError;
  }, [reporter]);

  return {
    handleError,
    reportError: reporter.reportError.bind(reporter),
    createError: createEnhancedError,
  };
};