/**
 * Enhanced API client with automatic JWT token injection and error handling
 */

import { useAuthToken } from '@/hooks/useAuthToken';

export interface ApiClientConfig {
  baseURL?: string;
  timeout?: number;
  headers?: Record<string, string>;
}

export interface ApiResponse<T = any> {
  data: T;
  status: number;
  statusText: string;
  headers: Headers;
}

export interface ApiError {
  message: string;
  status: number;
  statusText: string;
  data?: any;
}

class AuthenticatedApiClient {
  private baseURL: string;
  private timeout: number;
  private defaultHeaders: Record<string, string>;

  constructor(config: ApiClientConfig = {}) {
    this.baseURL = config.baseURL || import.meta.env.VITE_API_BASE_URL || '/api/v1';
    this.timeout = config.timeout || 30000; // 30 seconds
    this.defaultHeaders = {
      'Content-Type': 'application/json',
      ...(config.headers || {}),
    };

    // Add API key if available
    const apiKey = import.meta.env.VITE_API_KEY;
    if (apiKey) {
      this.defaultHeaders['X-API-Key'] = apiKey;
    }
  }

  private buildHeaders(additionalHeaders?: Record<string, string>): Record<string, string> {
    const headers = { ...this.defaultHeaders, ...additionalHeaders };
    
    // Get token from localStorage
    const token = localStorage.getItem('golf_daddy_auth_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    return headers;
  }

  private async makeRequest<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const url = `${this.baseURL}${endpoint}`;
    const headers = this.buildHeaders(options.headers as Record<string, string>);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      const data = response.headers.get('content-type')?.includes('application/json')
        ? await response.json()
        : await response.text();

      if (!response.ok) {
        const apiError: ApiError = {
          message: data.detail || data.message || `HTTP ${response.status}: ${response.statusText}`,
          status: response.status,
          statusText: response.statusText,
          data,
        };

        // Handle specific error cases
        if (response.status === 401) {
          // Token might be expired, remove it
          localStorage.removeItem('golf_daddy_auth_token');
          
          // Emit event for auth system to handle
          window.dispatchEvent(new CustomEvent('auth-token-expired'));
          
          apiError.message = 'Authentication expired. Please log in again.';
        }

        throw apiError;
      }

      return {
        data,
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      };
    } catch (error) {
      clearTimeout(timeoutId);
      
      if (error.name === 'AbortError') {
        throw new Error('Request timeout');
      }
      
      throw error;
    }
  }

  async get<T>(endpoint: string, params?: Record<string, any>): Promise<ApiResponse<T>> {
    const url = params ? `${endpoint}?${new URLSearchParams(params).toString()}` : endpoint;
    return this.makeRequest<T>(url, { method: 'GET' });
  }

  async post<T>(endpoint: string, data?: any): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async put<T>(endpoint: string, data?: any): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async patch<T>(endpoint: string, data?: any): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(endpoint, {
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async delete<T>(endpoint: string): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(endpoint, { method: 'DELETE' });
  }

  // File upload with multipart/form-data
  async uploadFile<T>(endpoint: string, formData: FormData): Promise<ApiResponse<T>> {
    const headers = this.buildHeaders();
    // Remove Content-Type header to let browser set it with boundary
    delete headers['Content-Type'];

    return this.makeRequest<T>(endpoint, {
      method: 'POST',
      headers,
      body: formData,
    });
  }

  // Set base URL dynamically
  setBaseURL(baseURL: string): void {
    this.baseURL = baseURL;
  }

  // Update default headers
  setDefaultHeader(key: string, value: string): void {
    this.defaultHeaders[key] = value;
  }

  // Remove default header
  removeDefaultHeader(key: string): void {
    delete this.defaultHeaders[key];
  }
}

// Create singleton instance
const authApiClient = new AuthenticatedApiClient();

// Custom hook for components to use the API client
export const useAuthenticatedApi = () => {
  const tokenManager = useAuthToken();

  return {
    apiClient: authApiClient,
    tokenManager,
  };
};

export default authApiClient;