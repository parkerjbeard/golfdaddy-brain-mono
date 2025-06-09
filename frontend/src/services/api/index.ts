// Simplified API exports
// The old token-based system is replaced with Supabase auth

import api from './endpoints';

// Re-export for backward compatibility
export { api };
export default api;

// Export endpoint groups
export const {
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
} = api;