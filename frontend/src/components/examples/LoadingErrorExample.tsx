/**
 * Example component demonstrating comprehensive loading states and error handling
 */

import React from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  LoadingSpinner, 
  InlineLoading, 
  TableLoading, 
  CardLoading,
  DashboardLoading,
  OptimisticUpdateIndicator,
  BulkOperationProgress
} from '@/components/ui/LoadingStates';
import {
  ErrorAlert,
  DetailedErrorCard,
  EmptyState,
  MultiErrorDisplay
} from '@/components/ui/ErrorStates';
import { 
  ErrorBoundary,
  FormErrorBoundary,
  TableErrorBoundary,
  DashboardErrorBoundary
} from '@/components/ErrorBoundary';
import { useStoreState } from '@/hooks/useStoreState';
import { useTaskSelectors, useUserSelectors } from '@/store';
import { createEnhancedError, ErrorSeverity, ErrorCategory } from '@/store/utils/errorHandling';
import { ClipboardList, Users, Plus, RefreshCw, AlertTriangle } from 'lucide-react';

export const LoadingErrorExample: React.FC = () => {
  const [currentDemo, setCurrentDemo] = React.useState<string>('loading');
  const [isLoading, setIsLoading] = React.useState(false);
  const [errors, setErrors] = React.useState<any[]>([]);
  const [bulkProgress, setBulkProgress] = React.useState({ total: 0, completed: 0, failed: 0, inProgress: 0 });

  const { filteredTasks } = useTaskSelectors();
  const { filteredUsers } = useUserSelectors();
  
  const storeState = useStoreState({
    enableOptimisticUpdates: true,
    enableErrorToasts: true,
    enableSuccessToasts: true,
  });

  // Simulate loading
  const simulateLoading = async (duration = 2000) => {
    setIsLoading(true);
    await new Promise(resolve => setTimeout(resolve, duration));
    setIsLoading(false);
  };

  // Simulate errors
  const simulateError = (type: 'network' | 'validation' | 'server' | 'authorization') => {
    const mockErrors = {
      network: createEnhancedError(
        new Error('Network connection failed'),
        'fetch-tasks',
        'task-123',
        { url: '/api/tasks', method: 'GET' }
      ),
      validation: createEnhancedError(
        { message: 'Invalid input data', statusCode: 400 },
        'create-task',
        undefined,
        { field: 'title', value: '' }
      ),
      server: createEnhancedError(
        { message: 'Internal server error', statusCode: 500 },
        'update-task',
        'task-456'
      ),
      authorization: createEnhancedError(
        { message: 'Unauthorized access', statusCode: 403 },
        'delete-task',
        'task-789'
      ),
    };

    setErrors([mockErrors[type]]);
  };

  // Simulate bulk operation
  const simulateBulkOperation = async () => {
    const total = 10;
    setBulkProgress({ total, completed: 0, failed: 0, inProgress: total });

    for (let i = 0; i < total; i++) {
      await new Promise(resolve => setTimeout(resolve, 300));
      
      // Randomly fail some operations
      const failed = Math.random() < 0.2;
      
      setBulkProgress(prev => ({
        ...prev,
        completed: failed ? prev.completed : prev.completed + 1,
        failed: failed ? prev.failed + 1 : prev.failed,
        inProgress: prev.inProgress - 1,
      }));
    }
  };

  // Simulate optimistic update
  const simulateOptimisticUpdate = async () => {
    const mockTask = {
      id: 'temp-' + Date.now(),
      title: 'New Task (Optimistic)',
      status: 'TODO' as const,
      assignee_id: 'user-1',
    };

    await storeState.executeWithOptimism(
      mockTask.id,
      mockTask,
      async () => {
        // Simulate API delay
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        // Randomly succeed or fail
        if (Math.random() < 0.7) {
          return { success: true, data: { ...mockTask, id: 'real-' + Date.now() } };
        } else {
          throw new Error('Failed to create task');
        }
      },
      {
        showSuccessToast: true,
        successMessage: 'Task created successfully!',
        showErrorToast: true,
      }
    );
  };

  const renderDemo = () => {
    switch (currentDemo) {
      case 'loading':
        return (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-medium mb-4">Loading States</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card className="p-4">
                  <h4 className="font-medium mb-2">Spinner Variants</h4>
                  <div className="space-y-3">
                    <LoadingSpinner size="sm" text="Small spinner" />
                    <LoadingSpinner size="md" text="Medium spinner" />
                    <LoadingSpinner size="lg" text="Large spinner" />
                  </div>
                </Card>
                
                <Card className="p-4">
                  <h4 className="font-medium mb-2">Inline Loading</h4>
                  <div className="space-y-3">
                    <InlineLoading isLoading={isLoading} loadingText="Processing...">
                      <Button onClick={() => simulateLoading()}>
                        Click me
                      </Button>
                    </InlineLoading>
                    
                    <InlineLoading isLoading={false}>
                      <Button variant="outline">
                        Normal button
                      </Button>
                    </InlineLoading>
                  </div>
                </Card>
              </div>
            </div>

            <div>
              <h4 className="font-medium mb-2">Table Loading</h4>
              <TableLoading rows={3} columns={4} />
            </div>

            <div>
              <h4 className="font-medium mb-2">Card Loading</h4>
              <CardLoading count={2} showAvatar={true} />
            </div>

            <div>
              <h4 className="font-medium mb-2">Optimistic Updates</h4>
              <div className="space-y-2">
                {storeState.getPendingUpdateIds().map(id => (
                  <OptimisticUpdateIndicator key={id} isPending={true}>
                    <Card className="p-3">
                      <p>Task {id} (pending update)</p>
                    </Card>
                  </OptimisticUpdateIndicator>
                ))}
                
                <Button onClick={simulateOptimisticUpdate}>
                  <Plus className="h-4 w-4 mr-2" />
                  Create Task (Optimistic)
                </Button>
              </div>
            </div>

            <div>
              <h4 className="font-medium mb-2">Bulk Operation Progress</h4>
              <BulkOperationProgress
                total={bulkProgress.total}
                completed={bulkProgress.completed}
                failed={bulkProgress.failed}
                inProgress={bulkProgress.inProgress}
                operation="Creating tasks"
              />
              <Button onClick={simulateBulkOperation} className="mt-2">
                Start Bulk Operation
              </Button>
            </div>
          </div>
        );

      case 'errors':
        return (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-medium mb-4">Error States</h3>
              
              <div className="grid grid-cols-2 gap-2 mb-4">
                <Button size="sm" onClick={() => simulateError('network')}>
                  Network Error
                </Button>
                <Button size="sm" onClick={() => simulateError('validation')}>
                  Validation Error
                </Button>
                <Button size="sm" onClick={() => simulateError('server')}>
                  Server Error
                </Button>
                <Button size="sm" onClick={() => simulateError('authorization')}>
                  Auth Error
                </Button>
              </div>

              {errors.length > 0 && (
                <div className="space-y-4">
                  <ErrorAlert
                    error={errors[0]}
                    onRetry={() => console.log('Retrying...')}
                    onDismiss={() => setErrors([])}
                  />
                  
                  <DetailedErrorCard
                    error={errors[0]}
                    onRetry={() => console.log('Retrying...')}
                    onReport={(error) => console.log('Reporting error:', error)}
                  />
                </div>
              )}

              {errors.length > 1 && (
                <MultiErrorDisplay
                  errors={errors}
                  onRetryAll={() => console.log('Retrying all...')}
                  onDismissAll={() => setErrors([])}
                />
              )}
            </div>

            <div>
              <h4 className="font-medium mb-2">Empty States</h4>
              <EmptyState
                icon={<ClipboardList className="h-6 w-6" />}
                title="No tasks found"
                description="Get started by creating your first task."
                action={{
                  label: 'Create Task',
                  onClick: () => console.log('Creating task...'),
                }}
              />
            </div>
          </div>
        );

      case 'boundaries':
        return (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-medium mb-4">Error Boundaries</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormErrorBoundary>
                  <Card className="p-4">
                    <h4 className="font-medium mb-2">Form with Error Boundary</h4>
                    <Button 
                      onClick={() => {
                        throw new Error('Form component crashed!');
                      }}
                      variant="destructive"
                      size="sm"
                    >
                      Trigger Form Error
                    </Button>
                  </Card>
                </FormErrorBoundary>

                <TableErrorBoundary>
                  <Card className="p-4">
                    <h4 className="font-medium mb-2">Table with Error Boundary</h4>
                    <Button 
                      onClick={() => {
                        throw new Error('Table component crashed!');
                      }}
                      variant="destructive"
                      size="sm"
                    >
                      Trigger Table Error
                    </Button>
                  </Card>
                </TableErrorBoundary>
              </div>
            </div>
          </div>
        );

      case 'dashboard':
        return (
          <DashboardErrorBoundary>
            <DashboardLoading />
          </DashboardErrorBoundary>
        );

      default:
        return null;
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-2">Loading States & Error Handling Demo</h2>
        <p className="text-muted-foreground">
          Comprehensive examples of loading states, error handling, and optimistic updates.
        </p>
      </div>

      {/* Demo Navigation */}
      <div className="flex gap-2 flex-wrap">
        {[
          { key: 'loading', label: 'Loading States', icon: <RefreshCw className="h-4 w-4" /> },
          { key: 'errors', label: 'Error Handling', icon: <AlertTriangle className="h-4 w-4" /> },
          { key: 'boundaries', label: 'Error Boundaries', icon: <AlertTriangle className="h-4 w-4" /> },
          { key: 'dashboard', label: 'Dashboard Demo', icon: <Users className="h-4 w-4" /> },
        ].map(({ key, label, icon }) => (
          <Button
            key={key}
            variant={currentDemo === key ? 'default' : 'outline'}
            size="sm"
            onClick={() => setCurrentDemo(key)}
          >
            {icon}
            {label}
          </Button>
        ))}
      </div>

      {/* Store State Debug Info */}
      <Card className="p-4 bg-muted/50">
        <h4 className="font-medium mb-2">Store State Debug</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="font-medium">Loading:</span>
            <Badge variant={storeState.isLoading ? 'default' : 'outline'} className="ml-2">
              {storeState.isLoading ? 'Yes' : 'No'}
            </Badge>
          </div>
          <div>
            <span className="font-medium">Errors:</span>
            <Badge variant={storeState.hasErrors ? 'destructive' : 'outline'} className="ml-2">
              {storeState.getAllErrors().length}
            </Badge>
          </div>
          <div>
            <span className="font-medium">Optimistic:</span>
            <Badge variant={storeState.hasPendingUpdates ? 'default' : 'outline'} className="ml-2">
              {storeState.getPendingUpdateIds().length}
            </Badge>
          </div>
          <div>
            <span className="font-medium">Tasks:</span>
            <Badge variant="outline" className="ml-2">
              {filteredTasks.length}
            </Badge>
          </div>
        </div>
      </Card>

      {/* Demo Content */}
      <ErrorBoundary>
        {renderDemo()}
      </ErrorBoundary>
    </div>
  );
};