import { addDays } from 'date-fns';
import { DateRange } from 'react-day-picker';

export type ManagerTimeframe = 'biweekly' | 'monthly';

export const buildRangeForTimeframe = (timeframe: ManagerTimeframe): DateRange => {
  const today = new Date();
  const daysBack = timeframe === 'biweekly' ? 13 : 29;
  return { from: addDays(today, -daysBack), to: today };
};

export const computeProgressValue = (activityScore: number, maxActivityScore: number): number => {
  if (maxActivityScore <= 0) {
    return activityScore > 0 ? 100 : 0;
  }
  const ratio = (activityScore / maxActivityScore) * 100;
  if (!Number.isFinite(ratio)) {
    return 0;
  }
  return Math.max(0, Math.min(Math.round(ratio), 100));
};
