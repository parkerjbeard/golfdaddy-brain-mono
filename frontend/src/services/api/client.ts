import { supabase } from '../../lib/supabaseClient'
import logger from '../../utils/logger'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

// Log API configuration on load
logger.info('API Client initialized', 'api-client', {
  baseUrl: API_BASE_URL,
  environment: import.meta.env.MODE
});

// Resolve URL without double-prefixing
const getApiUrl = (endpoint: string) => {
  // If caller already passed a rooted API path, keep it
  if (
    endpoint.startsWith('/api') ||
    endpoint.startsWith('/auth') ||
    endpoint.startsWith('/dev') ||
    endpoint.startsWith('/test')
  ) {
    return endpoint;
  }
  // Otherwise, prefix with configured base (defaults to /api/v1)
  return `${API_BASE_URL}${endpoint}`;
}

export interface ApiResponse<T = any> {
  data?: T
  error?: string
  status: number
}

class ApiClient {
  private baseURL: string

  constructor(baseURL: string) {
    this.baseURL = baseURL
  }

  private async getAuthToken(): Promise<string | null> {
    const { data: { session } } = await supabase.auth.getSession()
    return session?.access_token || null
  }

  private async request<T = any>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const startTime = performance.now();
    const method = options.method || 'GET';
    
    try {
      const token = await this.getAuthToken()
      
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
        ...options.headers,
      }

      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      // Add API key if configured
      const apiKey = import.meta.env.VITE_API_KEY
      if (apiKey) {
        headers['X-API-Key'] = apiKey
      }

      const url = getApiUrl(endpoint);
      
      // Log request
      logger.logApiRequest(method, url, options.body ? JSON.parse(options.body as string) : undefined);
      
      const response = await fetch(url, {
        ...options,
        headers,
      })

      const data = response.ok && response.headers.get('content-type')?.includes('application/json')
        ? await response.json()
        : null

      // Log response
      const duration = performance.now() - startTime;
      logger.logApiResponse(method, url, response.status, data);
      logger.logPerformance(`API ${method} ${endpoint}`, duration);

      if (!response.ok) {
        const errorMsg = data?.detail || data?.message || `Request failed with status ${response.status}`;
        logger.logApiError(method, url, { status: response.status, error: errorMsg, data });
        return {
          error: errorMsg,
          status: response.status,
        }
      }

      return {
        data,
        status: response.status,
      }
    } catch (error) {
      logger.logApiError(method, endpoint, error);
      console.error('API request failed:', error)
      return {
        error: error instanceof Error ? error.message : 'Network error',
        status: 0,
      }
    }
  }

  async get<T = any>(endpoint: string): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'GET' })
  }

  async post<T = any>(endpoint: string, body?: any): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    })
  }

  async put<T = any>(endpoint: string, body?: any): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    })
  }

  async patch<T = any>(endpoint: string, body?: any): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
    })
  }

  async delete<T = any>(endpoint: string): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'DELETE' })
  }
}

export const apiClient = new ApiClient(API_BASE_URL) 
