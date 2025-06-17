import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { 
  CalendarIcon, 
  Clock, 
  GitCommit, 
  MessageSquare, 
  TrendingUp,
  FileText,
  AlertCircle
} from 'lucide-react';
import { format, startOfWeek, endOfWeek, subWeeks } from 'date-fns';
import { useApi } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

interface DailyReport {
  id: string;
  user_id: string;
  report_date: string;
  raw_text_input: string;
  clarified_tasks_summary?: string;
  ai_analysis?: {
    summary?: string;
    estimated_hours?: number;
    key_achievements?: string[];
    potential_blockers?: string[];
    sentiment?: string;
  };
  final_estimated_hours?: number;
  commit_hours?: number;
  additional_hours?: number;
  linked_commit_ids?: string[];
  deduplication_results?: any;
  conversation_state?: {
    status?: string;
    history?: Array<{
      user: string;
      ai: string;
      timestamp: string;
    }>;
  };
}

interface WeeklySummary {
  week_start: string;
  week_end: string;
  total_commit_hours: number;
  total_report_hours: number;
  total_combined_hours: number;
  daily_breakdown: Array<{
    date: string;
    commit_hours: number;
    report_hours: number;
    total_hours: number;
    has_report: boolean;
  }>;
  deduplication_summary: {
    total_duplicates: number;
    hours_saved: number;
  };
}

interface DailyReportHistoryProps {
  userId?: string;
  showWeeklySummary?: boolean;
}

export const DailyReportHistory: React.FC<DailyReportHistoryProps> = ({
  userId,
  showWeeklySummary = true
}) => {
  const { fetchApi } = useApi();
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [selectedWeek, setSelectedWeek] = useState<Date>(startOfWeek(new Date(), { weekStartsOn: 1 }));
  const [reports, setReports] = useState<DailyReport[]>([]);
  const [weeklySummary, setWeeklySummary] = useState<WeeklySummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'daily' | 'weekly'>('weekly');

  // Fetch reports for selected period
  useEffect(() => {
    if (viewMode === 'daily') {
      fetchDailyReport(selectedDate);
    } else {
      fetchWeeklySummary(selectedWeek);
    }
  }, [selectedDate, selectedWeek, viewMode, userId]);

  const fetchDailyReport = async (date: Date) => {
    setLoading(true);
    setError(null);
    try {
      const dateStr = format(date, 'yyyy-MM-dd');
      const endpoint = userId 
        ? `/api/v1/daily-reports/user/${userId}?date=${dateStr}`
        : `/api/v1/daily-reports/my?date=${dateStr}`;
      
      const response = await fetchApi(endpoint);
      setReports(response.data ? [response.data] : []);
    } catch (err) {
      setError('Failed to fetch daily report');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchWeeklySummary = async (weekStart: Date) => {
    if (!showWeeklySummary) return;
    
    setLoading(true);
    setError(null);
    try {
      const weekStartStr = format(weekStart, 'yyyy-MM-dd');
      const endpoint = userId
        ? `/api/v1/weekly-hours/summary/${userId}?week_start=${weekStartStr}`
        : `/api/v1/weekly-hours/summary/me?week_start=${weekStartStr}`;
      
      const response = await fetchApi(endpoint);
      setWeeklySummary(response.data);
    } catch (err) {
      setError('Failed to fetch weekly summary');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const renderDailyReport = (report: DailyReport) => (
    <Card key={report.id} className="mb-4">
      <CardHeader>
        <div className="flex justify-between items-start">
          <div>
            <CardTitle className="text-lg">
              {format(new Date(report.report_date), 'EEEE, MMMM d, yyyy')}
            </CardTitle>
            <CardDescription className="flex items-center gap-2 mt-1">
              <Clock className="h-4 w-4" />
              {report.final_estimated_hours?.toFixed(1) || '0'} hours
              {report.linked_commit_ids && report.linked_commit_ids.length > 0 && (
                <>
                  <GitCommit className="h-4 w-4 ml-2" />
                  {report.linked_commit_ids.length} commits
                </>
              )}
            </CardDescription>
          </div>
          <div className="flex gap-2">
            {report.ai_analysis?.sentiment && (
              <Badge variant={
                report.ai_analysis.sentiment === 'Positive' ? 'default' :
                report.ai_analysis.sentiment === 'Negative' ? 'destructive' : 'secondary'
              }>
                {report.ai_analysis.sentiment}
              </Badge>
            )}
            {report.conversation_state?.status && (
              <Badge variant="outline">
                <MessageSquare className="h-3 w-3 mr-1" />
                {report.conversation_state.status}
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Summary */}
          <div>
            <h4 className="font-medium mb-2">Summary</h4>
            <p className="text-sm text-muted-foreground">
              {report.clarified_tasks_summary || report.ai_analysis?.summary || report.raw_text_input}
            </p>
          </div>

          {/* Hours Breakdown */}
          {(report.commit_hours !== undefined || report.additional_hours !== undefined) && (
            <div>
              <h4 className="font-medium mb-2">Hours Breakdown</h4>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>From Commits:</span>
                  <span>{report.commit_hours?.toFixed(1) || '0'} hours</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Additional Work:</span>
                  <span>{report.additional_hours?.toFixed(1) || '0'} hours</span>
                </div>
                <div className="border-t pt-2 flex justify-between text-sm font-medium">
                  <span>Total:</span>
                  <span>{report.final_estimated_hours?.toFixed(1) || '0'} hours</span>
                </div>
              </div>
            </div>
          )}

          {/* Key Achievements */}
          {report.ai_analysis?.key_achievements && report.ai_analysis.key_achievements.length > 0 && (
            <div>
              <h4 className="font-medium mb-2">Key Achievements</h4>
              <ul className="list-disc list-inside space-y-1">
                {report.ai_analysis.key_achievements.map((achievement, idx) => (
                  <li key={idx} className="text-sm text-muted-foreground">{achievement}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Blockers */}
          {report.ai_analysis?.potential_blockers && report.ai_analysis.potential_blockers.length > 0 && (
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                <strong>Potential Blockers:</strong>
                <ul className="list-disc list-inside mt-1">
                  {report.ai_analysis.potential_blockers.map((blocker, idx) => (
                    <li key={idx} className="text-sm">{blocker}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}
        </div>
      </CardContent>
    </Card>
  );

  const renderWeeklySummary = () => {
    if (!weeklySummary) return null;

    const weekTotal = weeklySummary.total_combined_hours;
    const targetHours = 40; // Standard work week
    const progressPercentage = Math.min((weekTotal / targetHours) * 100, 100);

    return (
      <div className="space-y-4">
        {/* Weekly Overview Card */}
        <Card>
          <CardHeader>
            <CardTitle>Week Overview</CardTitle>
            <CardDescription>
              {format(new Date(weeklySummary.week_start), 'MMM d')} - {format(new Date(weeklySummary.week_end), 'MMM d, yyyy')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Progress Bar */}
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span>Total Hours</span>
                  <span className="font-medium">{weekTotal.toFixed(1)} / {targetHours} hours</span>
                </div>
                <Progress value={progressPercentage} className="h-2" />
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-3 gap-4 pt-4">
                <div className="text-center">
                  <GitCommit className="h-5 w-5 mx-auto mb-1 text-muted-foreground" />
                  <div className="text-2xl font-semibold">{weeklySummary.total_commit_hours.toFixed(1)}</div>
                  <div className="text-xs text-muted-foreground">Commit Hours</div>
                </div>
                <div className="text-center">
                  <FileText className="h-5 w-5 mx-auto mb-1 text-muted-foreground" />
                  <div className="text-2xl font-semibold">{weeklySummary.total_report_hours.toFixed(1)}</div>
                  <div className="text-xs text-muted-foreground">Report Hours</div>
                </div>
                <div className="text-center">
                  <TrendingUp className="h-5 w-5 mx-auto mb-1 text-muted-foreground" />
                  <div className="text-2xl font-semibold">{weeklySummary.deduplication_summary.hours_saved.toFixed(1)}</div>
                  <div className="text-xs text-muted-foreground">Hours Deduplicated</div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Daily Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle>Daily Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {weeklySummary.daily_breakdown.map((day) => (
                <div key={day.date} className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                  <div>
                    <div className="font-medium">{format(new Date(day.date), 'EEEE')}</div>
                    <div className="text-sm text-muted-foreground">{format(new Date(day.date), 'MMM d')}</div>
                  </div>
                  <div className="flex items-center gap-4">
                    {day.has_report && (
                      <Badge variant="outline" className="text-xs">
                        <FileText className="h-3 w-3 mr-1" />
                        Report
                      </Badge>
                    )}
                    <div className="text-right">
                      <div className="font-medium">{day.total_hours.toFixed(1)} hrs</div>
                      <div className="text-xs text-muted-foreground">
                        {day.commit_hours > 0 && `${day.commit_hours.toFixed(1)}h commits`}
                        {day.commit_hours > 0 && day.report_hours > 0 && ' + '}
                        {day.report_hours > 0 && `${day.report_hours.toFixed(1)}h report`}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* View Mode Toggle */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <Button
            variant={viewMode === 'daily' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setViewMode('daily')}
          >
            Daily View
          </Button>
          <Button
            variant={viewMode === 'weekly' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setViewMode('weekly')}
            disabled={!showWeeklySummary}
          >
            Weekly View
          </Button>
        </div>

        {/* Date/Week Selector */}
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" className={cn("justify-start text-left font-normal")}>
              <CalendarIcon className="mr-2 h-4 w-4" />
              {viewMode === 'daily' 
                ? format(selectedDate, 'PPP')
                : `Week of ${format(selectedWeek, 'MMM d, yyyy')}`
              }
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0">
            <Calendar
              mode="single"
              selected={viewMode === 'daily' ? selectedDate : selectedWeek}
              onSelect={(date) => {
                if (date) {
                  if (viewMode === 'daily') {
                    setSelectedDate(date);
                  } else {
                    setSelectedWeek(startOfWeek(date, { weekStartsOn: 1 }));
                  }
                }
              }}
              initialFocus
            />
          </PopoverContent>
        </Popover>
      </div>

      {/* Navigation */}
      <div className="flex justify-between">
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            if (viewMode === 'daily') {
              setSelectedDate(new Date(selectedDate.getTime() - 24 * 60 * 60 * 1000));
            } else {
              setSelectedWeek(subWeeks(selectedWeek, 1));
            }
          }}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            if (viewMode === 'daily') {
              setSelectedDate(new Date());
            } else {
              setSelectedWeek(startOfWeek(new Date(), { weekStartsOn: 1 }));
            }
          }}
        >
          Today
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            if (viewMode === 'daily') {
              setSelectedDate(new Date(selectedDate.getTime() + 24 * 60 * 60 * 1000));
            } else {
              setSelectedWeek(subWeeks(selectedWeek, -1));
            }
          }}
        >
          Next
        </Button>
      </div>

      {/* Content */}
      {loading ? (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : error ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : viewMode === 'daily' ? (
        reports.length > 0 ? (
          reports.map(renderDailyReport)
        ) : (
          <Card>
            <CardContent className="text-center py-8">
              <FileText className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
              <p className="text-muted-foreground">No report submitted for this date</p>
            </CardContent>
          </Card>
        )
      ) : (
        renderWeeklySummary()
      )}
    </div>
  );
};