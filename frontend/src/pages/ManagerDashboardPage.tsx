import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { User, UserPerformanceSummary, PerformanceSummaryParams, UserWidgetSummary } from '@/types/managerDashboard';
import api from '@/services/api';
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableCaption, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DateRangePicker } from "@/components/ui/date-range-picker";
import { addDays, format, formatDistanceToNow, isEqual } from 'date-fns';
import { DateRange } from 'react-day-picker';
import { useAuth } from '@/contexts/AuthContext';
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { DailyReportsView } from "@/components/DailyReportsView";
import { Chart } from "@/components/ui/chart";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { TrendingUp, ChevronDown, ChevronUp, BarChart, Clock, Target } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import { buildRangeForTimeframe, computeProgressValue, ManagerTimeframe } from './managerDashboardUtils';

const ManagerDashboardPageV2: React.FC = () => {
  const { session } = useAuth();
  const token = session?.access_token || null;
  const [users, setUsers] = useState<User[]>([]);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [selectedTimeframe, setSelectedTimeframe] = useState<ManagerTimeframe | 'custom'>('biweekly');

  // Global date range state for the widget's summary stat
  const [globalDateRange, setGlobalDateRange] = useState<DateRange | undefined>(() => buildRangeForTimeframe('biweekly'));
  // Stores the date range that has been *confirmed* for global use
  const [confirmedGlobalDateRange, setConfirmedGlobalDateRange] = useState<DateRange | undefined>(() => buildRangeForTimeframe('biweekly'));
  // Widget-specific state
  const [userWidgetsData, setUserWidgetsData] = useState<UserWidgetSummary[]>([]);
  const [isLoadingWidgets, setIsLoadingWidgets] = useState<boolean>(false);
  const [errorWidgets, setErrorWidgets] = useState<string | null>(null);

  // Focused detailed view state
  const [showFocusedViewForUserId, setShowFocusedViewForUserId] = useState<string | null>(null);
  const [focusedUserPerformanceData, setFocusedUserPerformanceData] = useState<UserPerformanceSummary | null>(null);
  const [focusedUserDateRange, setFocusedUserDateRange] = useState<DateRange | undefined>(undefined);
  const [confirmedFocusedDateRange, setConfirmedFocusedDateRange] = useState<DateRange | undefined>(undefined);
  const [isLoadingFocusedSummary, setIsLoadingFocusedSummary] = useState<boolean>(false);
  const [errorFocusedSummary, setErrorFocusedSummary] = useState<string | null>(null);
  
  const [isLoadingUsers, setIsLoadingUsers] = useState<boolean>(false);
  const [errorUsers, setErrorUsers] = useState<string | null>(null);

const widgetSummaries = useMemo(() => (Array.isArray(userWidgetsData) ? userWidgetsData : []), [userWidgetsData]);

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
        const fetchedUsers = await api.users.getUsers();
        setUsers(fetchedUsers);
      } catch (err) {
        setErrorUsers(err instanceof Error ? err.message : 'Failed to fetch users.');
      }
      setIsLoadingUsers(false);
    };
    fetchUsersList();
  }, [token]);

  // Fetch BULK WIDGET data (hours + business points)
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
      const response = await api.kpi.getWidgetSummaries(params);
      const widgets = Array.isArray(response?.data) ? response.data : Array.isArray(response) ? response : [];
      setUserWidgetsData(widgets as UserWidgetSummary[]);
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

  // Fetch data for the FOCUSED DETAILED VIEW (includes hours + business points series)
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
      const params = {
        startDate: format(dateRangeToUse.from, 'yyyy-MM-dd'),
        endDate: dateRangeToUse.to ? format(dateRangeToUse.to, 'yyyy-MM-dd') : format(dateRangeToUse.from, 'yyyy-MM-dd'),
      } as any;
      const summary = await api.kpi.getUserSummary(userId, params);
      setFocusedUserPerformanceData((summary?.data || summary) as UserPerformanceSummary);
    } catch (err) {
      setErrorFocusedSummary(err instanceof Error ? err.message : 'Failed to fetch detailed performance summary.');
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

  // Live updates: poll nightly analysis results periodically
  useEffect(() => {
    const interval = setInterval(() => {
      if (confirmedGlobalDateRange) {
        fetchBulkWidgetData(confirmedGlobalDateRange);
      }
      if (showFocusedViewForUserId && confirmedFocusedDateRange) {
        fetchFocusedUserData(showFocusedViewForUserId, confirmedFocusedDateRange);
      }
    }, 300_000); // 5 min
    return () => clearInterval(interval);
  }, [confirmedGlobalDateRange, showFocusedViewForUserId, confirmedFocusedDateRange, fetchBulkWidgetData, fetchFocusedUserData]);

  // Handler for Global Confirm Date Change button
  const handleGlobalDateConfirm = () => {
    setConfirmedGlobalDateRange(globalDateRange);
    // If a focused view is open, re-sync its date range and trigger its refetch
    if (showFocusedViewForUserId) {
      setFocusedUserDateRange(globalDateRange);
      setConfirmedFocusedDateRange(globalDateRange);
    }
  };

  // Open focused sheet and sync its range to confirmed global range
  const handleWidgetClick = (userId: string) => {
    setShowFocusedViewForUserId(userId);
    const range =
      confirmedGlobalDateRange ??
      buildRangeForTimeframe(
        selectedTimeframe === 'custom' ? 'biweekly' : (selectedTimeframe as ManagerTimeframe),
      );
    setFocusedUserDateRange(range);
    setConfirmedFocusedDateRange(range);
    setFocusedUserPerformanceData(null);
  };

  // Confirm focused range to trigger refetch via effect
  const handleFocusedDateConfirm = () => {
    setConfirmedFocusedDateRange(focusedUserDateRange);
  };

  // Handler for clicking a widget
  const applyTimeframeRange = useCallback((timeframe: ManagerTimeframe) => {
    const range = buildRangeForTimeframe(timeframe);
    setGlobalDateRange(range);
    setConfirmedGlobalDateRange(range);
    if (showFocusedViewForUserId) {
      setFocusedUserDateRange(range);
      setConfirmedFocusedDateRange(range);
    }
  }, [showFocusedViewForUserId]);

  const handleTimeframeChange = (timeframe: ManagerTimeframe | 'custom') => {
    if (timeframe === 'custom') {
      setSelectedTimeframe('custom');
      return;
    }
    setSelectedTimeframe(timeframe);
    applyTimeframeRange(timeframe);
  };

  const handleDateRangeChange = (range: DateRange | undefined) => {
    setSelectedTimeframe('custom');
    setGlobalDateRange(range);
  };

  const toggleRowExpansion = (userId: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(userId)) {
      newExpanded.delete(userId);
    } else {
      newExpanded.add(userId);
    }
    setExpandedRows(newExpanded);
  };
  
  const getPeriodString = useCallback((dateRangeToFormat: DateRange | undefined) => {
    if (!dateRangeToFormat?.from) return "N/A";
    const fromDate = format(dateRangeToFormat.from, 'MMM dd, yyyy');
    const toDate = dateRangeToFormat.to ? format(dateRangeToFormat.to, 'MMM dd, yyyy') : fromDate;
    return `${fromDate} - ${toDate}`;
  }, []);

  const widgetSummaryById = useMemo(() => {
    const map = new Map<string, UserWidgetSummary>();
    widgetSummaries.forEach(widget => {
      map.set(widget.user_id, widget);
    });
    return map;
  }, [widgetSummaries]);

  const focusedUserName = useMemo(() => {
    const widgetUser = showFocusedViewForUserId ? widgetSummaryById.get(showFocusedViewForUserId) : undefined;
    if (widgetUser?.name) return widgetUser.name;
    const generalUser = users.find(u => u.id === showFocusedViewForUserId);
    return generalUser?.name || "Focused User";
  }, [users, widgetSummaryById, showFocusedViewForUserId]);

  // Calculate performance tier based on points per hour
  const getPerformanceTier = (pph: number) => {
    if (pph >= 2.5) return { label: 'Excellent', color: 'text-green-600', bgColor: 'bg-green-100', trend: 'up' };
    if (pph >= 1.5) return { label: 'Good', color: 'text-blue-600', bgColor: 'bg-blue-100', trend: 'up' };
    if (pph >= 0.5) return { label: 'Average', color: 'text-yellow-600', bgColor: 'bg-yellow-100', trend: 'neutral' };
    return { label: 'Needs Support', color: 'text-red-600', bgColor: 'bg-red-100', trend: 'down' };
  };

  // Sort users by activity score for leaderboard
  const sortedUserData = useMemo(() => {
    return users
      .map(user => {
        const widgetData = widgetSummaryById.get(user.id);
        const activityScore = widgetData?.activity_score ?? 0;
        return { user, widgetData, activityScore };
      })
      .sort((a, b) => b.activityScore - a.activityScore);
  }, [users, widgetSummaryById]);

  const maxActivityScore = useMemo(() => {
    if (!widgetSummaries.length) return 0;
    return Math.max(...widgetSummaries.map(w => w.activity_score ?? 0));
  }, [widgetSummaries]);

  const totalPrs = useMemo(() => widgetSummaries.reduce((sum, w) => sum + (w.total_prs ?? 0), 0), [widgetSummaries]);
  const totalMergedPrs = useMemo(() => widgetSummaries.reduce((sum, w) => sum + (w.merged_prs ?? 0), 0), [widgetSummaries]);
  const averageActivityScore = useMemo(() => {
    if (!widgetSummaries.length) return 0;
    const total = widgetSummaries.reduce((sum, w) => sum + (w.activity_score ?? 0), 0);
    return total / widgetSummaries.length;
  }, [widgetSummaries]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Modern Header with Stats */}
      <div className="bg-white shadow-sm">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <div>
                <h1 className="text-xl font-semibold text-gray-900">Team Dashboard</h1>
                <p className="text-sm text-gray-500">{users.length} developers</p>
              </div>
              
              {/* Quick Stats */}
              <div className="hidden lg:flex items-center gap-4 pl-6 border-l">
                <div className="text-center">
                  <p className="text-2xl font-bold text-gray-900">{totalPrs}</p>
                  <p className="text-xs text-gray-500">Total PRs</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-gray-900">{totalMergedPrs}</p>
                  <p className="text-xs text-gray-500">Merged</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-gray-900">{averageActivityScore.toFixed(1)}</p>
                  <p className="text-xs text-gray-500">Avg Activity Score</p>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant={selectedTimeframe === 'biweekly' ? 'default' : 'outline'}
                  onClick={() => handleTimeframeChange('biweekly')}
                >
                  Bi-weekly
                </Button>
                <Button
                  size="sm"
                  variant={selectedTimeframe === 'monthly' ? 'default' : 'outline'}
                  onClick={() => handleTimeframeChange('monthly')}
                >
                  Monthly
                </Button>
              </div>
              <DateRangePicker
                id="global-date-range-picker"
                date={globalDateRange}
                onDateChange={handleDateRangeChange}
                className="w-auto"
              />
              <Button
                onClick={handleGlobalDateConfirm}
                disabled={!globalDateRange?.from || isLoadingWidgets}
                size="sm"
              >
                {isLoadingWidgets ? 'Loading...' : 'Apply'}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="container mx-auto px-6 py-6">
        {/* Error States */}
        {errorUsers && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-600 text-sm">{errorUsers}</p>
          </div>
        )}

        {/* Loading State */}
        {(isLoadingUsers || isLoadingWidgets) && (
          <div className="flex items-center justify-center py-16">
            <div className="text-center">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto"></div>
              <p className="text-gray-500 mt-3">Loading team data...</p>
            </div>
          </div>
        )}

        {/* List View */}
        {!isLoadingUsers && !isLoadingWidgets && users.length > 0 && (
          <Card className="shadow-lg">
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b">
                    <tr>
                      <th className="text-left py-4 px-6 font-medium text-gray-700 text-sm">Developer</th>
                      <th className="text-right py-4 px-4 font-medium text-gray-700 text-sm">Activity Score</th>
                      <th className="text-right py-4 px-4 font-medium text-gray-700 text-sm">PRs</th>
                      <th className="text-right py-4 px-4 font-medium text-gray-700 text-sm hidden sm:table-cell">Hours</th>
                      <th className="text-right py-4 px-4 font-medium text-gray-700 text-sm hidden sm:table-cell">Points</th>
                      <th className="text-center py-4 px-4 font-medium text-gray-700 text-sm">Status</th>
                      <th className="text-center py-4 px-6 font-medium text-gray-700 text-sm">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {sortedUserData.map(({ user, widgetData }) => {
                      const userName = widgetData?.name || user.name || 'Unknown User';
                      const userAvatarUrl = widgetData?.avatar_url || undefined;
                      const isExpanded = expandedRows.has(user.id);

                      if (!widgetData) {
                        return (
                          <tr key={user.id} className="hover:bg-gray-50 transition-colors">
                            <td className="py-4 px-6">
                              <div className="flex items-center gap-3">
                                <Avatar className="h-9 w-9">
                                  <AvatarImage src={userAvatarUrl} alt={userName} />
                                  <AvatarFallback className="bg-gray-200 text-gray-600 text-sm">
                                    {userName.split(' ').map(n => n[0]).join('').toUpperCase()}
                                  </AvatarFallback>
                                </Avatar>
                                <div>
                                  <p className="font-medium text-gray-900">{userName}</p>
                                  <p className="text-xs text-gray-500">No data</p>
                                </div>
                              </div>
                            </td>
                            <td colSpan={6} className="text-center py-4 text-gray-400 text-sm">
                              No pull requests recorded for selected range
                            </td>
                          </tr>
                        );
                      }

                      const activityScore = widgetData.activity_score ?? 0;
                      const totalPrs = widgetData.total_prs ?? 0;
                      const mergedPrs = widgetData.merged_prs ?? 0;
                      const points = widgetData.total_business_points ?? 0;
                      const hours = widgetData.total_ai_estimated_pr_hours ?? 0;
                      const normalizedPph = widgetData.normalized_efficiency_points_per_hour ?? widgetData.efficiency_points_per_hour ?? 0;
                      const tier = getPerformanceTier(normalizedPph);
                      const isDayOff = widgetData.day_off ?? totalPrs === 0;
                      const latestActivityTimestamp = widgetData.latest_activity_timestamp;
                      const latestRelative = latestActivityTimestamp ? formatDistanceToNow(new Date(latestActivityTimestamp), { addSuffix: true }) : null;
                      const progressValue = computeProgressValue(activityScore, maxActivityScore);

                      return (
                        <React.Fragment key={user.id}>
                          <tr className="hover:bg-gray-50 transition-colors group">
                            <td className="py-4 px-6">
                              <div className="flex items-center gap-3">
                                <Avatar className="h-9 w-9">
                                  <AvatarImage src={userAvatarUrl} alt={userName} />
                                  <AvatarFallback className="bg-gray-200 text-gray-600 text-sm">
                                    {userName.split(' ').map(n => n[0]).join('').toUpperCase()}
                                  </AvatarFallback>
                                </Avatar>
                                <div>
                                  <p className="font-medium text-gray-900">{userName}</p>
                                  <p className="text-xs text-gray-500">{getPeriodString(confirmedGlobalDateRange)}</p>
                                </div>
                              </div>
                            </td>
                            <td className="text-right py-4 px-4">
                              <div className="flex flex-col items-end gap-1">
                                <div className="flex items-center gap-2">
                                  <p className="font-semibold text-gray-900">{activityScore.toFixed(1)}</p>
                                  {!isDayOff && (
                                    <Badge
                                      variant="outline"
                                      className={cn('text-xs font-medium', tier.color, tier.bgColor)}
                                    >
                                      {tier.label}
                                    </Badge>
                                  )}
                                </div>
                                <div className="w-28">
                                  <Progress value={progressValue} className="h-2" />
                                  <p className="text-xs text-gray-500 text-right mt-1">{Math.round(progressValue)}%</p>
                                </div>
                              </div>
                            </td>
                            <td className="text-right py-4 px-4">
                              <div className="flex flex-col items-end">
                                <p className="font-semibold text-gray-900">{totalPrs}</p>
                                <p className="text-xs text-gray-500">{mergedPrs} merged</p>
                              </div>
                            </td>
                            <td className="text-right py-4 px-4 hidden sm:table-cell">
                              <p className="font-medium text-gray-700">{hours.toFixed(1)}</p>
                            </td>
                            <td className="text-right py-4 px-4 hidden sm:table-cell">
                              <p className="font-medium text-gray-700">{points.toFixed(1)}</p>
                            </td>
                            <td className="py-4 px-4 text-center">
                              {isDayOff ? (
                                <Badge variant="secondary" className="bg-red-100 text-red-700 border-red-100">
                                  Day Off
                                </Badge>
                              ) : (
                                <div className="flex flex-col items-center gap-0.5">
                                  <p
                                    className="text-sm text-gray-800 max-w-[160px] truncate"
                                    title={widgetData.latest_pr_title || 'Active'}
                                  >
                                    {widgetData.latest_pr_title || 'Active'}
                                  </p>
                                  <p className="text-xs text-gray-500">{latestRelative || 'Updated just now'}</p>
                                </div>
                              )}
                            </td>
                            <td className="text-center py-4 px-6">
                              <div className="flex items-center justify-center gap-2">
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => toggleRowExpansion(user.id)}
                                  className="text-gray-600 hover:text-gray-900"
                                >
                                  {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleWidgetClick(user.id)}
                                  className="text-blue-600 hover:text-blue-700 border-blue-200 hover:border-blue-300"
                                >
                                  <BarChart className="w-4 h-4 mr-1" />
                                  Details
                                </Button>
                              </div>
                            </td>
                          </tr>
                          {isExpanded && (
                            <tr className="bg-gray-50">
                              <td colSpan={6} className="p-6">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                  <div className="space-y-2">
                                    <p className="text-sm font-medium text-gray-700">Performance Metrics</p>
                                    <div className="space-y-1">
                                      <div className="flex justify-between items-center">
                                        <span className="text-sm text-gray-500">Activity Score</span>
                                        <span className="text-sm font-medium">{activityScore.toFixed(1)}</span>
                                      </div>
                                      <div className="flex justify-between">
                                        <span className="text-xs text-gray-500">Normalized PPH</span>
                                        <span className="text-xs font-medium text-gray-600">{normalizedPph.toFixed(2)} pts/hr</span>
                                      </div>
                                      <div className="flex justify-between">
                                        <span className="text-sm text-gray-500">Pull Requests</span>
                                        <span className="text-sm font-medium">{totalPrs} ({mergedPrs} merged)</span>
                                      </div>
                                      <div className="flex justify-between">
                                        <span className="text-sm text-gray-500">Total Hours</span>
                                        <span className="text-sm font-medium">{hours.toFixed(1)}</span>
                                      </div>
                                      <div className="flex justify-between">
                                        <span className="text-sm text-gray-500">Business Points</span>
                                        <span className="text-sm font-medium">{points.toFixed(1)}</span>
                                      </div>
                                    </div>
                                  </div>
                                  {/* Quick Stats trend removed for simplicity */}
                                  <div className="space-y-2">
                                    <p className="text-sm font-medium text-gray-700">Recent Activity</p>
                                    {(() => {
                                      const hoursSeries = widgetData?.daily_hours_series || [];
                                      // Today's hours is the end of the applied global range (UTC date key)
                                      const endDate = confirmedGlobalDateRange?.to || confirmedGlobalDateRange?.from || new Date();
                                      const todayStr = format(endDate as Date, 'yyyy-MM-dd');
                                      const todayHours = hoursSeries.find(d => d.date === todayStr)?.hours ?? 0;
                                      // Weekly average points/hr based on last 7 days
                                      const pointsSeries = widgetData?.daily_points_series || [];
                                      const last7Hours = hoursSeries.slice(-7).reduce((a, b) => a + (b.hours || 0), 0);
                                      const last7Points = pointsSeries.slice(-7).reduce((a, b) => a + (b.points || 0), 0);
                                          const weeklyAvg = last7Hours > 0 ? (last7Points / last7Hours) : 0;
                                          // Last active (last day with any hours)
                                      const lastActiveEntry = [...hoursSeries].reverse().find(entry => (entry?.hours || 0) > 0);
                                      const lastActiveText = lastActiveEntry
                                        ? formatDistanceToNow(new Date(lastActiveEntry.date), { addSuffix: true })
                                        : 'No recent activity';
                                      return (
                                        <div className="space-y-1 text-sm text-gray-600">
                                          <p>• Last activity: {lastActiveText}</p>
                                          <p>• Today's hours: {todayHours.toFixed(1)}</p>
                                          <p>• Weekly average: {weeklyAvg.toFixed(1)} pts/hr</p>
                                        </div>
                                      );
                                    })()}
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Focused Detailed Stats View - Cleaner Design */}
      {showFocusedViewForUserId && (
        <Sheet open={!!showFocusedViewForUserId} onOpenChange={(open) => !open && setShowFocusedViewForUserId(null)}>
          <SheetContent side="right" className="sm:max-w-2xl overflow-y-auto">
            <SheetHeader className="space-y-1 pb-4 border-b">
              <SheetTitle className="text-xl font-semibold">{focusedUserName}</SheetTitle>
              <p className="text-sm text-gray-500">Performance Analysis • {getPeriodString(confirmedFocusedDateRange)}</p>
            </SheetHeader>
            
            <div className="mt-6 space-y-6">
              {/* Streamlined Date Range Selector */}
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-700 mb-2">Analysis Period</p>
                    <DateRangePicker 
                      id="focused-date-range-picker" 
                      date={focusedUserDateRange} 
                      onDateChange={setFocusedUserDateRange}
                      className="w-full"
                    />
                  </div>
                  <Button 
                    onClick={handleFocusedDateConfirm} 
                    disabled={isLoadingFocusedSummary || !focusedUserDateRange?.from}
                    size="sm"
                    className="mt-6"
                  >
                    {isLoadingFocusedSummary ? 'Loading...' : 'Update'}
                  </Button>
                </div>
              </div>

              {isLoadingFocusedSummary && (
                <div className="flex items-center justify-center py-8">
                  <div className="text-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                    <p className="text-gray-500 mt-2 text-sm">Loading performance data...</p>
                  </div>
                </div>
              )}
              
              {errorFocusedSummary && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-red-600 text-sm">{errorFocusedSummary}</p>
                </div>
              )}

              {focusedUserPerformanceData && (
                <>
                  {/* Key Metrics - Cleaner Grid */}
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900 mb-3">Key Metrics</h3>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="bg-white border rounded-lg p-4">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs text-gray-500">Activity Score</span>
                          <TrendingUp className="w-3 h-3 text-green-500" />
                        </div>
                        <p className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                          {focusedUserPerformanceData.activity_score.toFixed(1)}
                          {focusedUserPerformanceData.efficiency_provisional && (
                            <span className="text-[11px] text-gray-500 px-2 py-0.5 border border-gray-200 rounded">Baseline</span>
                          )}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          {(focusedUserPerformanceData.normalized_efficiency_points_per_hour ?? focusedUserPerformanceData.efficiency_points_per_hour ?? 0).toFixed(2)} pts/hr normalized
                        </p>
                      </div>

                      <div className="bg-white border rounded-lg p-4">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs text-gray-500">Pull Requests</span>
                          <BarChart className="w-3 h-3 text-blue-500" />
                        </div>
                        <p className="text-2xl font-bold text-gray-900">
                          {focusedUserPerformanceData.total_prs_in_period}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          {focusedUserPerformanceData.merged_prs_in_period} merged
                        </p>
                      </div>

                      <div className="bg-white border rounded-lg p-4">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs text-gray-500">AI Estimated Hours</span>
                          <Clock className="w-3 h-3 text-blue-500" />
                        </div>
                        <p className="text-2xl font-bold text-gray-900">
                          {focusedUserPerformanceData.total_ai_estimated_pr_hours.toFixed(1)}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">across all PRs</p>
                      </div>

                      <div className="bg-white border rounded-lg p-4">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs text-gray-500">Business Impact</span>
                          <Target className="w-3 h-3 text-purple-500" />
                        </div>
                        <p className="text-2xl font-bold text-gray-900">
                          {focusedUserPerformanceData.total_business_points.toFixed(1)}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">Avg turnaround {focusedUserPerformanceData.average_pr_turnaround_hours.toFixed(1)}h</p>
                      </div>
                    </div>
                  </div>

                  {/* Pull Request Summaries */}
                  <Collapsible defaultOpen>
                    <CollapsibleTrigger className="flex items-center justify-between w-full py-2 text-left hover:text-gray-700">
                      <h3 className="text-sm font-semibold text-gray-900">Pull Request Summaries</h3>
                      <ChevronDown className="w-4 h-4 text-gray-400" />
                    </CollapsibleTrigger>
                    <CollapsibleContent className="mt-3">
                      <div className="bg-white border rounded-lg overflow-hidden">
                        {focusedUserPerformanceData.pr_details.length ? (
                          <div className="divide-y">
                            {focusedUserPerformanceData.pr_details.slice(0, 10).map(pr => {
                              const activityDate = pr.activity_timestamp ? new Date(pr.activity_timestamp) : null;
                              return (
                                <div key={`${pr.pr_number}-${pr.activity_timestamp}`} className="p-4 space-y-2">
                                  <div className="flex items-start justify-between gap-3">
                                    <div>
                                      <p className="text-sm font-semibold text-gray-900">#{pr.pr_number} {pr.title || pr.ai_summary || 'Untitled PR'}</p>
                                      <p className="text-xs text-gray-500">
                                        {pr.status || 'pending'}
                                        {activityDate && (
                                          <span className="ml-2">• {format(activityDate, 'MMM dd, yyyy')}</span>
                                        )}
                                      </p>
                                    </div>
                                    {typeof pr.impact_score === 'number' && (
                                      <Badge variant="secondary" className="bg-emerald-100 text-emerald-700 border-emerald-100">
                                        {pr.impact_score.toFixed(1)} pts
                                      </Badge>
                                    )}
                                  </div>
                                  {pr.ai_summary && <p className="text-sm text-gray-700">{pr.ai_summary}</p>}
                                  {pr.ai_prompts?.length ? (
                                    <div className="flex flex-wrap gap-2">
                                      {pr.ai_prompts.map(prompt => (
                                        <Badge key={prompt} variant="outline" className="text-[11px]">{prompt}</Badge>
                                      ))}
                                    </div>
                                  ) : null}
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <p className="p-4 text-sm text-gray-500">No pull requests recorded in this range.</p>
                        )}
                      </div>
                    </CollapsibleContent>
                  </Collapsible>

                  {/* Trend Chart - Simplified */}
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900 mb-3">Performance Trend</h3>
                    <div className="bg-white border rounded-lg p-4">
                      <Chart
                        data={(() => {
                          const hours = focusedUserPerformanceData.daily_hours_series || [];
                          const points = focusedUserPerformanceData.daily_points_series || [];
                          const dates = Array.from(new Set([...
                            (hours as any[]).map(h => h.date), (points as any[]).map(p => p.date)
                          ].flat())).sort();
                          return dates.map(d => ({
                            date: d,
                            hours: (hours as any[]).find(h => h.date === d)?.hours ?? 0,
                            points: (points as any[]).find(p => p.date === d)?.points ?? 0,
                          }));
                        })()}
                        type="line"
                        xKey="date"
                        yKeys={[
                          { key: 'hours', name: 'Hours', color: '#3b82f6' },
                          { key: 'points', name: 'Points', color: '#10b981' },
                        ]}
                        height={200}
                      />
                    </div>
                  </div>

                  {/* Top Pull Requests - Collapsible */}
                  <Collapsible defaultOpen>
                    <CollapsibleTrigger className="flex items-center justify-between w-full py-2 text-left hover:text-gray-700">
                      <h3 className="text-sm font-semibold text-gray-900">Top PRs by Impact</h3>
                      <ChevronDown className="w-4 h-4 text-gray-400" />
                    </CollapsibleTrigger>
                    <CollapsibleContent className="mt-3">
                      <div className="bg-white border rounded-lg overflow-hidden">
                        {focusedUserPerformanceData.top_prs_by_impact?.length ? (
                          <Table>
                            <TableHeader>
                              <TableRow className="bg-gray-50">
                                <TableHead className="text-xs">PR #</TableHead>
                                <TableHead className="text-xs">Summary</TableHead>
                                <TableHead className="text-right text-xs">Impact</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {focusedUserPerformanceData.top_prs_by_impact.slice(0, 5).map((pr, idx) => (
                                <TableRow key={idx}>
                                  <TableCell className="font-mono text-xs py-2">#{pr.pr_number ?? '—'}</TableCell>
                                  <TableCell className="truncate max-w-[280px] text-sm py-2" title={pr.title || ''}>
                                    {pr.title || pr.ai_summary || '—'}
                                  </TableCell>
                                  <TableCell className="text-right text-sm py-2">
                                    {typeof pr.impact_score === 'number' ? pr.impact_score.toFixed(1) : pr.impact_score}
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        ) : (
                          <p className="p-4 text-sm text-gray-500">No high-impact PRs found for this period.</p>
                        )}
                      </div>
                    </CollapsibleContent>
                  </Collapsible>

                  {/* EOD Reports - Collapsible */}
                  <Collapsible>
                    <CollapsibleTrigger className="flex items-center justify-between w-full py-2 text-left hover:text-gray-700">
                      <h3 className="text-sm font-semibold text-gray-900">EOD Report Summary</h3>
                      <ChevronDown className="w-4 h-4 text-gray-400" />
                    </CollapsibleTrigger>
                    <CollapsibleContent className="mt-3">
                      <div className="bg-white border rounded-lg overflow-hidden">
                        {focusedUserPerformanceData.eod_report_details.length > 0 ? (
                          <div className="overflow-x-auto">
                            <Table>
                              <TableHeader>
                                <TableRow className="bg-gray-50">
                                  <TableHead className="text-xs">Date</TableHead>
                                  <TableHead className="text-right text-xs">Hours</TableHead>
                                  <TableHead className="text-xs">Summary</TableHead>
                                  <TableHead className="text-right text-xs">AI Est.</TableHead>
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {focusedUserPerformanceData.eod_report_details.slice(0, 5).map((eod, index) => (
                                  <TableRow key={index}>
                                    <TableCell className="text-sm py-2">{format(new Date(eod.report_date), 'MMM dd')}</TableCell>
                                    <TableCell className="text-right text-sm py-2">{eod.reported_hours.toFixed(1)}</TableCell>
                                    <TableCell className="max-w-[200px] truncate text-sm py-2" title={eod.ai_summary || ''}>{eod.ai_summary || 'N/A'}</TableCell>
                                    <TableCell className="text-right text-sm py-2">{eod.ai_estimated_hours.toFixed(1)}</TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </div>
                        ) : (
                          <p className="p-4 text-sm text-gray-500">No EOD reports found for this period.</p>
                        )}
                      </div>
                    </CollapsibleContent>
                  </Collapsible>

                  {/* Full History - Collapsible */}
                  <Collapsible>
                    <CollapsibleTrigger className="flex items-center justify-between w-full py-2 text-left hover:text-gray-700">
                      <h3 className="text-sm font-semibold text-gray-900">Full Report History</h3>
                      <ChevronDown className="w-4 h-4 text-gray-400" />
                    </CollapsibleTrigger>
                    <CollapsibleContent className="mt-3">
                      <div className="bg-white border rounded-lg p-4">
                        <DailyReportsView userId={showFocusedViewForUserId} userName={focusedUserName} />
                      </div>
                    </CollapsibleContent>
                  </Collapsible>
                </>
              )}
            </div>
          </SheetContent>
        </Sheet>
      )}
    </div>
  );
};

export default ManagerDashboardPageV2;
