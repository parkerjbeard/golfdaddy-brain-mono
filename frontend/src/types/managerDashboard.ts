export interface User {
  id: string;
  name: string; // Assuming users have a display name
  email?: string;
  // Add other relevant user fields if needed, e.g., role
}

export interface EodReportDetail {
  report_date: string;
  reported_hours: number;
  ai_summary: string | null;
  ai_estimated_hours: number;
  clarification_requests_count: number;
}

export interface CommitComparisonInsight {
  commit_hash: string;
  commit_timestamp: string;
  notes: string;
}

export interface UserPerformanceSummary {
  user_id: string;
  period_start_date: string;
  period_end_date: string;
  total_eod_reported_hours: number;
  eod_report_details: EodReportDetail[];
  total_commits_in_period: number;
  total_commit_ai_estimated_hours: number;
  average_commit_seniority_score: number;
  commit_comparison_insights: CommitComparisonInsight[];
}

// For API request parameters
export interface PerformanceSummaryParams {
  userId: string;
  periodDays?: number;
  startDate?: string;
  endDate?: string;
}

// New type for the bulk widget summaries
export interface UserWidgetSummary {
  user_id: string; 
  name?: string | null;
  avatar_url?: string | null;
  total_ai_estimated_commit_hours: number;
} 