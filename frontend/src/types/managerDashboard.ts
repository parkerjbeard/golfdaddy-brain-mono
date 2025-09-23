export interface User {
  id: string;
  name: string;
  email?: string;
}

export interface EodReportDetail {
  report_date: string;
  reported_hours: number;
  ai_summary: string | null;
  ai_estimated_hours: number;
  clarification_requests_count: number;
}

export interface PullRequestDetail {
  pr_number: number;
  title?: string | null;
  status: string;
  activity_timestamp?: string | null;
  ai_summary?: string | null;
  ai_prompts: string[];
  impact_score: number;
  ai_estimated_hours: number;
  url?: string | null;
  repository_name?: string | null;
  review_comments?: number | null;
}

export interface UserPerformanceSummary {
  user_id: string;
  period_start_date: string;
  period_end_date: string;
  total_prs_in_period: number;
  merged_prs_in_period: number;
  total_ai_estimated_pr_hours: number;
  total_business_points: number;
  efficiency_points_per_hour: number;
  normalized_efficiency_points_per_hour?: number;
  efficiency_provisional?: boolean;
  efficiency_baseline_source?: string;
  activity_score: number;
  average_pr_turnaround_hours: number;
  daily_hours_series: { date: string; hours: number }[];
  daily_points_series: { date: string; points: number }[];
  daily_prs_series: { date: string; count: number }[];
  pr_details: PullRequestDetail[];
  top_prs_by_impact: PullRequestDetail[];
  day_off_dates: string[];
  total_eod_reported_hours: number;
  eod_report_details: EodReportDetail[];
}

export interface PerformanceSummaryParams {
  userId: string;
  periodDays?: number;
  startDate?: string;
  endDate?: string;
}

export interface UserWidgetSummary {
  user_id: string;
  name?: string | null;
  avatar_url?: string | null;
  total_prs: number;
  merged_prs: number;
  total_ai_estimated_pr_hours: number;
  total_business_points: number;
  efficiency_points_per_hour: number;
  normalized_efficiency_points_per_hour?: number;
  efficiency_provisional?: boolean;
  efficiency_baseline_source?: string;
  activity_score: number;
  day_off: boolean;
  daily_prs_series: { date: string; count: number }[];
  daily_hours_series: { date: string; hours: number }[];
  daily_points_series: { date: string; points: number }[];
  latest_activity_timestamp?: string | null;
  latest_pr_title?: string | null;
}
