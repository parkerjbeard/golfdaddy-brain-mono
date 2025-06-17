import React from 'react';
import { Card } from '@/components/ui/card';

interface RetentionData {
  [key: string]: number;
}

interface RetentionChartProps {
  title: string;
  data: RetentionData;
  className?: string;
}

export const RetentionChart: React.FC<RetentionChartProps> = ({
  title,
  data,
  className = ""
}) => {
  const entries = Object.entries(data);

  return (
    <Card className={`p-4 ${className}`}>
      <h3 className="text-sm font-medium mb-4 text-center">{title}</h3>
      <div className="grid grid-cols-4 gap-2 text-center">
        {entries.map(([period, value], index) => (
          <div key={period} className="space-y-1">
            <div className="text-xs font-medium text-muted-foreground">
              {period}
            </div>
            <div className="text-sm font-semibold">
              {typeof value === 'number' ? value.toFixed(2) : value}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}; 