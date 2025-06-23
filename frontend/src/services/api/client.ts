import { supabase } from '../../lib/supabaseClient'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

// Use proxy in development
const getApiUrl = (endpoint: string) => {
  // In development, use the Vite proxy for /api, /auth, /dev, /test paths
  if (import.meta.env.DEV && (endpoint.startsWith('/api') || endpoint.startsWith('/auth') || endpoint.startsWith('/dev') || endpoint.startsWith('/test'))) {
    return endpoint;
  }
  // In production or for non-proxied requests, use full URL
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
      const response = await fetch(url, {
        ...options,
        headers,
      })

      const data = response.ok && response.headers.get('content-type')?.includes('application/json')
        ? await response.json()
        : null

      if (!response.ok) {
        return {
          error: data?.detail || data?.message || `Request failed with status ${response.status}`,
          status: response.status,
        }
      }

      return {
        data,
        status: response.status,
      }
    } catch (error) {
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