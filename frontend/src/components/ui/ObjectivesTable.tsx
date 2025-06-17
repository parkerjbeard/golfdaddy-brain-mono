import React from 'react';
import { Card } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { ZapierObjective } from '@/services/zapierApi';

interface ObjectivesTableProps {
  objectives: ZapierObjective[];
  className?: string;
}

export const ObjectivesTable: React.FC<ObjectivesTableProps> = ({
  objectives,
  className = ""
}) => {
  const getProgressColor = (percentage: number) => {
    if (percentage >= 100) return 'bg-red-500';
    if (percentage >= 75) return 'bg-orange-500';
    if (percentage >= 17) return 'bg-green-500';
    return 'bg-gray-400';
  };

  const isOverdue = (dueDate: string) => {
    const today = new Date();
    const due = new Date(dueDate);
    return due < today;
  };

  return (
    <Card className={`p-6 ${className}`}>
      <h3 className="text-lg font-medium mb-6 text-center bg-slate-700 text-white py-2 rounded">
        Current Objectives
      </h3>
      
      <div className="space-y-1">
        {/* Header */}
        <div className="grid grid-cols-5 gap-4 text-sm font-medium text-muted-foreground py-2 border-b">
          <div>Objective</div>
          <div className="text-center">Key Results</div>
          <div className="text-center">%</div>
          <div className="text-center">Deadline</div>
          <div className="text-center">Owner</div>
        </div>
        
        {/* Objectives */}
        {objectives.map((objective) => (
          <div key={objective.id} className="grid grid-cols-5 gap-4 items-center py-3 border-b last:border-b-0">
            <div className="text-sm font-medium">
              {objective.name}
            </div>
            
            <div className="flex items-center space-x-2">
              <div className="flex-1">
                <Progress 
                  value={objective.completion_percentage} 
                  className="h-6"
                  style={{
                    '--progress-background': getProgressColor(objective.completion_percentage)
                  } as React.CSSProperties}
                />
              </div>
            </div>
            
            <div className="text-center text-sm font-semibold">
              {objective.completion_percentage}%
            </div>
            
            <div className={`text-center text-sm ${isOverdue(objective.due_date) ? 'text-red-600 font-bold' : ''}`}>
              {objective.due_date}
            </div>
            
            <div className="text-center">
              <Badge variant="outline" className="text-xs">
                {objective.owner}
              </Badge>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}; 