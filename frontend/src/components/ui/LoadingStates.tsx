/**
 * Loading state components for different scenarios
 */

import React from 'react';
import { Skeleton } from './skeleton';
import { Card } from './card';
import { Loader2, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';

// Generic loading spinner
export interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  text?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'md',
  className,
  text
}) => {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6',
    lg: 'h-8 w-8',
  };

  return (
    <div className={cn('flex items-center justify-center gap-2', className)}>
      <Loader2 className={cn('animate-spin', sizeClasses[size])} />
      {text && <span className="text-sm text-muted-foreground">{text}</span>}
    </div>
  );
};

// Inline loading indicator for buttons/actions
export interface InlineLoadingProps {
  isLoading: boolean;
  children: React.ReactNode;
  loadingText?: string;
  className?: string;
}

export const InlineLoading: React.FC<InlineLoadingProps> = ({
  isLoading,
  children,
  loadingText,
  className
}) => {
  if (isLoading) {
    return (
      <div className={cn('flex items-center gap-2', className)}>
        <Loader2 className="h-4 w-4 animate-spin" />
        {loadingText && <span>{loadingText}</span>}
      </div>
    );
  }

  return <>{children}</>;
};

// Table loading skeleton
export interface TableLoadingProps {
  rows?: number;
  columns?: number;
  showHeader?: boolean;
  className?: string;
}

export const TableLoading: React.FC<TableLoadingProps> = ({
  rows = 5,
  columns = 4,
  showHeader = true,
  className
}) => {
  return (
    <div className={cn('space-y-2', className)}>
      {showHeader && (
        <div className="flex gap-4">
          {Array.from({ length: columns }).map((_, i) => (
            <Skeleton key={`header-${i}`} className="h-4 flex-1" />
          ))}
        </div>
      )}
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={`row-${rowIndex}`} className="flex gap-4">
          {Array.from({ length: columns }).map((_, colIndex) => (
            <Skeleton key={`cell-${rowIndex}-${colIndex}`} className="h-8 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
};

// Card loading skeleton
export interface CardLoadingProps {
  count?: number;
  showAvatar?: boolean;
  showActions?: boolean;
  className?: string;
}

export const CardLoading: React.FC<CardLoadingProps> = ({
  count = 3,
  showAvatar = false,
  showActions = true,
  className
}) => {
  return (
    <div className={cn('space-y-4', className)}>
      {Array.from({ length: count }).map((_, index) => (
        <Card key={index} className="p-4">
          <div className="space-y-3">
            <div className="flex items-center space-x-4">
              {showAvatar && <Skeleton className="h-10 w-10 rounded-full" />}
              <div className="space-y-2 flex-1">
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-3 w-3/4" />
              </div>
            </div>
            <Skeleton className="h-20 w-full" />
            {showActions && (
              <div className="flex gap-2">
                <Skeleton className="h-8 w-20" />
                <Skeleton className="h-8 w-16" />
              </div>
            )}
          </div>
        </Card>
      ))}
    </div>
  );
};

// List loading skeleton
export interface ListLoadingProps {
  items?: number;
  showIcon?: boolean;
  showSecondaryText?: boolean;
  className?: string;
}

export const ListLoading: React.FC<ListLoadingProps> = ({
  items = 5,
  showIcon = true,
  showSecondaryText = true,
  className
}) => {
  return (
    <div className={cn('space-y-3', className)}>
      {Array.from({ length: items }).map((_, index) => (
        <div key={index} className="flex items-center space-x-3">
          {showIcon && <Skeleton className="h-8 w-8 rounded" />}
          <div className="space-y-1 flex-1">
            <Skeleton className="h-4 w-3/4" />
            {showSecondaryText && <Skeleton className="h-3 w-1/2" />}
          </div>
        </div>
      ))}
    </div>
  );
};

// Form loading skeleton
export interface FormLoadingProps {
  fields?: number;
  showSubmitButton?: boolean;
  className?: string;
}

export const FormLoading: React.FC<FormLoadingProps> = ({
  fields = 4,
  showSubmitButton = true,
  className
}) => {
  return (
    <div className={cn('space-y-4', className)}>
      {Array.from({ length: fields }).map((_, index) => (
        <div key={index} className="space-y-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-10 w-full" />
        </div>
      ))}
      {showSubmitButton && (
        <div className="pt-4">
          <Skeleton className="h-10 w-32" />
        </div>
      )}
    </div>
  );
};

// Dashboard loading skeleton
export const DashboardLoading: React.FC<{ className?: string }> = ({ className }) => {
  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <div className="space-y-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-96" />
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i} className="p-4">
            <div className="space-y-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-8 w-16" />
              <Skeleton className="h-3 w-32" />
            </div>
          </Card>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-4">
          <div className="space-y-4">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-64 w-full" />
          </div>
        </Card>
        <Card className="p-4">
          <div className="space-y-4">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-64 w-full" />
          </div>
        </Card>
      </div>

      {/* Table */}
      <Card className="p-4">
        <div className="space-y-4">
          <Skeleton className="h-6 w-40" />
          <TableLoading rows={8} columns={5} />
        </div>
      </Card>
    </div>
  );
};

// Refresh loading overlay
export interface RefreshLoadingProps {
  isRefreshing: boolean;
  onRefresh?: () => void;
  className?: string;
}

export const RefreshLoading: React.FC<RefreshLoadingProps> = ({
  isRefreshing,
  onRefresh,
  className
}) => {
  return (
    <div className={cn('relative', className)}>
      {isRefreshing && (
        <div className="absolute inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center z-10">
          <div className="flex items-center gap-2 bg-background border rounded-lg px-4 py-2 shadow-lg">
            <RefreshCw className="h-4 w-4 animate-spin" />
            <span className="text-sm">Refreshing...</span>
          </div>
        </div>
      )}
    </div>
  );
};

// Optimistic update indicator
export interface OptimisticUpdateIndicatorProps {
  isPending: boolean;
  children: React.ReactNode;
  className?: string;
}

export const OptimisticUpdateIndicator: React.FC<OptimisticUpdateIndicatorProps> = ({
  isPending,
  children,
  className
}) => {
  return (
    <div className={cn('relative', isPending && 'opacity-60', className)}>
      {children}
      {isPending && (
        <div className="absolute top-2 right-2">
          <div className="h-2 w-2 bg-blue-500 rounded-full animate-pulse" />
        </div>
      )}
    </div>
  );
};

// Bulk operation progress
export interface BulkOperationProgressProps {
  total: number;
  completed: number;
  failed: number;
  inProgress: number;
  operation?: string;
  className?: string;
}

export const BulkOperationProgress: React.FC<BulkOperationProgressProps> = ({
  total,
  completed,
  failed,
  inProgress,
  operation = 'Processing',
  className
}) => {
  const percentage = total > 0 ? Math.round(((completed + failed) / total) * 100) : 0;

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex justify-between text-sm">
        <span>{operation} items...</span>
        <span>{percentage}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className="bg-blue-600 h-2 rounded-full transition-all duration-300"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Completed: {completed}</span>
        <span>Failed: {failed}</span>
        <span>In Progress: {inProgress}</span>
      </div>
    </div>
  );
};