/**
 * Main API service with integrated authentication and error handling
 */

import { apiClient } from './base';
import { tokenManager } from './tokenManager';
import api from './endpoints';

// ========== SETUP API CLIENT WITH TOKEN MANAGER ==========

// Set up token manager
apiClient.setTokenManager(tokenManager);

// Add request interceptor for authentication
apiClient.addRequestInterceptor(async ({ method, url, data, headers }) => {
  // Log outgoing requests in development
  if (import.meta.env.NODE_ENV === 'development') {
    console.log(`🌐 API ${method} ${url}`, data);
  }

  return null; // No modifications needed
});

// Add response interceptor for error handling
apiClient.addResponseInterceptor(async (response) => {
  // Log responses in development
  if (import.meta.env.NODE_ENV === 'development') {
    console.log(`✅ API Response ${response.status}`, response.data);
  }

  // Handle special cases
  if (response.status === 401) {
    // Token expired, clear it
    await tokenManager.clearToken();
    
    // Emit event for app to handle
    window.dispatchEvent(new CustomEvent('auth-token-expired', {
      detail: { response }
    }));
  }

  return response;
});

// ========== API INITIALIZATION ==========

export const initializeApi = async () => {
  try {
    // Check if we're in bypass mode
    const bypassAuth = import.meta.env.VITE_BYPASS_AUTH === 'true';
    
    if (bypassAuth) {
      console.log('🔓 API initialized in bypass mode - skipping authentication check');
      return;
    }
    
    // Check if we have a valid token
    const token = await tokenManager.getToken();
    
    if (token) {
      // Verify token is still valid by checking current user
      try {
        await api.auth.getCurrentUser();
        console.log('✅ API initialized with valid authentication');
      } catch (error) {
        console.warn('⚠️ Stored token is invalid, clearing authentication');
        await tokenManager.clearToken();
      }
    } else {
      console.log('ℹ️ API initialized without authentication');
    }
  } catch (error) {
    console.error('❌ Failed to initialize API:', error);
  }
};

// ========== AUTHENTICATION HELPERS ==========

export const authenticateUser = async (email: string, password: string) => {
  try {
    const loginResponse = await api.auth.login({ email, password });
    await tokenManager.setTokenData(loginResponse);
    
    console.log('✅ User authenticated successfully');
    return loginResponse.user;
  } catch (error) {
    console.error('❌ Authentication failed:', error);
    throw error;
  }
};

export const logoutUser = async () => {
  try {
    // Call logout endpoint if we have a token
    const token = await tokenManager.getToken();
    if (token) {
      await api.auth.logout();
    }
  } catch (error) {
    console.warn('⚠️ Logout API call failed:', error);
  } finally {
    // Always clear local token
    await tokenManager.clearToken();
    console.log('✅ User logged out');
  }
};

export const refreshAuthentication = async () => {
  try {
    const newToken = await tokenManager.refreshToken();
    if (newToken) {
      console.log('✅ Authentication refreshed');
      return true;
    } else {
      console.warn('⚠️ Failed to refresh authentication');
      return false;
    }
  } catch (error) {
    console.error('❌ Authentication refresh failed:', error);
    return false;
  }
};

// ========== API STATUS MONITORING ==========

export const getApiStatus = async () => {
  try {
    const health = await api.system.getHealthCheck();
    return {
      status: 'healthy',
      details: health,
    };
  } catch (error) {
    return {
      status: 'unhealthy',
      error: error.message,
    };
  }
};

// ========== ERROR RECOVERY ==========

export const handleApiError = (error: any) => {
  // Log error details
  console.error('API Error:', error);

  // Check for specific error types and provide recovery suggestions
  if (error.name === 'NetworkError') {
    return {
      type: 'network',
      message: 'Network connection failed. Please check your internet connection.',
      canRetry: true,
    };
  }

  if (error.status === 401) {
    return {
      type: 'authentication',
      message: 'Your session has expired. Please log in again.',
      canRetry: false,
      action: 'redirect_to_login',
    };
  }

  if (error.status === 403) {
    return {
      type: 'authorization',
      message: 'You do not have permission to perform this action.',
      canRetry: false,
    };
  }

  if (error.status >= 500) {
    return {
      type: 'server',
      message: 'Server error occurred. Please try again later.',
      canRetry: true,
    };
  }

  if (error.status === 429) {
    return {
      type: 'rate_limit',
      message: 'Too many requests. Please wait before trying again.',
      canRetry: true,
      retryAfter: error.headers?.get('Retry-After') || 60,
    };
  }

  return {
    type: 'unknown',
    message: error.message || 'An unexpected error occurred.',
    canRetry: true,
  };
};

// ========== DEVELOPMENT HELPERS ==========

if (import.meta.env.NODE_ENV === 'development') {
  // Expose API methods to window for debugging
  (window as any).golfDaddyApi = {
    api,
    tokenManager,
    apiClient,
    initializeApi,
    authenticateUser,
    logoutUser,
    refreshAuthentication,
    getApiStatus,
    handleApiError,
  };

  console.log('🔧 Development: API methods exposed to window.golfDaddyApi');
}

// ========== EXPORTS ==========

export { api, apiClient, tokenManager };
export default api;

// Export all endpoint APIs for convenience
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