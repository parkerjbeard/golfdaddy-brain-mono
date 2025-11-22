import { apiClient } from './api/client';

// Types for Zapier data
export interface WeeklyData {
  wins: string[];
  csat_score: number;
  csat_change_percentage: number | null;
  user_feedback_summary: string;
  social_media_views: number;
  social_views_change_percentage: number | null;
  average_shipping_time: number;
  weeks_since_logistics_mistake: number;
  weekly_retention: Record<string, number>;
  monthly_retention: Record<string, number>;
}

export interface ZapierObjective {
  id: string;
  name: string;
  completion_percentage: number;
  due_date: string;
  owner: string;
  sparkline_data: number[];
}

export interface BusinessGoals {
  short_term: Array<{
    id: string;
    name: string;
    tags: string[];
  }>;
  long_term: Array<{
    id: string;
    name: string;
    tags: string[];
  }>;
}

export interface DashboardRefreshResult {
  success: boolean;
  message: string;
  timestamp: string;
}

export const zapierApi = {
  /**
   * Get current week's analytics data from Zapier flows
   */
  async getWeeklyData(): Promise<WeeklyData> {
    const response = await apiClient.get<WeeklyData>('/zapier/weekly-data');
    return response.data;
  },

  /**
   * Get current objectives from ClickUp via Zapier
   */
  async getObjectives(): Promise<ZapierObjective[]> {
    const response = await apiClient.get<ZapierObjective[]>('/zapier/objectives');
    return response.data;
  },

  /**
   * Get business goals categorized as short-term and long-term
   */
  async getBusinessGoals(): Promise<BusinessGoals> {
    const response = await apiClient.get<BusinessGoals>('/zapier/business-goals');
    return response.data;
  },

  /**
   * Get company mission statement points
   */
  async getCompanyMission(): Promise<string[]> {
    const response = await apiClient.get<string[]>('/zapier/mission');
    return response.data;
  },

  /**
   * Trigger a refresh of all dashboard data from Zapier sources
   */
  async refreshDashboardData(): Promise<DashboardRefreshResult> {
    const response = await apiClient.post<DashboardRefreshResult>('/zapier/refresh');
    return response.data;
  },
}; 
