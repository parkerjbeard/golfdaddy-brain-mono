import { HTMLAttributes, forwardRef } from 'react';
import { Card } from './card';
import { cn } from '@/lib/utils';

export interface KpiCardProps extends HTMLAttributes<HTMLDivElement> {
  title: string;
  value: string | number;
  description?: string;
  trend?: 'up' | 'down' | 'neutral';
  percentageChange?: number;
}

const KpiCard = forwardRef<HTMLDivElement, KpiCardProps>(
  ({ className, title, value, description, trend = 'neutral', percentageChange, ...props }, ref) => {
    const trendColor =
      trend === 'up' ? 'text-green-500' : trend === 'down' ? 'text-red-500' : 'text-muted-foreground';
    const trendIcon =
      trend === 'up' ? '▲' : trend === 'down' ? '▼' : '';

    return (
      <Card ref={ref} className={cn('flex flex-col gap-4', className)} {...props}>
        <div>
          <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
          <div className="text-2xl font-semibold tracking-tight">{value}</div>
        </div>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
        {percentageChange !== undefined && (
          <div className="flex items-center text-sm">
            <span className={cn('mr-1 font-medium', trendColor)}>{trendIcon}</span>
            <span>{percentageChange}%</span>
          </div>
        )}
      </Card>
    );
  }
);

KpiCard.displayName = 'KpiCard';

export { KpiCard };
