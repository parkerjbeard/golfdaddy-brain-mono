/**
 * Comprehensive error boundary implementation with logging and recovery
 */

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { ErrorBoundaryFallback } from './ui/ErrorStates';
import { createEnhancedError, globalErrorReporter } from '@/store/utils/errorHandling';

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  errorId: string | null;
  retryCount: number;
}

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: React.ComponentType<{
    error: Error;
    resetError: () => void;
    retryCount: number;
  }>;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  maxRetries?: number;
  resetOnPropsChange?: boolean;
  resetKeys?: Array<string | number>;
  isolate?: boolean; // If true, only catches errors from direct children
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  private resetTimeoutId: number | null = null;

  constructor(props: ErrorBoundaryProps) {
    super(props);

    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: null,
      retryCount: 0,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    // Update state so the next render will show the fallback UI
    return {
      hasError: true,
      error,
      errorId: `boundary_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    const { onError } = this.props;

    // Update state with error info
    this.setState({ errorInfo });

    // Create enhanced error for reporting
    const enhancedError = createEnhancedError(
      error,
      'React Error Boundary',
      undefined,
      {
        componentStack: errorInfo.componentStack,
        errorBoundary: this.constructor.name,
        retryCount: this.state.retryCount,
      }
    );

    // Report error
    globalErrorReporter.reportError(enhancedError);

    // Call custom error handler
    if (onError) {
      onError(error, errorInfo);
    }

    // Log error for development
    if (process.env.NODE_ENV === 'development') {
      console.group('🚨 Error Boundary Caught Error');
      console.error('Error:', error);
      console.error('Error Info:', errorInfo);
      console.error('Component Stack:', errorInfo.componentStack);
      console.groupEnd();
    }
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    const { resetOnPropsChange, resetKeys } = this.props;
    const { hasError } = this.state;

    // Reset error boundary when specified props change
    if (hasError && resetOnPropsChange && prevProps.children !== this.props.children) {
      this.resetErrorBoundary();
    }

    // Reset when resetKeys change
    if (hasError && resetKeys && prevProps.resetKeys) {
      const hasResetKeyChanged = resetKeys.some(
        (key, idx) => prevProps.resetKeys![idx] !== key
      );
      
      if (hasResetKeyChanged) {
        this.resetErrorBoundary();
      }
    }
  }

  resetErrorBoundary = () => {
    const { maxRetries = 3 } = this.props;
    const { retryCount } = this.state;

    // Check retry limit
    if (retryCount >= maxRetries) {
      console.warn(`Error boundary retry limit (${maxRetries}) reached`);
      return;
    }

    this.setState(prevState => ({
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: null,
      retryCount: prevState.retryCount + 1,
    }));

    // Clear any pending reset timeout
    if (this.resetTimeoutId) {
      clearTimeout(this.resetTimeoutId);
      this.resetTimeoutId = null;
    }
  };

  render() {
    const { hasError, error, retryCount } = this.state;
    const { children, fallback: FallbackComponent, maxRetries = 3 } = this.props;

    if (hasError && error) {
      // Use custom fallback or default
      if (FallbackComponent) {
        return (
          <FallbackComponent
            error={error}
            resetError={this.resetErrorBoundary}
            retryCount={retryCount}
          />
        );
      }

      return (
        <ErrorBoundaryFallback
          error={error}
          resetError={this.resetErrorBoundary}
        />
      );
    }

    return children;
  }
}

// Hook for error boundaries
export const useErrorBoundary = () => {
  const [error, setError] = React.useState<Error | null>(null);

  const resetError = React.useCallback(() => {
    setError(null);
  }, []);

  const captureError = React.useCallback((error: Error) => {
    setError(error);
  }, []);

  React.useEffect(() => {
    if (error) {
      throw error;
    }
  }, [error]);

  return { captureError, resetError };
};

// Async error boundary for handling promise rejections
export const AsyncErrorBoundary: React.FC<{
  children: ReactNode;
  onError?: (error: Error) => void;
}> = ({ children, onError }) => {
  const { captureError } = useErrorBoundary();

  React.useEffect(() => {
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      const error = event.reason instanceof Error 
        ? event.reason 
        : new Error(String(event.reason));

      if (onError) {
        onError(error);
      }

      captureError(error);
    };

    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    return () => {
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, [captureError, onError]);

  return <>{children}</>;
};

// Specific error boundaries for different sections
export const DashboardErrorBoundary: React.FC<{ children: ReactNode }> = ({ children }) => {
  return (
    <ErrorBoundary
      maxRetries={2}
      resetOnPropsChange={true}
      onError={(error, errorInfo) => {
        console.error('Dashboard Error:', error, errorInfo);
      }}
      fallback={({ error, resetError }) => (
        <div className="p-8 text-center">
          <h2 className="text-lg font-semibold mb-2">Dashboard Error</h2>
          <p className="text-muted-foreground mb-4">
            Unable to load the dashboard. Please try again.
          </p>
          <button 
            onClick={resetError}
            className="px-4 py-2 bg-primary text-primary-foreground rounded"
          >
            Reload Dashboard
          </button>
        </div>
      )}
    >
      {children}
    </ErrorBoundary>
  );
};

export const FormErrorBoundary: React.FC<{ children: ReactNode }> = ({ children }) => {
  return (
    <ErrorBoundary
      maxRetries={1}
      isolate={true}
      onError={(error) => {
        console.error('Form Error:', error);
      }}
      fallback={({ error, resetError }) => (
        <div className="p-4 border border-red-200 bg-red-50 rounded">
          <h3 className="font-medium text-red-800">Form Error</h3>
          <p className="text-sm text-red-600 mt-1">
            There was an error with the form. Please refresh and try again.
          </p>
          <button 
            onClick={resetError}
            className="mt-2 text-sm text-red-700 underline"
          >
            Reset Form
          </button>
        </div>
      )}
    >
      {children}
    </ErrorBoundary>
  );
};

export const TableErrorBoundary: React.FC<{ children: ReactNode }> = ({ children }) => {
  return (
    <ErrorBoundary
      maxRetries={3}
      resetOnPropsChange={true}
      fallback={({ error, resetError, retryCount }) => (
        <div className="p-6 text-center border border-dashed border-gray-300 rounded">
          <h3 className="font-medium mb-2">Table Loading Error</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Unable to load table data. 
            {retryCount > 0 && ` (Attempt ${retryCount + 1})`}
          </p>
          <button 
            onClick={resetError}
            className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 rounded"
          >
            Try Again
          </button>
        </div>
      )}
    >
      {children}
    </ErrorBoundary>
  );
};

// Global error boundary wrapper
export const GlobalErrorBoundary: React.FC<{ children: ReactNode }> = ({ children }) => {
  return (
    <ErrorBoundary
      maxRetries={1}
      onError={(error, errorInfo) => {
        // Log to external service in production
        if (process.env.NODE_ENV === 'production') {
          // TODO: Send to error tracking service
          console.error('Global Error:', error, errorInfo);
        }
      }}
      fallback={({ error, resetError }) => (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="max-w-md mx-auto text-center p-6">
            <div className="w-16 h-16 mx-auto mb-4 bg-red-100 rounded-full flex items-center justify-center">
              <svg className="w-8 h-8 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <h1 className="text-xl font-semibold mb-2">Something went wrong</h1>
            <p className="text-gray-600 mb-6">
              We're sorry, but something unexpected happened. Please try refreshing the page.
            </p>
            <div className="space-x-4">
              <button 
                onClick={resetError}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                Try Again
              </button>
              <button 
                onClick={() => window.location.reload()}
                className="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300"
              >
                Refresh Page
              </button>
            </div>
          </div>
        </div>
      )}
    >
      <AsyncErrorBoundary>
        {children}
      </AsyncErrorBoundary>
    </ErrorBoundary>
  );
};