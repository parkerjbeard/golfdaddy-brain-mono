// Simplified API exports
// The old token-based system is replaced with Supabase auth

import api from './endpoints';

// Re-export for backward compatibility
export { api };
export default api;

// Export endpoint groups - using lazy evaluation to avoid initialization issues
export const authApi = () => api.auth;
export const usersApi = () => api.users;
export const tasksApi = () => api.tasks;
export const dailyReportsApi = () => api.dailyReports;
export const githubApi = () => api.github;
export const kpiApi = () => api.kpi;
export const developerInsightsApi = () => api.developerInsights;
export const archiveApi = () => api.archive;
export const systemApi = () => api.system;
export const webhookApi = () => api.webhook;
export const batchApi = () => api.batch;
export const searchApi = () => api.search;