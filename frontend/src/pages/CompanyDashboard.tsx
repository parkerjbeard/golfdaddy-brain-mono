
import { useState, useEffect } from 'react';
import { Card } from "@/components/ui/card";
import { KpiCard } from '@/components/ui/KpiCard';
import { MessageSquare, Award, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { RetentionChart } from '@/components/ui/RetentionChart';
import { api } from '@/services/api/endpoints';
import type { WeeklyData } from '@/services/zapierApi';

const CompanyDashboard = () => {
  // Zapier data state
  const [weeklyData, setWeeklyData] = useState<WeeklyData | null>(null);
  const [zapierLoading, setZapierLoading] = useState(false);
  const [authError, setAuthError] = useState(false);

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
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold mb-4">Company Dashboard</h1>
        <p className="text-muted-foreground mb-6">Weekly insights and company performance metrics</p>
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
            value={weeklyData ? `${weeklyData.csat_score}%` : '-'}
            description="Customer satisfaction"
            trend={weeklyData?.csat_change_percentage && weeklyData.csat_change_percentage > 0 ? 'up' : weeklyData?.csat_change_percentage && weeklyData.csat_change_percentage < 0 ? 'down' : 'neutral'}
            percentageChange={weeklyData?.csat_change_percentage || undefined}
          />
          <KpiCard 
            title="Social Media Views" 
            value={weeklyData?.social_media_views.toLocaleString() || '-'}
            description="Total social views"
            trend={weeklyData?.social_views_change_percentage && weeklyData.social_views_change_percentage > 0 ? 'up' : weeklyData?.social_views_change_percentage && weeklyData.social_views_change_percentage < 0 ? 'down' : 'neutral'}
            percentageChange={weeklyData?.social_views_change_percentage || undefined}
          />
          <KpiCard 
            title="Avg Shipping Time" 
            value={weeklyData ? `${weeklyData.average_shipping_time} days` : '-'}
            description="Average delivery time"
            trend="neutral"
          />
          <KpiCard 
            title="Weeks Since Issue" 
            value={weeklyData?.weeks_since_logistics_mistake.toString() || '-'}
            description="Last logistics mistake"
            trend="up"
          />
        </div>
      </div>

      {/* Retention Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* First Week Retention */}
        {weeklyData && (
          <RetentionChart 
            title="First Week Retention (%)"
            data={weeklyData.weekly_retention}
          />
        )}

        {/* First Month Usage */}
        {weeklyData && (
          <RetentionChart 
            title="First Month Usage (%)"
            data={weeklyData.monthly_retention}
          />
        )}
      </div>

      {/* User Feedback Summary */}
      <Card className="p-6">
        <h3 className="text-lg font-medium mb-4">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            User Feedback Summary
            {zapierLoading && <RefreshCw className="h-4 w-4 animate-spin" />}
          </div>
        </h3>
        <div className="prose max-w-none">
          {weeklyData ? (
            <p className="text-sm leading-relaxed">
              {weeklyData.user_feedback_summary}
            </p>
          ) : (
            <p className="text-muted-foreground">
              Loading user feedback from Zapier...
            </p>
          )}
        </div>
      </Card>

      {/* Recent Wins */}
      <Card className="p-6">
        <h2 className="text-lg font-medium mb-4">
          <div className="flex items-center gap-2">
            <Award className="h-5 w-5" />
            Recent Wins
            {zapierLoading && <RefreshCw className="h-4 w-4 animate-spin" />}
          </div>
        </h2>
        {weeklyData && weeklyData.wins.length > 0 ? (
          <div className="space-y-3">
            {weeklyData.wins.map((win, index) => (
              <div key={index} className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                <p className="text-sm font-medium text-yellow-900">{win}</p>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-32 border-2 border-dashed rounded-lg">
            <p className="text-muted-foreground">
              {zapierLoading ? 'Loading wins...' : 'No recent wins recorded'}
            </p>
            {!zapierLoading && (
              <Button variant="outline" className="mt-2" onClick={fetchZapierData}>
                Refresh Data
              </Button>
            )}
          </div>
        )}
      </Card>
    </div>
  );
};

export default CompanyDashboard;
