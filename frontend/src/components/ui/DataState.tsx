import React from 'react';
import { Card } from './card';
import { Skeleton } from './skeleton';
import { Button } from './button';
import { ErrorAlert } from './ErrorStates';
import { cn } from '@/lib/utils';

export type DataStateKind = 'loading' | 'empty' | 'error';

interface DataStateProps {
  state: DataStateKind;
  title?: string;
  description?: string;
  className?: string;
  onRetry?: () => void;
  actionLabel?: string;
  actionHref?: string;
  onAction?: () => void;
}

/**
 * Unified visual states for async dashboard sections.
 */
export const DataState: React.FC<DataStateProps> = ({
  state,
  title,
  description,
  className,
  onRetry,
  actionLabel,
  actionHref,
  onAction
}) => {
  if (state === 'loading') {
    return (
      <Card className={cn('p-4 space-y-3', className)}>
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-6 w-40" />
        <div className="space-y-2">
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-5/6" />
          <Skeleton className="h-3 w-3/4" />
        </div>
      </Card>
    );
  }

  if (state === 'error') {
    return (
      <Card className={cn('p-4', className)}>
        <ErrorAlert error={description || 'Something went wrong'} onRetry={onRetry} />
      </Card>
    );
  }

  return (
    <Card className={cn('p-4 space-y-2 text-center', className)}>
      {title && <p className="text-sm font-medium text-foreground">{title}</p>}
      {description && <p className="text-sm text-muted-foreground">{description}</p>}
      {actionLabel && actionHref && (
        <Button asChild variant="outline" size="sm" className="mt-1">
          <a href={actionHref}>{actionLabel}</a>
        </Button>
      )}
      {actionLabel && !actionHref && onAction && (
        <Button variant="outline" size="sm" className="mt-1" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </Card>
  );
};
