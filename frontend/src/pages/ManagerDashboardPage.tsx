import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { User, UserPerformanceSummary, PerformanceSummaryParams, UserWidgetSummary } from '@/types/managerDashboard';
import { getUsers, getUserPerformanceSummary, getBulkWidgetSummaries } from '@/lib/apiService';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableCaption, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DateRangePicker } from "@/components/ui/date-range-picker";
import { addDays, format, isEqual } from 'date-fns';
import { DateRange } from 'react-day-picker';
import { useAuth } from '@/hooks/useAuth';
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

const ManagerDashboardPage: React.FC = () => {
  const { token } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string | undefined>(undefined);

  // Global date range state for the widget's summary stat
  const [globalDateRange, setGlobalDateRange] = useState<DateRange | undefined>(() => {
    const today = new Date();
    return { from: addDays(today, -7), to: today };
  });
  // Stores the date range that has been *confirmed* for global use
  const [confirmedGlobalDateRange, setConfirmedGlobalDateRange] = useState<DateRange | undefined>(globalDateRange);

  // Widget-specific state
  const [userWidgetsData, setUserWidgetsData] = useState<UserWidgetSummary[]>([]);
  const [isLoadingWidgets, setIsLoadingWidgets] = useState<boolean>(false);
  const [errorWidgets, setErrorWidgets] = useState<string | null>(null);

  // Focused detailed view state
  const [showFocusedViewForUserId, setShowFocusedViewForUserId] = useState<string | null>(null);
  const [focusedUserPerformanceData, setFocusedUserPerformanceData] = useState<UserPerformanceSummary | null>(null);
  const [focusedUserDateRange, setFocusedUserDateRange] = useState<DateRange | undefined>(undefined);
   // Stores the date range that has been *confirmed* for the focused view
  const [confirmedFocusedDateRange, setConfirmedFocusedDateRange] = useState<DateRange | undefined>(undefined);
  const [isLoadingFocusedSummary, setIsLoadingFocusedSummary] = useState<boolean>(false);
  const [errorFocusedSummary, setErrorFocusedSummary] = useState<string | null>(null);
  
  const [isLoadingUsers, setIsLoadingUsers] = useState<boolean>(false);
  const [errorUsers, setErrorUsers] = useState<string | null>(null);


  // Fetch users
  useEffect(() => {
    const fetchUsersList = async () => {
      setIsLoadingUsers(true);
      setErrorUsers(null);
      try {
        if (!token) {
          setErrorUsers('Authentication token not found.');
          setIsLoadingUsers(false);
          return;
        }
        const fetchedUsers = await getUsers(token);
        setUsers(fetchedUsers);
        // Do not auto-select user, let manager choose
      } catch (err) {
        setErrorUsers(err instanceof Error ? err.message : 'Failed to fetch users.');
        console.error('Error fetching users:', err);
      }
      setIsLoadingUsers(false);
    };
    fetchUsersList();
  }, [token]);

  // Fetch BULK WIDGET data
  const fetchBulkWidgetData = useCallback(async (dateRangeToUse: DateRange | undefined) => {
    if (!dateRangeToUse?.from || !token) {
      setUserWidgetsData([]);
      setErrorWidgets(token ? 'Date range is required for bulk widget data.' : 'Authentication token not found.');
      return;
    }
    setIsLoadingWidgets(true);
    setErrorWidgets(null);
    try {
      const params = {
        startDate: format(dateRangeToUse.from, 'yyyy-MM-dd'),
        endDate: dateRangeToUse.to ? format(dateRangeToUse.to, 'yyyy-MM-dd') : format(dateRangeToUse.from, 'yyyy-MM-dd'),
      };
      const summaries = await getBulkWidgetSummaries(token, params);
      setUserWidgetsData(summaries);
    } catch (err) {
      setErrorWidgets(err instanceof Error ? err.message : 'Failed to fetch bulk widget summaries.');
      setUserWidgetsData([]);
    }
    setIsLoadingWidgets(false);
  }, [token]);

  // Effect to fetch bulk widget data when confirmed global date range changes
  useEffect(() => {
    if (confirmedGlobalDateRange) {
      fetchBulkWidgetData(confirmedGlobalDateRange);
    }
  }, [confirmedGlobalDateRange, fetchBulkWidgetData]);

  // Fetch data for the FOCUSED DETAILED VIEW
  const fetchFocusedUserData = useCallback(async (userId: string, dateRangeToUse: DateRange | undefined) => {
    if (!userId || !dateRangeToUse?.from) {
      setErrorFocusedSummary('User ID and date range are required for detailed view.');
      setFocusedUserPerformanceData(null);
      return;
    }
     if (!token) {
      setErrorFocusedSummary('Authentication token not found.');
      return;
    }

    setIsLoadingFocusedSummary(true);
    setErrorFocusedSummary(null);
    try {
      const params: PerformanceSummaryParams = {
        userId: userId,
        startDate: format(dateRangeToUse.from, 'yyyy-MM-dd'),
        endDate: dateRangeToUse.to ? format(dateRangeToUse.to, 'yyyy-MM-dd') : format(dateRangeToUse.from, 'yyyy-MM-dd'),
      };
      const summary = await getUserPerformanceSummary(token, params);
      setFocusedUserPerformanceData(summary);
    } catch (err) {
      setErrorFocusedSummary(err instanceof Error ? err.message : 'Failed to fetch detailed performance summary.');
      console.error('Error fetching focused user data:', err);
      setFocusedUserPerformanceData(null);
    }
    setIsLoadingFocusedSummary(false);
  }, [token]);

  // Effect to fetch focused data when the focused user or its *confirmed* date range changes
  useEffect(() => {
    if (showFocusedViewForUserId && confirmedFocusedDateRange) {
      fetchFocusedUserData(showFocusedViewForUserId, confirmedFocusedDateRange);
    }
  }, [showFocusedViewForUserId, confirmedFocusedDateRange, fetchFocusedUserData]);


  // Handler for Global Confirm Date Change button
  const handleGlobalDateConfirm = () => {
    setConfirmedGlobalDateRange(globalDateRange);
    // If a focused view is open, re-sync its date range and trigger its refetch
    if (showFocusedViewForUserId) {
      setFocusedUserDateRange(globalDateRange);
      setConfirmedFocusedDateRange(globalDateRange);
    }
  };

  // Handler for clicking a widget
  const handleWidgetClick = (userId: string) => {
    setShowFocusedViewForUserId(userId);
    setFocusedUserDateRange(confirmedGlobalDateRange);
    setConfirmedFocusedDateRange(confirmedGlobalDateRange);
    setFocusedUserPerformanceData(null);
  };

  // Handler for Internal (Focused View) Confirm Date Change button
  const handleFocusedDateConfirm = () => {
    setConfirmedFocusedDateRange(focusedUserDateRange);
  };
  
  const getPeriodString = useCallback((dateRangeToFormat: DateRange | undefined) => {
    if (!dateRangeToFormat?.from) return "N/A";
    const fromDate = format(dateRangeToFormat.from, 'MMM dd, yyyy');
    const toDate = dateRangeToFormat.to ? format(dateRangeToFormat.to, 'MMM dd, yyyy') : fromDate;
    return `${fromDate} - ${toDate}`;
  }, []);


  const selectedUserName = useMemo(() => users.find(u => u.id === selectedUserId)?.name || "Selected User", [users, selectedUserId]);
  const focusedUserName = useMemo(() => {
    const widgetUser = userWidgetsData.find(w => w.user_id === showFocusedViewForUserId);
    if (widgetUser?.name) return widgetUser.name;
    const generalUser = users.find(u => u.id === showFocusedViewForUserId);
    return generalUser?.name || "Focused User";
  }, [users, userWidgetsData, showFocusedViewForUserId]);

  return (
    <div className="container mx-auto p-4 md:p-8 space-y-6">
      {/* Controls Section */}
      <Card>
        <CardHeader>
          <CardTitle>Manager Performance Dashboard</CardTitle>
          <CardDescription>Set a global date range to view performance widgets for all developers.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 md:flex md:space-y-0 md:space-x-4 items-end">
          <div className='flex-grow md:flex-grow-0 md:w-1/2'>
            <label htmlFor="global-date-range-picker" className="block text-sm font-medium text-gray-700 mb-1">Global Date Range (for Widgets)</label>
            <DateRangePicker id="global-date-range-picker" date={globalDateRange} onDateChange={setGlobalDateRange} />
          </div>
          <Button onClick={handleGlobalDateConfirm} disabled={!globalDateRange?.from || isLoadingWidgets}>
            {isLoadingWidgets ? 'Loading Widgets...' : 'Confirm Global Date'}
          </Button>
        </CardContent>
      </Card>

      {/* User Widgets Display Section */}
      {isLoadingUsers && <p className="text-center py-4">Loading users...</p>}
      {errorUsers && <Card className="bg-destructive/10 border-destructive"><CardHeader><CardTitle className="text-destructive">Error Loading Users</CardTitle></CardHeader><CardContent><p>{errorUsers}</p></CardContent></Card>}
      
      {!isLoadingUsers && !errorUsers && users.length === 0 && (
        <p className="text-center py-4">No users found.</p>
      )}

      {!isLoadingUsers && !errorUsers && users.length > 0 && isLoadingWidgets && <p className="text-center py-4">Loading performance widgets...</p>}
      {!isLoadingUsers && !errorUsers && users.length > 0 && errorWidgets && <Card className="bg-destructive/10 border-destructive"><CardHeader><CardTitle className="text-destructive">Error Loading Widgets</CardTitle></CardHeader><CardContent><p>{errorWidgets}</p></CardContent></Card>}
      
      {!isLoadingWidgets && !errorWidgets && users.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {users.map((user) => {
            const widgetData = userWidgetsData.find(w => w.user_id === user.id);
            const userName = widgetData?.name || user.name || 'Unknown User';
            const userAvatarUrl = widgetData?.avatar_url || undefined; // Corrected: User type does not have avatarUrl

            if (widgetData) {
              return (
                <Card 
                  key={user.id}
                  onClick={() => handleWidgetClick(user.id)} 
                  className="cursor-pointer hover:shadow-lg transition-shadow flex flex-col"
                >
                  <CardHeader className="flex-row items-center space-x-4 pb-2">
                    <Avatar>
                      <AvatarImage src={userAvatarUrl} alt={userName} />
                      <AvatarFallback>{userName.charAt(0).toUpperCase()}</AvatarFallback>
                    </Avatar>
                    <div>
                      <CardTitle className="text-lg">{userName}</CardTitle>
                      <CardDescription className="text-xs">ID: {user.id.substring(0,8)}...</CardDescription>
                    </div>
                  </CardHeader>
                  <CardContent className="flex-grow flex flex-col justify-center items-center">
                    <h3 className="text-sm font-medium text-muted-foreground">AI Est. Commit Hours</h3>
                    <p className="text-2xl font-bold">{widgetData.total_ai_estimated_commit_hours.toFixed(2)}</p>
                    <p className="text-xs text-muted-foreground mt-1">Period: {getPeriodString(confirmedGlobalDateRange)}</p>
                  </CardContent>
                  <CardFooter className="text-xs text-center block pt-2 border-t mt-2">
                       Click to view details
                  </CardFooter>
                </Card>
              );
            } else {
              // Card for user with no widget data
              return (
                <Card key={user.id} className="flex flex-col bg-muted/30">
                  <CardHeader className="flex-row items-center space-x-4 pb-2">
                    <Avatar>
                      <AvatarImage src={userAvatarUrl} alt={userName} />
                      <AvatarFallback>{userName.charAt(0).toUpperCase()}</AvatarFallback>
                    </Avatar>
                    <div>
                      <CardTitle className="text-lg">{userName}</CardTitle>
                      <CardDescription className="text-xs">ID: {user.id.substring(0,8)}...</CardDescription>
                    </div>
                  </CardHeader>
                  <CardContent className="flex-grow flex flex-col justify-center items-center">
                    <p className="text-sm text-muted-foreground">No performance data available</p>
                    <p className="text-xs text-muted-foreground mt-1">for {getPeriodString(confirmedGlobalDateRange)}</p>
                  </CardContent>
                   <CardFooter className="text-xs text-center block pt-2 border-t mt-2 text-muted-foreground">
                       Date range confirmed
                  </CardFooter>
                </Card>
              );
            }
          })}
        </div>
      )}

      {/* Focused Detailed Stats View */}
      {showFocusedViewForUserId && (
        <div className="space-y-6 border-t-2 border-primary pt-6 mt-10">
          <Card>
            <CardHeader>
              <CardTitle>Detailed Performance for {focusedUserName}</CardTitle>
               <CardDescription>Use the date picker below to analyze a specific period for this user.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 md:flex md:space-y-0 md:space-x-4 items-end">
                <div className='flex-grow md:flex-grow-0 md:w-1/3'>
                    <label htmlFor="focused-date-range-picker" className="block text-sm font-medium text-gray-700 mb-1">Focused Date Range</label>
                    <DateRangePicker id="focused-date-range-picker" date={focusedUserDateRange} onDateChange={setFocusedUserDateRange}/>
                </div>
                <Button onClick={handleFocusedDateConfirm} disabled={isLoadingFocusedSummary || !focusedUserDateRange?.from}>
                    {isLoadingFocusedSummary ? 'Loading Details...' : 'Confirm Focused Date'}
                </Button>
            </CardContent>
          </Card>

          {isLoadingFocusedSummary && <p className="text-center py-4">Loading detailed summary for {focusedUserName}...</p>}
          {errorFocusedSummary && <Card className="bg-destructive/10 border-destructive"><CardHeader><CardTitle className="text-destructive">Error Loading Details</CardTitle></CardHeader><CardContent><p>{errorFocusedSummary}</p></CardContent></Card>}
          
          {focusedUserPerformanceData && (
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Performance Overview</CardTitle>
                  <CardDescription>Period: {getPeriodString(confirmedFocusedDateRange)}</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  <Card><CardHeader><CardTitle className="text-sm font-medium">Total EOD Reported Hours</CardTitle></CardHeader><CardContent><p className="text-2xl font-bold">{focusedUserPerformanceData.total_eod_reported_hours.toFixed(2)}</p></CardContent></Card>
                  <Card><CardHeader><CardTitle className="text-sm font-medium">Total Commits</CardTitle></CardHeader><CardContent><p className="text-2xl font-bold">{focusedUserPerformanceData.total_commits_in_period}</p></CardContent></Card>
                  <Card><CardHeader><CardTitle className="text-sm font-medium">AI Estimated Commit Hours</CardTitle></CardHeader><CardContent><p className="text-2xl font-bold">{focusedUserPerformanceData.total_commit_ai_estimated_hours.toFixed(2)}</p></CardContent></Card>
                  <Card><CardHeader><CardTitle className="text-sm font-medium">Avg. Commit Seniority</CardTitle></CardHeader><CardContent><p className="text-2xl font-bold">{focusedUserPerformanceData.average_commit_seniority_score.toFixed(2)} / 10</p></CardContent></Card>
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle>EOD Report Details</CardTitle></CardHeader>
                <CardContent>
                  {focusedUserPerformanceData.eod_report_details.length > 0 ? (
                    <Table>
                      <TableHeader><TableRow><TableHead>Date</TableHead><TableHead className="text-right">Reported Hours</TableHead><TableHead>AI Summary</TableHead><TableHead className="text-right">AI Est. Hours</TableHead><TableHead className="text-right">Clarifications</TableHead></TableRow></TableHeader>
                      <TableBody>
                        {focusedUserPerformanceData.eod_report_details.map((eod, index) => (
                          <TableRow key={index}>
                            <TableCell>{format(new Date(eod.report_date), 'MMM dd, yyyy')}</TableCell>
                            <TableCell className="text-right">{eod.reported_hours.toFixed(2)}</TableCell>
                            <TableCell className="max-w-xs truncate" title={eod.ai_summary || ''}>{eod.ai_summary || 'N/A'}</TableCell>
                            <TableCell className="text-right">{eod.ai_estimated_hours.toFixed(2)}</TableCell>
                            <TableCell className="text-right">{eod.clarification_requests_count}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : <p>No EOD reports found for this period.</p>}
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle>Commit Comparison Insights</CardTitle><CardDescription>Highlights from comparing EOD reports with commit analysis.</CardDescription></CardHeader>
                <CardContent className="space-y-4">
                  {focusedUserPerformanceData.commit_comparison_insights.length > 0 ? (
                    focusedUserPerformanceData.commit_comparison_insights.map((insight, index) => (
                      <Card key={index} className="bg-muted/50">
                        <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Commit: {insight.commit_hash.substring(0, 7)}...</CardTitle><CardDescription className="text-xs">{format(new Date(insight.commit_timestamp), 'MMM dd, yyyy HH:mm')}</CardDescription></CardHeader>
                        <CardContent><pre className="whitespace-pre-wrap text-xs p-2 bg-background rounded-md">{insight.notes}</pre></CardContent>
                      </Card>
                    ))
                  ) : <p>No commit comparison insights available for this period.</p>}
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ManagerDashboardPage; 