// API service for making HTTP requests
import { apiClient } from '@/services/api/client';

export interface ApiResponse<T = any> {
  data?: T;
  error?: string;
  status: number;
}

// User management
export const userService = {
  getCurrentUser: async (): Promise<ApiResponse> => {
    return apiClient.get('/auth/me');
  },

  updateProfile: async (data: any): Promise<ApiResponse> => {
    return apiClient.put('/users/profile', data);
  },

  getUsers: async (): Promise<ApiResponse> => {
    return apiClient.get('/users');
  },
};

// Manager dashboard functions
export const getUserPerformanceSummary = async (params?: any): Promise<ApiResponse> => {
  const { userId, ...queryParams } = params || {};
  if (!userId) {
    throw new Error('userId is required for getUserPerformanceSummary');
  }
  const query = new URLSearchParams(queryParams).toString();
  return apiClient.get(`/api/v1/kpi/user-summary/${userId}${query ? `?${query}` : ''}`);
};

export const getBulkWidgetSummaries = async (params?: any): Promise<ApiResponse> => {
  const query = new URLSearchParams(params).toString();
  return apiClient.get(`/api/v1/kpi/performance/widget-summaries${query ? `?${query}` : ''}`);
};

// Daily reports
export const dailyReportsService = {
  getReports: async (params?: any): Promise<ApiResponse> => {
    const query = new URLSearchParams(params).toString();
    return apiClient.get(`/daily-reports${query ? `?${query}` : ''}`);
  },

  createReport: async (data: any): Promise<ApiResponse> => {
    return apiClient.post('/daily-reports', data);
  },

  updateReport: async (id: string, data: any): Promise<ApiResponse> => {
    return apiClient.put(`/daily-reports/${id}`, data);
  },

  deleteReport: async (id: string): Promise<ApiResponse> => {
    return apiClient.delete(`/daily-reports/${id}`);
  },
};

// RACI Matrix
export const raciService = {
  getMatrices: async (): Promise<ApiResponse> => {
    return apiClient.get('/raci-matrices');
  },

  createMatrix: async (data: any): Promise<ApiResponse> => {
    return apiClient.post('/raci-matrices', data);
  },

  updateMatrix: async (id: string, data: any): Promise<ApiResponse> => {
    return apiClient.put(`/raci-matrices/${id}`, data);
  },

  deleteMatrix: async (id: string): Promise<ApiResponse> => {
    return apiClient.delete(`/raci-matrices/${id}`);
  },
};

// Tasks and KPIs
export const taskService = {
  getTasks: async (params?: any): Promise<ApiResponse> => {
    const query = new URLSearchParams(params).toString();
    return apiClient.get(`/tasks${query ? `?${query}` : ''}`);
  },

  createTask: async (data: any): Promise<ApiResponse> => {
    return apiClient.post('/tasks', data);
  },

  updateTask: async (id: string, data: any): Promise<ApiResponse> => {
    return apiClient.put(`/tasks/${id}`, data);
  },

  deleteTask: async (id: string): Promise<ApiResponse> => {
    return apiClient.delete(`/tasks/${id}`);
  },
};

// Analytics and KPIs
export const analyticsService = {
  getDashboardData: async (params?: any): Promise<ApiResponse> => {
    const query = new URLSearchParams(params).toString();
    return apiClient.get(`/analytics/dashboard${query ? `?${query}` : ''}`);
  },

  getKPIs: async (params?: any): Promise<ApiResponse> => {
    const query = new URLSearchParams(params).toString();
    return apiClient.get(`/kpis${query ? `?${query}` : ''}`);
  },

  getMetrics: async (params?: any): Promise<ApiResponse> => {
    const query = new URLSearchParams(params).toString();
    return apiClient.get(`/metrics${query ? `?${query}` : ''}`);
  },
};

// Documentation service
export const documentationService = {
  getDocuments: async (params?: any): Promise<ApiResponse> => {
    const query = new URLSearchParams(params).toString();
    return apiClient.get(`/docs${query ? `?${query}` : ''}`);
  },

  searchDocuments: async (query: string): Promise<ApiResponse> => {
    return apiClient.post('/docs/search', { query });
  },

  createDocument: async (data: any): Promise<ApiResponse> => {
    return apiClient.post('/docs', data);
  },

  updateDocument: async (id: string, data: any): Promise<ApiResponse> => {
    return apiClient.put(`/docs/${id}`, data);
  },

  approveDocument: async (id: string): Promise<ApiResponse> => {
    return apiClient.post(`/docs/${id}/approve`);
  },
};

// Health check
export const healthService = {
  check: async (): Promise<ApiResponse> => {
    return apiClient.get('/health');
  },
};

// Export all services
export default {
  userService,
  dailyReportsService,
  raciService,
  taskService,
  analyticsService,
  documentationService,
  healthService,
};