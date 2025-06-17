/**
 * Error state components for different scenarios
 */

import React from 'react';
import { Alert, AlertDescription, AlertTitle } from './alert';
import { Button } from './button';
import { Card } from './card';
import { Badge } from './badge';
import { 
  AlertTriangle, 
  RefreshCw, 
  Wifi, 
  Shield, 
  Clock, 
  Server, 
  AlertCircle,
  Info,
  X,
  ChevronDown,
  ChevronRight,
  Copy,
  Bug
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { EnhancedStoreError, ErrorSeverity, ErrorCategory } from '@/store/utils/errorHandling';

// Basic error alert
export interface ErrorAlertProps {
  error: string | EnhancedStoreError;
  onRetry?: () => void;
  onDismiss?: () => void;
  className?: string;
}

export const ErrorAlert: React.FC<ErrorAlertProps> = ({
  error,
  onRetry,
  onDismiss,
  className
}) => {
  const errorObj = typeof error === 'string' ? { message: error, severity: ErrorSeverity.MEDIUM } : error;
  
  const getIcon = () => {
    if (typeof error === 'string') return <AlertCircle className="h-4 w-4" />;
    
    switch (errorObj.category) {
      case ErrorCategory.NETWORK:
        return <Wifi className="h-4 w-4" />;
      case ErrorCategory.AUTHORIZATION:
        return <Shield className="h-4 w-4" />;
      case ErrorCategory.TIMEOUT:
        return <Clock className="h-4 w-4" />;
      case ErrorCategory.SERVER:
        return <Server className="h-4 w-4" />;
      default:
        return <AlertTriangle className="h-4 w-4" />;
    }
  };

  const getVariant = () => {
    if (typeof error === 'string') return 'destructive';
    
    switch (errorObj.severity) {
      case ErrorSeverity.LOW:
        return 'default';
      case ErrorSeverity.MEDIUM:
        return 'default';
      case ErrorSeverity.HIGH:
      case ErrorSeverity.CRITICAL:
        return 'destructive';
      default:
        return 'destructive';
    }
  };

  return (
    <Alert variant={getVariant()} className={className}>
      {getIcon()}
      <AlertTitle className="flex items-center justify-between">
        Error
        {onDismiss && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onDismiss}
            className="h-4 w-4 p-0"
          >
            <X className="h-3 w-3" />
          </Button>
        )}
      </AlertTitle>
      <AlertDescription className="mt-2">
        <div className="space-y-2">
          <p>{typeof error === 'string' ? error : errorObj.userMessage || errorObj.message}</p>
          
          {typeof error !== 'string' && errorObj.suggestions && errorObj.suggestions.length > 0 && (
            <ul className="list-disc list-inside text-sm space-y-1">
              {errorObj.suggestions.map((suggestion, index) => (
                <li key={index}>{suggestion}</li>
              ))}
            </ul>
          )}
          
          {onRetry && (
            <Button
              variant="outline"
              size="sm"
              onClick={onRetry}
              className="mt-2"
            >
              <RefreshCw className="h-3 w-3 mr-1" />
              Try Again
            </Button>
          )}
        </div>
      </AlertDescription>
    </Alert>
  );
};

// Detailed error card with expandable technical details
export interface DetailedErrorCardProps {
  error: EnhancedStoreError;
  onRetry?: () => void;
  onReport?: (error: EnhancedStoreError) => void;
  className?: string;
}

export const DetailedErrorCard: React.FC<DetailedErrorCardProps> = ({
  error,
  onRetry,
  onReport,
  className
}) => {
  const [showDetails, setShowDetails] = React.useState(false);
  const [copied, setCopied] = React.useState(false);

  const getSeverityColor = (severity: ErrorSeverity) => {
    switch (severity) {
      case ErrorSeverity.LOW:
        return 'bg-blue-100 text-blue-800';
      case ErrorSeverity.MEDIUM:
        return 'bg-yellow-100 text-yellow-800';
      case ErrorSeverity.HIGH:
        return 'bg-orange-100 text-orange-800';
      case ErrorSeverity.CRITICAL:
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getCategoryIcon = (category: ErrorCategory) => {
    switch (category) {
      case ErrorCategory.NETWORK:
        return <Wifi className="h-4 w-4" />;
      case ErrorCategory.AUTHORIZATION:
        return <Shield className="h-4 w-4" />;
      case ErrorCategory.TIMEOUT:
        return <Clock className="h-4 w-4" />;
      case ErrorCategory.SERVER:
        return <Server className="h-4 w-4" />;
      case ErrorCategory.VALIDATION:
        return <AlertCircle className="h-4 w-4" />;
      default:
        return <Bug className="h-4 w-4" />;
    }
  };

  const copyErrorDetails = async () => {
    const details = JSON.stringify({
      message: error.message,
      code: error.code,
      operation: error.operation,
      correlationId: error.correlationId,
      timestamp: new Date(error.timestamp).toISOString(),
      technicalDetails: error.technicalDetails,
    }, null, 2);

    try {
      await navigator.clipboard.writeText(details);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy error details:', err);
    }
  };

  return (
    <Card className={cn('p-4', className)}>
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            {getCategoryIcon(error.category)}
            <Badge className={getSeverityColor(error.severity)} variant="secondary">
              {error.severity.toUpperCase()}
            </Badge>
            <Badge variant="outline">{error.category}</Badge>
          </div>
          <span className="text-xs text-muted-foreground">
            {new Date(error.timestamp).toLocaleString()}
          </span>
        </div>

        {/* User Message */}
        <div>
          <h4 className="font-medium">Something went wrong</h4>
          <p className="text-sm text-muted-foreground mt-1">
            {error.userMessage || error.message}
          </p>
        </div>

        {/* Suggestions */}
        {error.suggestions && error.suggestions.length > 0 && (
          <div>
            <h5 className="font-medium text-sm mb-2">What you can try:</h5>
            <ul className="list-disc list-inside text-sm space-y-1 text-muted-foreground">
              {error.suggestions.map((suggestion, index) => (
                <li key={index}>{suggestion}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-2">
          {onRetry && error.retryable && (
            <Button variant="outline" size="sm" onClick={onRetry}>
              <RefreshCw className="h-3 w-3 mr-1" />
              Try Again
            </Button>
          )}
          
          {onReport && (
            <Button variant="outline" size="sm" onClick={() => onReport(error)}>
              <Bug className="h-3 w-3 mr-1" />
              Report Issue
            </Button>
          )}

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowDetails(!showDetails)}
          >
            {showDetails ? (
              <ChevronDown className="h-3 w-3 mr-1" />
            ) : (
              <ChevronRight className="h-3 w-3 mr-1" />
            )}
            Technical Details
          </Button>
        </div>

        {/* Expandable Technical Details */}
        {showDetails && (
          <div className="border-t pt-4 space-y-3">
            <div className="flex items-center justify-between">
              <h5 className="font-medium text-sm">Technical Information</h5>
              <Button
                variant="ghost"
                size="sm"
                onClick={copyErrorDetails}
                className="h-6 px-2"
              >
                <Copy className="h-3 w-3 mr-1" />
                {copied ? 'Copied!' : 'Copy'}
              </Button>
            </div>
            
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="font-medium">Operation:</span>
                <p className="text-muted-foreground">{error.operation}</p>
              </div>
              
              {error.code && (
                <div>
                  <span className="font-medium">Error Code:</span>
                  <p className="text-muted-foreground">{error.code}</p>
                </div>
              )}
              
              {error.statusCode && (
                <div>
                  <span className="font-medium">Status Code:</span>
                  <p className="text-muted-foreground">{error.statusCode}</p>
                </div>
              )}
              
              {error.correlationId && (
                <div>
                  <span className="font-medium">Correlation ID:</span>
                  <p className="text-muted-foreground font-mono text-xs">{error.correlationId}</p>
                </div>
              )}
            </div>

            {error.technicalDetails && (
              <div>
                <span className="font-medium text-sm">Stack Trace:</span>
                <pre className="text-xs bg-muted p-2 rounded mt-1 overflow-auto max-h-32">
                  {error.technicalDetails}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
};

// Error boundary fallback
export interface ErrorBoundaryFallbackProps {
  error: Error;
  resetError: () => void;
  className?: string;
}

export const ErrorBoundaryFallback: React.FC<ErrorBoundaryFallbackProps> = ({
  error,
  resetError,
  className
}) => {
  return (
    <div className={cn('flex flex-col items-center justify-center min-h-64 p-8', className)}>
      <div className="text-center space-y-4 max-w-md">
        <div className="mx-auto w-12 h-12 bg-red-100 rounded-full flex items-center justify-center">
          <AlertTriangle className="h-6 w-6 text-red-600" />
        </div>
        
        <div>
          <h2 className="text-lg font-semibold">Something went wrong</h2>
          <p className="text-muted-foreground mt-1">
            An unexpected error occurred. Please try refreshing the page.
          </p>
        </div>

        <details className="text-left">
          <summary className="cursor-pointer text-sm text-muted-foreground hover:text-foreground">
            View error details
          </summary>
          <pre className="text-xs bg-muted p-2 rounded mt-2 overflow-auto max-h-32">
            {error.message}
            {error.stack && `\n\n${error.stack}`}
          </pre>
        </details>

        <div className="flex gap-2">
          <Button onClick={resetError}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Try Again
          </Button>
          <Button variant="outline" onClick={() => window.location.reload()}>
            Refresh Page
          </Button>
        </div>
      </div>
    </div>
  );
};

// Empty state component
export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
  className
}) => {
  return (
    <div className={cn('flex flex-col items-center justify-center py-12 px-4', className)}>
      {icon && (
        <div className="mx-auto w-12 h-12 bg-muted rounded-full flex items-center justify-center mb-4">
          {icon}
        </div>
      )}
      
      <div className="text-center space-y-2">
        <h3 className="text-lg font-medium">{title}</h3>
        {description && (
          <p className="text-muted-foreground max-w-sm">{description}</p>
        )}
      </div>

      {action && (
        <Button onClick={action.onClick} className="mt-4">
          {action.label}
        </Button>
      )}
    </div>
  );
};

// Multi-error display for bulk operations
export interface MultiErrorDisplayProps {
  errors: EnhancedStoreError[];
  onRetryAll?: () => void;
  onRetryIndividual?: (error: EnhancedStoreError) => void;
  onDismissAll?: () => void;
  className?: string;
}

export const MultiErrorDisplay: React.FC<MultiErrorDisplayProps> = ({
  errors,
  onRetryAll,
  onRetryIndividual,
  onDismissAll,
  className
}) => {
  const [expanded, setExpanded] = React.useState(false);
  
  if (errors.length === 0) return null;

  const criticalErrors = errors.filter(e => e.severity === ErrorSeverity.CRITICAL);
  const retryableErrors = errors.filter(e => e.retryable);

  return (
    <Card className={cn('p-4', className)}>
      <div className="space-y-4">
        {/* Summary */}
        <div className="flex items-center justify-between">
          <div>
            <h4 className="font-medium">
              {errors.length} error{errors.length !== 1 ? 's' : ''} occurred
            </h4>
            {criticalErrors.length > 0 && (
              <p className="text-sm text-red-600 mt-1">
                {criticalErrors.length} critical error{criticalErrors.length !== 1 ? 's' : ''}
              </p>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            {onRetryAll && retryableErrors.length > 0 && (
              <Button variant="outline" size="sm" onClick={onRetryAll}>
                <RefreshCw className="h-3 w-3 mr-1" />
                Retry All ({retryableErrors.length})
              </Button>
            )}
            
            {onDismissAll && (
              <Button variant="ghost" size="sm" onClick={onDismissAll}>
                <X className="h-3 w-3 mr-1" />
                Dismiss
              </Button>
            )}
          </div>
        </div>

        {/* Error List Toggle */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setExpanded(!expanded)}
          className="w-full justify-between"
        >
          <span>View all errors</span>
          {expanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </Button>

        {/* Expanded Error List */}
        {expanded && (
          <div className="space-y-2 max-h-96 overflow-auto">
            {errors.map((error, index) => (
              <div key={index} className="border rounded p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge className={
                      error.severity === ErrorSeverity.CRITICAL 
                        ? 'bg-red-100 text-red-800'
                        : error.severity === ErrorSeverity.HIGH
                        ? 'bg-orange-100 text-orange-800'
                        : 'bg-yellow-100 text-yellow-800'
                    } variant="secondary">
                      {error.severity}
                    </Badge>
                    <span className="text-sm font-medium">{error.operation}</span>
                  </div>
                  
                  {onRetryIndividual && error.retryable && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onRetryIndividual(error)}
                    >
                      <RefreshCw className="h-3 w-3" />
                    </Button>
                  )}
                </div>
                
                <p className="text-sm text-muted-foreground">
                  {error.userMessage || error.message}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
};