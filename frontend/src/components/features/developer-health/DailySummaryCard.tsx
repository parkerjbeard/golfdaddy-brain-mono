import React from 'react';
import { DeveloperDailySummary } from '@/services/developerInsightsApi';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertCircle, CheckCircle, Clock, BarChart } from 'lucide-react';

interface DailySummaryCardProps {
  summary: DeveloperDailySummary | null;
  isLoading: boolean;
  error: Error | null;
}

const DailySummaryCard: React.FC<DailySummaryCardProps> = ({ summary, isLoading, error }) => {
  if (isLoading) {
    return <Card className="animate-pulse"><CardHeader><div className="h-6 bg-gray-300 rounded w-3/4"></div></CardHeader><CardContent><div className="h-4 bg-gray-300 rounded w-full mb-2"></div><div className="h-4 bg-gray-300 rounded w-5/6"></div></CardContent></Card>;
  }

  if (error) {
    return (
      <Card className="border-destructive">
        <CardHeader className="text-destructive">
          <CardTitle className="flex items-center"><AlertCircle className="mr-2" /> Error Loading Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <p>{error.message}</p>
        </CardContent>
      </Card>
    );
  }

  if (!summary) {
    return <Card><CardContent><p className="pt-6 text-center text-gray-500">No summary data available for the selected date.</p></CardContent></Card>;
  }

  const avgSeniorityText = summary.average_seniority_score !== null && summary.average_seniority_score !== undefined 
    ? `${summary.average_seniority_score.toFixed(1)} / 10` 
    : 'N/A';

  return (
    <Card className={summary.low_seniority_flag ? 'border-yellow-500' : ''}>
      <CardHeader>
        <CardTitle className="text-lg">Daily Summary - {summary.report_date}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="flex items-center">
            <Clock className="mr-2 h-4 w-4 text-gray-500" />
            <span>Total Hours:</span>
            <span className="font-semibold ml-auto">{summary.total_estimated_hours.toFixed(1)} h</span>
          </div>
          <div className="flex items-center">
            <BarChart className="mr-2 h-4 w-4 text-gray-500" />
            <span>Avg. Seniority:</span>
            <span className={`font-semibold ml-auto ${summary.low_seniority_flag ? 'text-yellow-600' : ''}`}>
              {avgSeniorityText}
              {summary.low_seniority_flag && <AlertCircle className="inline-block ml-1 h-4 w-4 text-yellow-500" title="Low average seniority score" />}            
            </span>
          </div>
          <div className="flex items-center">
            <Clock className="mr-2 h-4 w-4 text-gray-500" />
            <span>Commit Hours:</span>
            <span className="font-semibold ml-auto">{summary.commit_estimated_hours.toFixed(1)} h</span>
          </div>
           <div className="flex items-center">
            <span className="font-semibold">(from {summary.commit_count} commits)</span>
          </div>
          <div className="flex items-center">
            <Clock className="mr-2 h-4 w-4 text-gray-500" />
            <span>EOD Hours:</span>
            <span className="font-semibold ml-auto">{summary.eod_estimated_hours.toFixed(1)} h</span>
          </div>
        </div>
        {summary.eod_summary && (
          <div className="pt-4 border-t">
            <h4 className="text-sm font-medium mb-1">EOD Report Summary:</h4>
            <p className="text-xs text-gray-600 italic">{summary.eod_summary}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default DailySummaryCard; 