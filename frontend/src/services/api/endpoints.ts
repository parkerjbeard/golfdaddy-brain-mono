import { apiClient } from './client'

// Helper to create endpoint methods that unwrap API responses
const createEndpoint = (basePath: string) => ({
  getAll: async (params?: any) => {
    const queryString = params ? `?${new URLSearchParams(params).toString()}` : '';
    const result = await apiClient.get(`${basePath}${queryString}`);
    if (result.error) throw new Error(result.error);
    return result.data;
  },
  get: async (id: string) => {
    const result = await apiClient.get(`${basePath}/${id}`);
    if (result.error) throw new Error(result.error);
    return result.data;
  },
  create: async (data: any) => {
    const result = await apiClient.post(basePath, data);
    if (result.error) throw new Error(result.error);
    return result.data;
  },
  update: async (id: string, data: any) => {
    const result = await apiClient.put(`${basePath}/${id}`, data);
    if (result.error) throw new Error(result.error);
    return result.data;
  },
  patch: async (id: string, data: any) => {
    const result = await apiClient.patch(`${basePath}/${id}`, data);
    if (result.error) throw new Error(result.error);
    return result.data;
  },
  delete: async (id: string) => {
    const result = await apiClient.delete(`${basePath}/${id}`);
    if (result.error) throw new Error(result.error);
    return result.data;
  },
});

// Auth endpoints - using the actual backend routes
const auth = {
  login: (credentials: { email: string; password: string }) => 
    apiClient.post('/api/auth/login', credentials),
  logout: () => apiClient.post('/api/auth/logout'),
  getCurrentUser: async () => {
    const result = await apiClient.get('/api/auth/me');
    if (result.error) throw new Error(result.error);
    return result.data;
  },
  register: (data: any) => apiClient.post('/api/auth/register', data),
};

// User endpoints
const users = {
  ...createEndpoint('/api/v1/users'),
  getCurrentUserProfile: async () => {
    const result = await apiClient.get('/api/v1/users/me');
    if (result.error) throw new Error(result.error);
    return result.data;
  },
  updateCurrentUser: async (data: any) => {
    const result = await apiClient.patch('/api/v1/users/me', data);
    if (result.error) throw new Error(result.error);
    return result.data;
  },
  getUsersByRole: async (role: string) => {
    const result = await apiClient.get(`/api/v1/users/by-role/${role}`);
    if (result.error) throw new Error(result.error);
    return result.data;
  },
  searchUsers: async (query: string) => {
    const result = await apiClient.get(`/api/v1/users/search?q=${query}`);
    if (result.error) throw new Error(result.error);
    return result.data;
  },
  getUsers: async (params?: any) => {
    const queryString = params ? `?${new URLSearchParams(params).toString()}` : '';
    const result = await apiClient.get(`/api/v1/users${queryString}`);
    if (result.error) throw new Error(result.error);
    return result.data;
  },
  getUser: async (id: string) => {
    const result = await apiClient.get(`/api/v1/users/${id}`);
    if (result.error) throw new Error(result.error);
    return result.data;
  },
  createUser: async (data: any) => {
    const result = await apiClient.post('/api/v1/users', data);
    if (result.error) throw new Error(result.error);
    return result.data;
  },
  updateUser: async (id: string, data: any) => {
    const result = await apiClient.put(`/api/v1/users/${id}`, data);
    if (result.error) throw new Error(result.error);
    return result.data;
  },
  deleteUser: async (id: string) => {
    const result = await apiClient.delete(`/api/v1/users/${id}`);
    if (result.error) throw new Error(result.error);
    return result.data;
  },
};



// Daily reports endpoints
const dailyReports = {
  ...createEndpoint('/api/daily-reports'),
  getReports: (params?: any) => {
    const queryString = params ? `?${new URLSearchParams(params).toString()}` : '';
    return apiClient.get(`/api/daily-reports${queryString}`);
  },
  createReport: (data: any) => apiClient.post('/api/daily-reports', data),
  updateReport: (id: string, data: any) => apiClient.put(`/api/daily-reports/${id}`, data),
  deleteReport: (id: string) => apiClient.delete(`/api/daily-reports/${id}`),
  getMyReports: () => apiClient.get('/api/daily-reports/mine'),
  getReportByDate: (date: string) => apiClient.get(`/api/daily-reports/date/${date}`),
  getReportsByUser: (userId: string) => apiClient.get(`/api/daily-reports/user/${userId}`),
  getReportsByDateRange: (start: string, end: string) => 
    apiClient.get(`/api/daily-reports/range?start=${start}&end=${end}`),
};

// KPI endpoints
const kpi = {
  getMetrics: () => apiClient.get('/api/kpi/metrics'),
  getDashboard: () => apiClient.get('/api/kpi/dashboard'),
  getTeamMetrics: (teamId: string) => apiClient.get(`/api/kpi/team/${teamId}`),
  getUserMetrics: (userId: string) => apiClient.get(`/api/kpi/user/${userId}`),
};

// Developer insights endpoints
const developerInsights = {
  getInsights: (userId?: string) => 
    apiClient.get(userId ? `/api/developer-insights/${userId}` : '/api/developer-insights'),
  getTeamInsights: (teamId: string) => apiClient.get(`/api/developer-insights/team/${teamId}`),
  getCommitAnalysis: (userId: string, days: number = 30) => 
    apiClient.get(`/api/developer-insights/${userId}/commits?days=${days}`),
};

// GitHub endpoints
const github = {
  getEvents: () => apiClient.get('/api/github/events'),
  syncRepository: (repo: string) => apiClient.post('/api/github/sync', { repository: repo }),
  getCommits: (params?: any) => {
    const queryString = params ? `?${new URLSearchParams(params).toString()}` : '';
    return apiClient.get(`/api/github/commits${queryString}`);
  },
};

// Archive endpoints
const archive = {
  archiveOldData: (days: number) => apiClient.post('/api/archive/old-data', { days }),
  getArchiveStatus: () => apiClient.get('/api/archive/status'),
};

// System endpoints
const system = {
  getHealthCheck: () => apiClient.get('/api/health'),
  getStatus: () => apiClient.get('/api/status'),
  getVersion: () => apiClient.get('/api/version'),
};

// Webhook endpoints
const webhook = {
  github: (data: any) => apiClient.post('/api/webhooks/github', data),
  slack: (data: any) => apiClient.post('/api/webhooks/slack', data),
};

// Batch operations
const batch = {
  execute: (operations: any[]) => apiClient.post('/api/batch', { operations }),
};

// Search endpoints
const search = {
  globalSearch: (query: string, params?: any) => {
    const additionalParams = params ? `&${new URLSearchParams(params).toString()}` : '';
    return apiClient.get(`/api/search?q=${query}${additionalParams}`);
  },
  searchUsers: (query: string, params?: any) => {
    const additionalParams = params ? `&${new URLSearchParams(params).toString()}` : '';
    return apiClient.get(`/api/search/users?q=${query}${additionalParams}`);
  },
};

// Documentation approvals endpoints
const docApprovals = {
  list: (params?: { status?: string; repo?: string; limit?: number; offset?: number }) => {
    const qs = params ? `?${new URLSearchParams(params as any).toString()}` : ''
    return apiClient.get(`/api/v1/doc-approvals${qs}`)
  },
  get: (id: string) => apiClient.get(`/api/v1/doc-approvals/${id}`),
  approve: (id: string) => apiClient.post(`/api/v1/doc-approvals/${id}/approve`),
  reject: (id: string, reason: string) => apiClient.post(`/api/v1/doc-approvals/${id}/reject`, { reason }),
}

export const api = {
  auth,
  users,
  dailyReports,
  github,
  kpi,
  developerInsights,
  archive,
  system,
  webhook,
  batch,
  search,
  docApprovals,
};

export default api;