/**
 * Comprehensive API types matching backend models and endpoints
 */

// ========== CORE API TYPES ==========

export interface ApiResponse<T = any> {
  data: T;
  status: number;
  statusText: string;
  headers: Headers;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: string[];
  };
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page?: number;
  limit?: number;
  hasMore?: boolean;
}

// ========== ENUM TYPES ==========

export enum UserRole {
  USER = 'USER',
  DEVELOPER = 'DEVELOPER',
  MANAGER = 'MANAGER',
  ADMIN = 'ADMIN',
}

export enum TaskStatus {
  ASSIGNED = 'ASSIGNED',
  IN_PROGRESS = 'IN_PROGRESS',
  BLOCKED = 'BLOCKED',
  COMPLETED = 'COMPLETED',
}

export enum TaskPriority {
  URGENT = 'URGENT',
  HIGH = 'HIGH',
  MEDIUM = 'MEDIUM',
  LOW = 'LOW',
}

// ========== USER TYPES ==========

export interface User {
  id: string;
  name?: string;
  avatar_url?: string;
  email?: string;
  slack_id?: string;
  github_username?: string;
  role: UserRole;
  team?: string;
  team_id?: string;
  reports_to_id?: string;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
  last_login_at?: string;
  is_active: boolean;
  preferences?: Record<string, any>;
}

export interface CreateUserRequest {
  name?: string;
  email: string;
  role: UserRole;
  team?: string;
  team_id?: string;
  reports_to_id?: string;
  slack_id?: string;
  github_username?: string;
  metadata?: Record<string, any>;
  preferences?: Record<string, any>;
}

export interface UpdateUserRequest {
  name?: string;
  email?: string;
  role?: UserRole;
  team?: string;
  team_id?: string;
  reports_to_id?: string;
  slack_id?: string;
  github_username?: string;
  metadata?: Record<string, any>;
  preferences?: Record<string, any>;
  is_active?: boolean;
}

export interface UpdateCurrentUserRequest {
  name?: string;
  preferences?: Record<string, any>;
}

// ========== TASK TYPES ==========

export interface Task {
  id: string;
  title: string;
  description: string;
  assignee_id?: string;
  status: TaskStatus;
  priority: TaskPriority;
  task_type?: string;
  // RACI roles
  responsible_id?: string;
  accountable_id?: string;
  consulted_ids?: string[];
  informed_ids?: string[];
  creator_id: string;
  due_date?: string;
  estimated_hours?: number;
  actual_hours?: number;
  tags?: string[];
  metadata?: Record<string, any>;
  blocked: boolean;
  blocked_reason?: string;
  doc_references?: string[];
  created_at: string;
  updated_at: string;
  
  // Optional populated relationships
  assignee?: User;
  responsible?: User;
  accountable?: User;
  consulted?: User[];
  informed?: User[];
  creator?: User;
}

export interface CreateTaskRequest {
  title: string;
  description: string;
  assignee_id?: string;
  priority?: TaskPriority;
  task_type?: string;
  responsible_id?: string;
  accountable_id?: string;
  consulted_ids?: string[];
  informed_ids?: string[];
  due_date?: string;
  estimated_hours?: number;
  tags?: string[];
  metadata?: Record<string, any>;
}

export interface CreateTaskResponse {
  task: Task;
  warnings: string[];
}

export interface UpdateTaskRequest {
  title?: string;
  description?: string;
  assignee_id?: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  task_type?: string;
  responsible_id?: string;
  accountable_id?: string;
  consulted_ids?: string[];
  informed_ids?: string[];
  due_date?: string;
  estimated_hours?: number;
  actual_hours?: number;
  tags?: string[];
  metadata?: Record<string, any>;
  blocked?: boolean;
  blocked_reason?: string;
  doc_references?: string[];
}

export interface TaskFilters {
  assignee_id?: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  creator_id?: string;
  responsible_id?: string;
  accountable_id?: string;
  blocked?: boolean;
  tags?: string[];
  due_before?: string;
  due_after?: string;
  created_after?: string;
  created_before?: string;
}

export interface TasksResponse {
  tasks: Task[];
  total: number;
}

// ========== DAILY REPORT TYPES ==========

export interface AiAnalysis {
  sentiment_analysis?: {
    overall_mood: string;
    confidence_score: number;
    key_emotions: string[];
  };
  productivity_insights?: {
    estimated_productivity_score: number;
    key_accomplishments: string[];
    potential_blockers: string[];
  };
  collaboration_insights?: {
    team_interactions: string[];
    communication_quality: string;
    knowledge_sharing: string[];
  };
  recommendations?: {
    immediate_actions: string[];
    process_improvements: string[];
    skill_development: string[];
  };
  risk_flags?: {
    burnout_indicators: string[];
    scope_creep_signs: string[];
    resource_constraints: string[];
  };
}

export interface DailyReport {
  id: string;
  user_id: string;
  report_date: string;
  raw_text_input: string;
  clarified_tasks_summary?: string;
  ai_analysis?: AiAnalysis;
  linked_commit_ids: string[];
  overall_assessment_notes?: string;
  final_estimated_hours?: number;
  created_at: string;
  updated_at: string;
  
  // Optional populated relationships
  user?: User;
}

export interface CreateDailyReportRequest {
  report_date: string;
  raw_text_input: string;
  clarified_tasks_summary?: string;
  overall_assessment_notes?: string;
  final_estimated_hours?: number;
}

export interface UpdateDailyReportRequest {
  raw_text_input?: string;
  clarified_tasks_summary?: string;
  overall_assessment_notes?: string;
  final_estimated_hours?: number;
}

export interface DailyReportsResponse {
  reports: DailyReport[];
  total: number;
}

// ========== COMMIT TYPES ==========

export interface Commit {
  id: string;
  sha: string;
  repository: string;
  author_email: string;
  author_name: string;
  message: string;
  timestamp: string;
  files_changed: string[];
  additions: number;
  deletions: number;
  ai_analysis?: {
    summary: string;
    impact_assessment: string;
    code_quality_notes: string[];
    potential_issues: string[];
  };
  created_at: string;
  updated_at: string;
}

export interface CreateCommitRequest {
  sha: string;
  repository: string;
  author_email: string;
  author_name: string;
  message: string;
  timestamp: string;
  files_changed: string[];
  additions: number;
  deletions: number;
}

// ========== KPI TYPES ==========

export interface PerformanceWidgetSummary {
  widget_type: string;
  title: string;
  data: Record<string, any>;
  metadata: {
    last_updated: string;
    data_quality: string;
    confidence_score?: number;
  };
}

export interface UserKpiSummary {
  user_id: string;
  date_range: {
    start_date: string;
    end_date: string;
  };
  metrics: {
    tasks_completed: number;
    commits_made: number;
    lines_of_code: number;
    reports_submitted: number;
    productivity_score: number;
  };
  trends: {
    productivity_trend: 'up' | 'down' | 'stable';
    engagement_trend: 'up' | 'down' | 'stable';
    quality_trend: 'up' | 'down' | 'stable';
  };
  insights: string[];
}

// ========== DEVELOPER INSIGHTS TYPES ==========

export interface DeveloperDailySummary {
  user_id: string;
  date: string;
  summary: {
    tasks_worked_on: number;
    commits_made: number;
    lines_added: number;
    lines_removed: number;
    hours_logged: number;
  };
  detailed_activities: {
    tasks: Task[];
    commits: Commit[];
    reports: DailyReport[];
  };
  ai_insights: {
    productivity_assessment: string;
    code_quality_notes: string[];
    recommendations: string[];
    risk_indicators: string[];
  };
  collaboration_metrics: {
    code_reviews: number;
    team_interactions: number;
    knowledge_sharing_instances: number;
  };
}

// ========== ARCHIVE TYPES ==========

export interface ArchiveStats {
  archived_records: Record<string, number>;
  storage_freed: string;
  last_archive_run: string;
  next_scheduled_run?: string;
}

export interface RetentionPolicy {
  table_name: string;
  retention_months: number;
  archive_enabled: boolean;
  last_archived: string;
  description: string;
}

export interface ArchiveRecord {
  id: string;
  original_table: string;
  archived_at: string;
  archive_reason: string;
  data_snapshot: Record<string, any>;
  can_restore: boolean;
}

export interface RunArchiveRequest {
  dry_run?: boolean;
  tables?: string[];
  force?: boolean;
}

export interface RestoreArchiveRequest {
  table_name: string;
  record_ids: string[];
  force?: boolean;
}

export interface UpdateRetentionPolicyRequest {
  table_name: string;
  retention_months: number;
  archive_enabled: boolean;
}

// ========== AUTHENTICATION TYPES ==========

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

export interface RefreshTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// ========== GITHUB INTEGRATION TYPES ==========

export interface GitHubWebhookPayload {
  repository: {
    name: string;
    full_name: string;
  };
  commits: Array<{
    id: string;
    message: string;
    author: {
      name: string;
      email: string;
    };
    timestamp: string;
    added: string[];
    removed: string[];
    modified: string[];
  }>;
}

export interface CompareCommitsResponse {
  ahead_by: number;
  behind_by: number;
  commits: Commit[];
  files: Array<{
    filename: string;
    status: string;
    additions: number;
    deletions: number;
    changes: number;
  }>;
}

// ========== API REQUEST PARAMS ==========

export interface PaginationParams {
  page?: number;
  limit?: number;
  offset?: number;
}

export interface SortParams {
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface DateRangeParams {
  start_date?: string;
  end_date?: string;
}

export interface UserListParams extends PaginationParams, SortParams {
  role?: UserRole;
  team?: string;
  is_active?: boolean;
  search?: string;
}

export interface TaskListParams extends PaginationParams, SortParams, TaskFilters {
  search?: string;
  include_relationships?: boolean;
}

export interface DailyReportListParams extends PaginationParams, SortParams, DateRangeParams {
  user_id?: string;
}

export interface KpiParams extends DateRangeParams {
  widget_types?: string[];
  include_metadata?: boolean;
}

// ========== HEALTH CHECK TYPES ==========

export interface HealthCheckResponse {
  status: 'healthy' | 'unhealthy';
  timestamp: string;
  version: string;
  services: {
    database: 'up' | 'down';
    auth: 'up' | 'down';
    ai_service: 'up' | 'down';
    github_integration: 'up' | 'down';
  };
  metrics: {
    uptime: number;
    memory_usage: number;
    cpu_usage: number;
    active_connections: number;
  };
}

// ========== WEBHOOK TYPES ==========

export interface WebhookEvent {
  id: string;
  type: 'github.push' | 'github.pull_request' | 'slack.message' | 'make.workflow';
  source: string;
  timestamp: string;
  payload: Record<string, any>;
  processed: boolean;
  processing_errors?: string[];
}
