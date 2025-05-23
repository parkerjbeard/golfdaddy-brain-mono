/**
 * Comprehensive API endpoints for all backend services
 */

import { apiClient } from './base';
import { 
  // Authentication
  LoginRequest, 
  LoginResponse, 
  RefreshTokenRequest, 
  RefreshTokenResponse,
  
  // Users
  User,
  CreateUserRequest,
  UpdateUserRequest,
  UpdateCurrentUserRequest,
  UserListParams,
  
  // Tasks
  Task,
  CreateTaskRequest,
  CreateTaskResponse,
  UpdateTaskRequest,
  TasksResponse,
  TaskListParams,
  
  // Daily Reports
  DailyReport,
  CreateDailyReportRequest,
  UpdateDailyReportRequest,
  DailyReportsResponse,
  DailyReportListParams,
  
  // Commits
  Commit,
  CreateCommitRequest,
  CompareCommitsResponse,
  GitHubWebhookPayload,
  
  // KPIs
  PerformanceWidgetSummary,
  UserKpiSummary,
  KpiParams,
  
  // Developer Insights
  DeveloperDailySummary,
  
  // Archive
  ArchiveStats,
  RetentionPolicy,
  ArchiveRecord,
  RunArchiveRequest,
  RestoreArchiveRequest,
  UpdateRetentionPolicyRequest,
  
  // System
  HealthCheckResponse,
  
  // Common
  ApiResponse,
  PaginatedResponse,
} from '@/types/api';

// ========== AUTHENTICATION API ==========

export const authApi = {
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await apiClient.post<LoginResponse>('/auth/login', credentials, { skipAuth: true });
    return response.data;
  },

  async refresh(refreshData: RefreshTokenRequest): Promise<RefreshTokenResponse> {
    const response = await apiClient.post<RefreshTokenResponse>('/auth/refresh', refreshData, { skipAuth: true });
    return response.data;
  },

  async getCurrentUser(): Promise<User> {
    const response = await apiClient.get<User>('/auth/me');
    return response.data;
  },

  async logout(): Promise<void> {
    await apiClient.post('/auth/logout');
  },

  async checkAuth(): Promise<boolean> {
    try {
      await this.getCurrentUser();
      return true;
    } catch {
      return false;
    }
  },
};

// ========== USERS API ==========

export const usersApi = {
  async getUsers(params?: UserListParams): Promise<PaginatedResponse<User>> {
    const response = await apiClient.get<User[]>('/users', params);
    return {
      data: response.data,
      total: response.data.length, // TODO: Add total from headers or response
    };
  },

  async getUser(userId: string): Promise<User> {
    const response = await apiClient.get<User>(`/users/${userId}`);
    return response.data;
  },

  async getCurrentUserProfile(): Promise<User> {
    const response = await apiClient.get<User>('/users/me');
    return response.data;
  },

  async createUser(userData: CreateUserRequest): Promise<User> {
    const response = await apiClient.post<User>('/users', userData);
    return response.data;
  },

  async updateUser(userId: string, userData: UpdateUserRequest): Promise<User> {
    const response = await apiClient.put<User>(`/users/${userId}`, userData);
    return response.data;
  },

  async updateCurrentUser(userData: UpdateCurrentUserRequest): Promise<User> {
    const response = await apiClient.put<User>('/users/me', userData);
    return response.data;
  },

  async deleteUser(userId: string): Promise<void> {
    await apiClient.delete(`/users/${userId}`);
  },

  async getUsersByRole(role: string, params?: Partial<UserListParams>): Promise<User[]> {
    const response = await apiClient.get<User[]>('/users', { ...params, role });
    return response.data;
  },

  async searchUsers(query: string, params?: Partial<UserListParams>): Promise<User[]> {
    const response = await apiClient.get<User[]>('/users', { ...params, search: query });
    return response.data;
  },
};

// ========== TASKS API ==========

export const tasksApi = {
  async getTasks(params?: TaskListParams): Promise<TasksResponse> {
    const response = await apiClient.get<TasksResponse>('/tasks', params);
    return response.data;
  },

  async getTask(taskId: string): Promise<Task> {
    const response = await apiClient.get<Task>(`/tasks/${taskId}`);
    return response.data;
  },

  async createTask(taskData: CreateTaskRequest): Promise<CreateTaskResponse> {
    const response = await apiClient.post<CreateTaskResponse>('/tasks', taskData);
    return response.data;
  },

  async updateTask(taskId: string, taskData: UpdateTaskRequest): Promise<Task> {
    const response = await apiClient.put<Task>(`/tasks/${taskId}`, taskData);
    return response.data;
  },

  async deleteTask(taskId: string): Promise<void> {
    await apiClient.delete(`/tasks/${taskId}`);
  },

  async getTasksByAssignee(assigneeId: string, params?: Partial<TaskListParams>): Promise<Task[]> {
    const response = await apiClient.get<TasksResponse>('/tasks', { ...params, assignee_id: assigneeId });
    return response.data.tasks;
  },

  async getTasksByStatus(status: string, params?: Partial<TaskListParams>): Promise<Task[]> {
    const response = await apiClient.get<TasksResponse>('/tasks', { ...params, status });
    return response.data.tasks;
  },

  async getTasksByCreator(creatorId: string, params?: Partial<TaskListParams>): Promise<Task[]> {
    const response = await apiClient.get<TasksResponse>('/tasks', { ...params, creator_id: creatorId });
    return response.data.tasks;
  },

  async bulkUpdateTasks(taskIds: string[], updates: UpdateTaskRequest): Promise<Task[]> {
    const response = await apiClient.put<Task[]>('/tasks/bulk', {
      task_ids: taskIds,
      updates,
    });
    return response.data;
  },

  async bulkDeleteTasks(taskIds: string[]): Promise<void> {
    await apiClient.delete('/tasks/bulk', {
      headers: { 'Content-Type': 'application/json' },
    });
  },

  async assignTask(taskId: string, assigneeId: string): Promise<Task> {
    return this.updateTask(taskId, { assignee_id: assigneeId });
  },

  async updateTaskStatus(taskId: string, status: string): Promise<Task> {
    return this.updateTask(taskId, { status: status as any });
  },

  async blockTask(taskId: string, reason: string): Promise<Task> {
    return this.updateTask(taskId, { blocked: true, blocked_reason: reason });
  },

  async unblockTask(taskId: string): Promise<Task> {
    return this.updateTask(taskId, { blocked: false, blocked_reason: undefined });
  },
};

// ========== DAILY REPORTS API ==========

export const dailyReportsApi = {
  async getReports(params?: DailyReportListParams): Promise<DailyReportsResponse> {
    const response = await apiClient.get<DailyReportsResponse>('/reports/daily/', params);
    return response.data;
  },

  async getMyReports(params?: Partial<DailyReportListParams>): Promise<DailyReport[]> {
    const response = await apiClient.get<DailyReport[]>('/reports/daily/me', params);
    return response.data;
  },

  async getReportByDate(date: string): Promise<DailyReport> {
    const response = await apiClient.get<DailyReport>(`/reports/daily/me/${date}`);
    return response.data;
  },

  async getReport(reportId: string): Promise<DailyReport> {
    const response = await apiClient.get<DailyReport>(`/reports/daily/${reportId}`);
    return response.data;
  },

  async createReport(reportData: CreateDailyReportRequest): Promise<DailyReport> {
    const response = await apiClient.post<DailyReport>('/reports/daily/', reportData);
    return response.data;
  },

  async updateReport(reportId: string, reportData: UpdateDailyReportRequest): Promise<DailyReport> {
    const response = await apiClient.put<DailyReport>(`/reports/daily/${reportId}`, reportData);
    return response.data;
  },

  async deleteReport(reportId: string): Promise<void> {
    await apiClient.delete(`/reports/daily/${reportId}`);
  },

  async getAllReports(params?: DailyReportListParams): Promise<DailyReportsResponse> {
    const response = await apiClient.get<DailyReportsResponse>('/reports/daily/admin/all', params);
    return response.data;
  },

  async getReportsByUser(userId: string, params?: Partial<DailyReportListParams>): Promise<DailyReport[]> {
    const response = await apiClient.get<DailyReportsResponse>('/reports/daily/admin/all', { 
      ...params, 
      user_id: userId 
    });
    return response.data.reports;
  },

  async getReportsByDateRange(startDate: string, endDate: string, params?: Partial<DailyReportListParams>): Promise<DailyReport[]> {
    const response = await apiClient.get<DailyReportsResponse>('/reports/daily/admin/all', {
      ...params,
      start_date: startDate,
      end_date: endDate,
    });
    return response.data.reports;
  },
};

// ========== GITHUB INTEGRATION API ==========

export const githubApi = {
  async processCommitWebhook(payload: GitHubWebhookPayload): Promise<Commit[]> {
    const response = await apiClient.post<Commit[]>('/api/v1/integrations/github/commit', payload, { skipAuth: true });
    return response.data;
  },

  async createCommit(commitData: CreateCommitRequest): Promise<Commit> {
    const response = await apiClient.post<Commit>('/api/v1/integrations/github/commit', commitData);
    return response.data;
  },

  async compareCommits(repository: string, base: string, head: string): Promise<CompareCommitsResponse> {
    const response = await apiClient.get<CompareCommitsResponse>(`/api/v1/integrations/github/compare/${repository}/${base}/${head}`);
    return response.data;
  },

  async getCommitsByUser(userId: string, params?: { start_date?: string; end_date?: string }): Promise<Commit[]> {
    const response = await apiClient.get<Commit[]>('/commits', { ...params, user_id: userId });
    return response.data;
  },

  async getCommitsByRepository(repository: string, params?: { start_date?: string; end_date?: string }): Promise<Commit[]> {
    const response = await apiClient.get<Commit[]>('/commits', { ...params, repository });
    return response.data;
  },
};

// ========== KPI API ==========

export const kpiApi = {
  async testKpi(): Promise<any> {
    const response = await apiClient.get('/api/v1/kpi/test-kpi');
    return response.data;
  },

  async getPerformanceWidgetSummaries(params?: KpiParams): Promise<PerformanceWidgetSummary[]> {
    const response = await apiClient.get<PerformanceWidgetSummary[]>('/api/v1/kpi/performance/widget-summaries', params);
    return response.data;
  },

  async getUserKpiSummary(userId: string, params?: KpiParams): Promise<UserKpiSummary> {
    const response = await apiClient.get<UserKpiSummary>(`/api/v1/kpi/user-summary/${userId}`, params);
    return response.data;
  },

  async getTeamKpiSummary(teamId: string, params?: KpiParams): Promise<UserKpiSummary[]> {
    const response = await apiClient.get<UserKpiSummary[]>('/api/v1/kpi/team-summary', { ...params, team_id: teamId });
    return response.data;
  },

  async getDashboardMetrics(params?: KpiParams): Promise<Record<string, any>> {
    const response = await apiClient.get<Record<string, any>>('/api/v1/kpi/dashboard', params);
    return response.data;
  },
};

// ========== DEVELOPER INSIGHTS API ==========

export const developerInsightsApi = {
  async getDailySummary(userId: string, date: string): Promise<DeveloperDailySummary> {
    const response = await apiClient.get<DeveloperDailySummary>(`/insights/developer/${userId}/daily_summary/${date}`);
    return response.data;
  },

  async getWeeklySummary(userId: string, weekStart: string): Promise<any> {
    const response = await apiClient.get(`/insights/developer/${userId}/weekly_summary/${weekStart}`);
    return response.data;
  },

  async getMonthlySummary(userId: string, month: string): Promise<any> {
    const response = await apiClient.get(`/insights/developer/${userId}/monthly_summary/${month}`);
    return response.data;
  },

  async getTeamInsights(teamId: string, params?: { start_date?: string; end_date?: string }): Promise<any> {
    const response = await apiClient.get('/insights/team', { ...params, team_id: teamId });
    return response.data;
  },

  async getProductivityTrends(userId: string, params?: { days?: number }): Promise<any> {
    const response = await apiClient.get(`/insights/developer/${userId}/productivity-trends`, params);
    return response.data;
  },
};

// ========== ARCHIVE API ==========

export const archiveApi = {
  async runArchive(request?: RunArchiveRequest): Promise<ArchiveStats> {
    const response = await apiClient.post<ArchiveStats>('/api/v1/archive/run', request);
    return response.data;
  },

  async restoreArchive(request: RestoreArchiveRequest): Promise<void> {
    await apiClient.post('/api/v1/archive/restore', request);
  },

  async getArchiveStats(): Promise<ArchiveStats> {
    const response = await apiClient.get<ArchiveStats>('/api/v1/archive/stats');
    return response.data;
  },

  async getRetentionPolicies(): Promise<RetentionPolicy[]> {
    const response = await apiClient.get<RetentionPolicy[]>('/api/v1/archive/policies');
    return response.data;
  },

  async updateRetentionPolicy(request: UpdateRetentionPolicyRequest): Promise<RetentionPolicy> {
    const response = await apiClient.put<RetentionPolicy>('/api/v1/archive/policies', request);
    return response.data;
  },

  async getArchivedRecords(tableName: string, params?: { page?: number; limit?: number }): Promise<PaginatedResponse<ArchiveRecord>> {
    const response = await apiClient.get<ArchiveRecord[]>(`/api/v1/archive/archived/${tableName}`, params);
    return {
      data: response.data,
      total: response.data.length, // TODO: Add total from headers
    };
  },

  async purgeOldArchives(tableName: string, beforeDate?: string): Promise<void> {
    const params = beforeDate ? { before_date: beforeDate } : undefined;
    await apiClient.delete(`/api/v1/archive/purge/${tableName}`, { headers: { 'Content-Type': 'application/json' } });
  },

  async scheduleArchive(cronExpression: string): Promise<void> {
    await apiClient.post('/api/v1/archive/schedule', { cron: cronExpression });
  },

  async getArchiveJobs(): Promise<any[]> {
    const response = await apiClient.get<any[]>('/api/v1/archive/jobs');
    return response.data;
  },
};

// ========== SYSTEM API ==========

export const systemApi = {
  async getHealthCheck(): Promise<HealthCheckResponse> {
    const response = await apiClient.get<HealthCheckResponse>('/health', {}, { skipAuth: true });
    return response.data;
  },

  async getSystemMetrics(): Promise<any> {
    const response = await apiClient.get('/api/v1/system/metrics');
    return response.data;
  },

  async getVersion(): Promise<{ version: string; build: string; deploy_date: string }> {
    const response = await apiClient.get('/api/v1/system/version', {}, { skipAuth: true });
    return response.data;
  },

  async getLogs(params?: { level?: string; limit?: number; since?: string }): Promise<any[]> {
    const response = await apiClient.get<any[]>('/api/v1/system/logs', params);
    return response.data;
  },
};

// ========== WEBHOOK API ==========

export const webhookApi = {
  async processWebhook(type: string, payload: any): Promise<void> {
    await apiClient.post(`/webhooks/${type}`, payload, { skipAuth: true });
  },

  async getWebhookHistory(params?: { limit?: number; type?: string }): Promise<any[]> {
    const response = await apiClient.get<any[]>('/api/v1/webhooks/history', params);
    return response.data;
  },

  async retryWebhook(webhookId: string): Promise<void> {
    await apiClient.post(`/api/v1/webhooks/${webhookId}/retry`);
  },
};

// ========== BATCH OPERATIONS ==========

export const batchApi = {
  async batchCreateTasks(tasks: CreateTaskRequest[]): Promise<CreateTaskResponse[]> {
    const response = await apiClient.post<CreateTaskResponse[]>('/api/v1/batch/tasks/create', { tasks });
    return response.data;
  },

  async batchUpdateTasks(updates: Array<{ id: string; data: UpdateTaskRequest }>): Promise<Task[]> {
    const response = await apiClient.put<Task[]>('/api/v1/batch/tasks/update', { updates });
    return response.data;
  },

  async batchCreateUsers(users: CreateUserRequest[]): Promise<User[]> {
    const response = await apiClient.post<User[]>('/api/v1/batch/users/create', { users });
    return response.data;
  },

  async batchImportData(type: string, data: any[]): Promise<any> {
    const response = await apiClient.post(`/api/v1/batch/import/${type}`, { data });
    return response.data;
  },

  async getBatchJobStatus(jobId: string): Promise<any> {
    const response = await apiClient.get(`/api/v1/batch/jobs/${jobId}/status`);
    return response.data;
  },
};

// ========== SEARCH API ==========

export const searchApi = {
  async globalSearch(query: string, params?: { types?: string[]; limit?: number }): Promise<any> {
    const response = await apiClient.get('/api/v1/search', { q: query, ...params });
    return response.data;
  },

  async searchTasks(query: string, params?: Partial<TaskListParams>): Promise<Task[]> {
    const response = await apiClient.get<TasksResponse>('/tasks', { ...params, search: query });
    return response.data.tasks;
  },

  async searchUsers(query: string, params?: Partial<UserListParams>): Promise<User[]> {
    const response = await apiClient.get<User[]>('/users', { ...params, search: query });
    return response.data;
  },

  async searchReports(query: string, params?: Partial<DailyReportListParams>): Promise<DailyReport[]> {
    const response = await apiClient.get<DailyReportsResponse>('/reports/daily/', { ...params, search: query });
    return response.data.reports;
  },
};

// ========== EXPORT ALL APIs ==========

export const api = {
  auth: authApi,
  users: usersApi,
  tasks: tasksApi,
  dailyReports: dailyReportsApi,
  github: githubApi,
  kpi: kpiApi,
  developerInsights: developerInsightsApi,
  archive: archiveApi,
  system: systemApi,
  webhook: webhookApi,
  batch: batchApi,
  search: searchApi,
};

export default api;