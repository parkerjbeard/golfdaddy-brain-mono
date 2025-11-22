
import { useState, useEffect } from 'react';
import { Card } from "@/components/ui/card";
import { KpiCard } from '@/components/ui/KpiCard';
import { MessageSquare, Award, RefreshCw, Target, AlertTriangle, Users, Archive, CheckCircle2, Lightbulb } from "lucide-react";
import { Button } from "@/components/ui/button";
import { RetentionChart } from '@/components/ui/RetentionChart';
import { Progress } from "@/components/ui/progress";
import { api } from '@/services/api/endpoints';
import type { WeeklyData } from '@/services/zapierApi';
import type { DashboardData } from '@/types/dashboard';
import dashboardData from '../dashboard_data.json';
import { DataState } from '@/components/ui/DataState';

const CompanyDashboard = () => {
  // Zapier data state
  const [weeklyData, setWeeklyData] = useState<WeeklyData | null>(null);
  const [zapierLoading, setZapierLoading] = useState(false);
  const [authError, setAuthError] = useState(false);
  
  // Local dashboard data
  const [localData, setLocalData] = useState<DashboardData | null>(null);

  // Fetch Zapier data
  const fetchZapierData = async () => {
    setZapierLoading(true);
    setAuthError(false);
    try {
      const data = await api.zapier.getWeeklyData();
      setWeeklyData(data);
    } catch (error: any) {
      console.error('Error fetching Zapier data:', error);
      // Handle authentication errors
      if (error?.response?.status === 401) {
        setAuthError(true);
        console.log('Authentication token expired. Please refresh the page or log in again.');
      }
    } finally {
      setZapierLoading(false);
    }
  };

  useEffect(() => {
    fetchZapierData();
    setLocalData(dashboardData as DashboardData);
  }, []);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold mb-4">Company Dashboard</h1>
        <p className="text-muted-foreground mb-6">
          Weekly insights and company performance metrics
          {localData && ` • Last updated: ${formatDate(localData.dashboard.lastUpdated)}`}
        </p>
      </div>

      {/* Authentication Error Message */}
      {authError && (
        <Card className="p-4 border-amber-200 bg-amber-50">
          <div className="flex items-center justify-between">
            <p className="text-sm text-amber-900">
              Your session has expired. Please refresh the page to continue.
            </p>
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => window.location.reload()}
              className="ml-4"
            >
              Refresh Page
            </Button>
          </div>
        </Card>
      )}

      {/* Weekly KPI Cards from Zapier */}
      <div>
        <h2 className="text-lg font-medium mb-4">Weekly Key Performance Indicators</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard 
            title="CSAT Score" 
            value={localData ? localData.dashboard.kpis.csat.current.toString() : (weeklyData ? `${weeklyData.csat_score}%` : '-')}
            description={localData ? `Previous: ${localData.dashboard.kpis.csat.previous}` : "Customer satisfaction"}
            trend={localData ? localData.dashboard.kpis.csat.trend : (weeklyData?.csat_change_percentage && weeklyData.csat_change_percentage > 0 ? 'up' : weeklyData?.csat_change_percentage && weeklyData.csat_change_percentage < 0 ? 'down' : 'neutral')}
            percentageChange={localData ? parseFloat(((localData.dashboard.kpis.csat.change / localData.dashboard.kpis.csat.previous) * 100).toFixed(1)) : (weeklyData?.csat_change_percentage || undefined)}
          />
          <KpiCard 
            title="Social Media Views" 
            value={localData ? `${(localData.dashboard.kpis.socialMedia.totalViews / 1000000).toFixed(1)}M` : (weeklyData?.social_media_views.toLocaleString() || '-')}
            description={localData ? `Across ${localData.dashboard.kpis.socialMedia.platforms.length} platforms` : "Total social views"}
            trend={weeklyData?.social_views_change_percentage && weeklyData.social_views_change_percentage > 0 ? 'up' : weeklyData?.social_views_change_percentage && weeklyData.social_views_change_percentage < 0 ? 'down' : 'neutral'}
            percentageChange={weeklyData?.social_views_change_percentage || undefined}
          />
          <KpiCard 
            title="Week 1 Retention" 
            value={localData ? `${localData.dashboard.kpis.retention.week1.toFixed(1)}%` : '-'}
            description={localData ? `Target: ${localData.dashboard.kpis.retention.week1Target}%` : "User retention"}
            trend={localData && localData.dashboard.kpis.retention.week1 < localData.dashboard.kpis.retention.week1Target ? 'down' : 'neutral'}
          />
          <KpiCard 
            title="Active Projects" 
            value={localData ? localData.dashboard.projects.active.length.toString() : '-'}
            description={localData ? `${localData.dashboard.projects.archived.length} archived` : "Company initiatives"}
            trend="neutral"
          />
        </div>
      </div>

      {/* Retention Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {weeklyData ? (
          <RetentionChart 
            title="First Week Retention (%)"
            data={weeklyData.weekly_retention}
          />
        ) : (
          <DataState
            state={zapierLoading ? 'loading' : 'empty'}
            title="Retention data"
            description={zapierLoading ? 'Loading retention metrics...' : 'No retention data yet'}
          />
        )}

        {weeklyData ? (
          <RetentionChart 
            title="First Month Usage (%)"
            data={weeklyData.monthly_retention}
          />
        ) : (
          <DataState
            state={zapierLoading ? 'loading' : 'empty'}
            title="Usage data"
            description={zapierLoading ? 'Loading usage metrics...' : 'No usage data yet'}
          />
        )}
      </div>

      {/* Weekly Insights & User Feedback */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Weekly Insights */}
        {localData && (
          <Card className="p-6">
            <h3 className="text-lg font-medium mb-4">
              <div className="flex items-center gap-2">
                <Lightbulb className="h-5 w-5" />
                Weekly Insights
              </div>
            </h3>
            <p className="text-sm leading-relaxed">
              {localData.dashboard.insights.weekly}
            </p>
          </Card>
        )}

        {/* User Feedback Summary */}
        {weeklyData ? (
          <Card className="p-6">
            <h3 className="text-lg font-medium mb-4">
              <div className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5" />
                User Feedback Summary
                {zapierLoading && <RefreshCw className="h-4 w-4 animate-spin" />}
              </div>
            </h3>
            <div className="prose max-w-none">
              <p className="text-sm leading-relaxed">
                {weeklyData.user_feedback_summary}
              </p>
            </div>
          </Card>
        ) : (
          <DataState
            state={zapierLoading ? 'loading' : 'empty'}
            title="User feedback"
            description={zapierLoading ? 'Fetching feedback from Zapier' : 'No feedback available'}
            onRetry={fetchZapierData}
          />
        )}
      </div>

      {/* Recent Wins */}
      {weeklyData && weeklyData.wins.length > 0 ? (
        <Card className="p-6">
          <h2 className="text-lg font-medium mb-4">
            <div className="flex items-center gap-2">
              <Award className="h-5 w-5" />
              Recent Wins
              {zapierLoading && <RefreshCw className="h-4 w-4 animate-spin" />}
            </div>
          </h2>
          <div className="space-y-3">
            {weeklyData.wins.map((win, index) => (
              <div key={index} className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                <p className="text-sm font-medium text-yellow-900">{win}</p>
              </div>
            ))}
          </div>
        </Card>
      ) : (
        <DataState
          state={zapierLoading ? 'loading' : 'empty'}
          title="Recent wins"
          description={zapierLoading ? 'Pulling latest wins...' : 'No wins logged for this period'}
          onRetry={fetchZapierData}
          actionLabel={!zapierLoading ? 'Refresh data' : undefined}
          onAction={!zapierLoading ? fetchZapierData : undefined}
        />
      )}

      {/* Active Company Goals & Projects */}
      {localData && (
        <Card className="p-6">
          <h2 className="text-lg font-medium mb-4">
            <div className="flex items-center gap-2">
              <Target className="h-5 w-5" />
              Active Company Goals & Projects
            </div>
          </h2>
          <div className="space-y-4">
            {localData.dashboard.projects.active.map((project) => (
              <div key={project.id} className="border rounded-lg p-4 space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-medium">{project.name}</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      {project.team} • {project.owner.name} • Due: {project.dueDate ? formatDate(project.dueDate) : 'TBD'}
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold">{project.progress}%</div>
                  </div>
                </div>
                
                <Progress value={project.progress} className="h-2" />
                
                {project.keyResults.length > 0 && (
                  <div className="pt-2">
                    <p className="text-sm font-medium mb-2">Key Results:</p>
                    <div className="space-y-1">
                      {project.keyResults.map((kr, index) => (
                        <div key={index} className="text-sm text-muted-foreground flex items-center gap-1">
                          <CheckCircle2 className="h-3 w-3" />
                          {kr}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {project.checklist && (
                  <div className="pt-2">
                    <p className="text-sm font-medium mb-2">
                      Progress: {project.checklist.completed}/{project.checklist.total} completed
                    </p>
                    <div className="space-y-1">
                      {project.checklist.items.map((item, index) => (
                        <div key={index} className="flex items-center gap-2 text-sm">
                          <CheckCircle2 
                            className={`h-4 w-4 ${item.completed ? 'text-green-600' : 'text-gray-300'}`} 
                          />
                          <span className={item.completed ? 'line-through text-muted-foreground' : ''}>
                            {item.name}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Customer Support Issues */}
      {localData && localData.dashboard.issues.customerSupport.length > 0 && (
        <Card className="p-6">
          <h2 className="text-lg font-medium mb-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-orange-500" />
              Customer Support Issues
            </div>
          </h2>
          <div className="space-y-2">
            {localData.dashboard.issues.customerSupport.map((issue, index) => (
              <div key={index} className="p-3 bg-orange-50 rounded-lg">
                <p className="text-sm">{issue}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Team Distribution */}
      {localData && (
        <Card className="p-6">
          <h2 className="text-lg font-medium mb-4">
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              Team Project Distribution
            </div>
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.entries(localData.dashboard.teamStats).map(([team, stats]) => (
              <div key={team} className="text-center p-4 bg-gray-50 rounded">
                <h3 className="font-medium text-sm">{team}</h3>
                <div className="mt-2">
                  <div className="text-lg font-bold">{stats.active}</div>
                  <div className="text-xs text-muted-foreground">Active Projects</div>
                </div>
                {stats.archived > 0 && (
                  <div className="mt-1">
                    <div className="text-sm text-gray-500">{stats.archived} archived</div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Archived Projects */}
      {localData && localData.dashboard.projects.archived.length > 0 && (
        <Card className="p-6">
          <h2 className="text-lg font-medium mb-4">
            <div className="flex items-center gap-2">
              <Archive className="h-5 w-5" />
              Archived Projects
            </div>
          </h2>
          <div className="space-y-3">
            {localData.dashboard.projects.archived.map((project) => (
              <div key={project.id} className="border rounded-lg p-3 bg-gray-50">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-medium text-gray-700">{project.name}</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      {project.team} • {project.owner.name}
                    </p>
                  </div>
                  <span className="text-sm text-gray-500">Archived</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};

export default CompanyDashboard;
