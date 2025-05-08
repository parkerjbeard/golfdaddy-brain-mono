import React, { useState, useEffect, useMemo } from 'react';
import { User, UserPerformanceSummary, PerformanceSummaryParams } from '@/types/managerDashboard';
import { getUsers, getUserPerformanceSummary } from '@/lib/apiService';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableCaption, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DateRangePicker } from "@/components/ui/date-range-picker"; // Assuming you have or will add this
import { addDays, format } from 'date-fns';
import { DateRange } from 'react-day-picker';
import { useAuth } from '@/hooks/useAuth'; // Import useAuth

const ManagerDashboardPage: React.FC = () => {
  const { token } = useAuth(); // Get token from useAuth
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string | undefined>(undefined);
  const [dateRange, setDateRange] = useState<DateRange | undefined>(() => {
    const today = new Date();
    return {
      from: addDays(today, -7),
      to: today,
    };
  });
  const [performanceData, setPerformanceData] = useState<UserPerformanceSummary | null>(null);
  const [isLoadingUsers, setIsLoadingUsers] = useState<boolean>(false);
  const [isLoadingSummary, setIsLoadingSummary] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchUsers = async () => {
      setIsLoadingUsers(true);
      try {
        if (!token) {
          setError('Authentication token not found. Cannot fetch users.');
          setIsLoadingUsers(false);
          return;
        }
        // Assuming getUsers can fetch all relevant users or those with a 'DEVELOPER' role
        const fetchedUsers = await getUsers(token); // Pass token to getUsers
        setUsers(fetchedUsers);
        if (fetchedUsers.length > 0) {
          // setSelectedUserId(fetchedUsers[0].id); // Auto-select first user
        }
      } catch (err) {
        let message = 'Failed to fetch users.';
        if (err instanceof Error) {
          message += ` Details: ${err.message}`;
        }
        setError(message);
        console.error('Error fetching users:', err);
      }
      setIsLoadingUsers(false);
    };
    fetchUsers();
  }, [token]);

  const handleFetchSummary = async () => {
    if (!selectedUserId || !dateRange?.from) {
      setError('Please select a user and a date range.');
      return;
    }
    if (!token) {
      setError('Authentication token not found. Cannot fetch summary.');
      return;
    }
    setIsLoadingSummary(true);
    setError(null);
    setPerformanceData(null);
    try {
      const params: PerformanceSummaryParams = {
        userId: selectedUserId,
        startDate: format(dateRange.from, 'yyyy-MM-dd'),
        endDate: dateRange.to ? format(dateRange.to, 'yyyy-MM-dd') : format(dateRange.from, 'yyyy-MM-dd'),
      };
      const summary = await getUserPerformanceSummary(token, params); // Pass token to getUserPerformanceSummary
      setPerformanceData(summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch performance summary.');
      console.error(err);
    }
    setIsLoadingSummary(false);
  };
  
  // Memoize derived values for display
  const periodString = useMemo(() => {
    if (!dateRange?.from) return "";
    const fromDate = format(dateRange.from, 'MMM dd, yyyy');
    const toDate = dateRange.to ? format(dateRange.to, 'MMM dd, yyyy') : fromDate;
    return `${fromDate} - ${toDate}`;
  }, [dateRange]);

  return (
    <div className="container mx-auto p-4 md:p-8 space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Manager Performance Dashboard</CardTitle>
          <CardDescription>Review team member performance metrics.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 md:flex md:space-y-0 md:space-x-4 items-end">
          <div className='flex-grow md:flex-grow-0 md:w-1/3'>
            <label htmlFor="user-select" className="block text-sm font-medium text-gray-700 mb-1">Select User</label>
            {isLoadingUsers ? (
              <p>Loading users...</p>
            ) : users.length > 0 ? (
              <Select value={selectedUserId} onValueChange={setSelectedUserId}>
                <SelectTrigger id="user-select">
                  <SelectValue placeholder="Select a user" />
                </SelectTrigger>
                <SelectContent>
                  {users.map((user) => (
                    <SelectItem key={user.id} value={user.id}>
                      {user.name || user.email || user.id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <p>No users available or failed to load.</p>
            )}
          </div>
          <div className='flex-grow md:flex-grow-0 md:w-1/3'>
             <label htmlFor="date-range-picker" className="block text-sm font-medium text-gray-700 mb-1">Select Period</label>
            {/* If you don't have DateRangePicker yet, you can use a simple period selector first */}
            {/* For now, a placeholder. Replace with actual DateRangePicker from shadcn/ui or similar */}
            <DateRangePicker
              id="date-range-picker"
              date={dateRange}
              onDateChange={setDateRange}
              // You might need to add a className prop here if you want to style it, e.g., className="w-full"
            />
            {/* 
            <div className="p-2 border rounded-md text-center">
                {dateRange?.from ? (
                    `${format(dateRange.from, "LLL dd, y")} - ${dateRange.to ? format(dateRange.to, "LLL dd, y") : "..."}`
                ) : (
                    <span>Pick a date range</span>
                )}
            </div>
             <p className="text-xs text-muted-foreground mt-1">DateRangePicker component to be integrated here.</p>
            */}
          </div>
          <Button onClick={handleFetchSummary} disabled={isLoadingSummary || !selectedUserId || !dateRange?.from}>
            {isLoadingSummary ? 'Loading Summary...' : 'Get Summary'}
          </Button>
        </CardContent>
      </Card>

      {error && (
        <Card className="bg-destructive/10 border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive">Error</CardTitle>
          </CardHeader>
          <CardContent>
            <p>{error}</p>
          </CardContent>
        </Card>
      )}

      {performanceData && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Performance Overview for {users.find(u => u.id === selectedUserId)?.name}</CardTitle>
              <CardDescription>Period: {periodString}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <Card>
                <CardHeader><CardTitle className="text-sm font-medium">Total EOD Reported Hours</CardTitle></CardHeader>
                <CardContent><p className="text-2xl font-bold">{performanceData.total_eod_reported_hours.toFixed(2)}</p></CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle className="text-sm font-medium">Total Commits</CardTitle></CardHeader>
                <CardContent><p className="text-2xl font-bold">{performanceData.total_commits_in_period}</p></CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle className="text-sm font-medium">AI Estimated Commit Hours</CardTitle></CardHeader>
                <CardContent><p className="text-2xl font-bold">{performanceData.total_commit_ai_estimated_hours.toFixed(2)}</p></CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle className="text-sm font-medium">Avg. Commit Seniority</CardTitle></CardHeader>
                <CardContent><p className="text-2xl font-bold">{performanceData.average_commit_seniority_score.toFixed(2)} / 10</p></CardContent>
              </Card>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>EOD Report Details</CardTitle>
            </CardHeader>
            <CardContent>
              {performanceData.eod_report_details.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead className="text-right">Reported Hours</TableHead>
                      <TableHead>AI Summary</TableHead>
                      <TableHead className="text-right">AI Est. Hours</TableHead>
                      <TableHead className="text-right">Clarifications</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {performanceData.eod_report_details.map((eod, index) => (
                      <TableRow key={index}>
                        <TableCell>{eod.report_date}</TableCell>
                        <TableCell className="text-right">{eod.reported_hours.toFixed(2)}</TableCell>
                        <TableCell className="max-w-xs truncate" title={eod.ai_summary || ''}>{eod.ai_summary || 'N/A'}</TableCell>
                        <TableCell className="text-right">{eod.ai_estimated_hours.toFixed(2)}</TableCell>
                        <TableCell className="text-right">{eod.clarification_requests_count}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p>No EOD reports found for this period.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Commit Comparison Insights</CardTitle>
              <CardDescription>Highlights from comparing EOD reports with commit analysis.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {performanceData.commit_comparison_insights.length > 0 ? (
                performanceData.commit_comparison_insights.map((insight, index) => (
                  <Card key={index} className="bg-muted/50">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-medium">Commit: {insight.commit_hash.substring(0, 7)}...</CardTitle>
                      <CardDescription className="text-xs">{insight.commit_timestamp}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <pre className="whitespace-pre-wrap text-xs p-2 bg-background rounded-md">{insight.notes}</pre>
                    </CardContent>
                  </Card>
                ))
              ) : (
                <p>No commit comparison insights available for this period.</p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default ManagerDashboardPage; 