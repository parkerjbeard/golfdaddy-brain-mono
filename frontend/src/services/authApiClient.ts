/**
 * Enhanced API client with automatic JWT token injection and error handling
 * @deprecated Use the new comprehensive API client from @/services/api instead
 */

import { apiClient } from '@/services/api/base';
import { ApiResponse } from '@/types/api';

// Legacy interface for backward compatibility
export interface ApiClientConfig {
  baseURL?: string;
  timeout?: number;
  headers?: Record<string, string>;
}

export interface ApiError {
  message: string;
  status: number;
  statusText: string;
  data?: any;
}

// Legacy class that wraps the new API client
class AuthenticatedApiClient {
  private baseURL: string;
  private timeout: number;
  private defaultHeaders: Record<string, string>;

  constructor(config: ApiClientConfig = {}) {
    console.warn('AuthenticatedApiClient is deprecated. Use the new API client from @/services/api instead.');
    
    this.baseURL = config.baseURL || import.meta.env.VITE_API_BASE_URL || '/api/v1';
    this.timeout = config.timeout || 30000;
    this.defaultHeaders = {
      'Content-Type': 'application/json',
      ...(config.headers || {}),
    };

    // Update the new API client configuration
    apiClient.updateConfig({
      baseURL: this.baseURL,
      timeout: this.timeout,
      headers: this.defaultHeaders,
    });
  }

  // Delegate all methods to the new API client
  async get<T>(endpoint: string, params?: Record<string, any>): Promise<ApiResponse<T>> {
    return apiClient.get<T>(endpoint, params);
  }

  async post<T>(endpoint: string, data?: any): Promise<ApiResponse<T>> {
    return apiClient.post<T>(endpoint, data);
  }

  async put<T>(endpoint: string, data?: any): Promise<ApiResponse<T>> {
    return apiClient.put<T>(endpoint, data);
  }

  async patch<T>(endpoint: string, data?: any): Promise<ApiResponse<T>> {
    return apiClient.patch<T>(endpoint, data);
  }

  async delete<T>(endpoint: string): Promise<ApiResponse<T>> {
    return apiClient.delete<T>(endpoint);
  }

  // File upload with multipart/form-data
  async uploadFile<T>(endpoint: string, formData: FormData): Promise<ApiResponse<T>> {
    const config = { headers: {} as Record<string, string> };
    return apiClient.post<T>(endpoint, formData, config);
  }

  // Set base URL dynamically
  setBaseURL(baseURL: string): void {
    this.baseURL = baseURL;
    apiClient.updateConfig({ baseURL });
  }

  // Update default headers
  setDefaultHeader(key: string, value: string): void {
    this.defaultHeaders[key] = value;
    apiClient.updateConfig({ headers: this.defaultHeaders });
  }

  // Remove default header
  removeDefaultHeader(key: string): void {
    delete this.defaultHeaders[key];
    apiClient.updateConfig({ headers: this.defaultHeaders });
  }
}

// Create singleton instance
const authApiClient = new AuthenticatedApiClient();

// Custom hook for components to use the API client
export const useAuthenticatedApi = () => {
  console.warn('useAuthenticatedApi is deprecated. Use the new API hooks from @/services/api instead.');
  
  return {
    apiClient: authApiClient,
    tokenManager: null, // Deprecated
  };
};

export default authApiClient;