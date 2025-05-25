/**
 * Enhanced API client with comprehensive error handling, retry mechanisms, and authentication
 */

import { ApiResponse, ApiError } from '@/types/api';
import { createEnhancedError, ErrorCategory, ErrorSeverity, EnhancedStoreError } from '@/store/utils/errorHandling';

export interface ApiClientConfig {
  baseURL: string;
  timeout: number;
  retries: number;
  retryDelay: number;
  retryMultiplier: number;
  headers: Record<string, string>;
  enableLogging: boolean;
}

export interface RequestConfig {
  timeout?: number;
  retries?: number;
  skipAuth?: boolean;
  skipRetry?: boolean;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

export interface RetryConfig {
  maxRetries: number;
  baseDelay: number;
  maxDelay: number;
  multiplier: number;
  retryableStatuses: number[];
  retryableErrors: string[];
}

const DEFAULT_CONFIG: ApiClientConfig = {
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  retries: 3,
  retryDelay: 1000,
  retryMultiplier: 2,
  headers: {
    'Content-Type': 'application/json',
  },
  enableLogging: import.meta.env.NODE_ENV === 'development',
};

const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  baseDelay: 1000,
  maxDelay: 10000,
  multiplier: 2,
  retryableStatuses: [408, 429, 500, 502, 503, 504],
  retryableErrors: ['NetworkError', 'TimeoutError', 'AbortError'],
};

export class ApiClient {
  private config: ApiClientConfig;
  private retryConfig: RetryConfig;
  private tokenManager: TokenManager | null = null;
  private requestInterceptors: RequestInterceptor[] = [];
  private responseInterceptors: ResponseInterceptor[] = [];

  constructor(config?: Partial<ApiClientConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.retryConfig = DEFAULT_RETRY_CONFIG;
  }

  // ========== CONFIGURATION ==========

  setTokenManager(tokenManager: TokenManager): void {
    this.tokenManager = tokenManager;
  }

  addRequestInterceptor(interceptor: RequestInterceptor): void {
    this.requestInterceptors.push(interceptor);
  }

  addResponseInterceptor(interceptor: ResponseInterceptor): void {
    this.responseInterceptors.push(interceptor);
  }

  updateConfig(config: Partial<ApiClientConfig>): void {
    this.config = { ...this.config, ...config };
  }

  updateRetryConfig(config: Partial<RetryConfig>): void {
    this.retryConfig = { ...this.retryConfig, ...config };
  }

  // ========== HTTP METHODS ==========

  async get<T>(url: string, params?: Record<string, any>, config?: RequestConfig): Promise<ApiResponse<T>> {
    const searchParams = params ? new URLSearchParams(this.flattenParams(params)).toString() : '';
    const fullUrl = searchParams ? `${url}?${searchParams}` : url;
    return this.request<T>('GET', fullUrl, undefined, config);
  }

  async post<T>(url: string, data?: any, config?: RequestConfig): Promise<ApiResponse<T>> {
    return this.request<T>('POST', url, data, config);
  }

  async put<T>(url: string, data?: any, config?: RequestConfig): Promise<ApiResponse<T>> {
    return this.request<T>('PUT', url, data, config);
  }

  async patch<T>(url: string, data?: any, config?: RequestConfig): Promise<ApiResponse<T>> {
    return this.request<T>('PATCH', url, data, config);
  }

  async delete<T>(url: string, config?: RequestConfig): Promise<ApiResponse<T>> {
    return this.request<T>('DELETE', url, undefined, config);
  }

  // ========== CORE REQUEST METHOD ==========

  private async request<T>(
    method: string,
    url: string,
    data?: any,
    config: RequestConfig = {}
  ): Promise<ApiResponse<T>> {
    const requestId = this.generateRequestId();
    const startTime = Date.now();

    try {
      const response = await this.executeWithRetry(
        () => this.executeRequest<T>(method, url, data, config, requestId),
        config.retries ?? this.config.retries,
        config.skipRetry ?? false
      );

      this.logRequest(requestId, method, url, Date.now() - startTime, response.status);
      return response;
    } catch (error) {
      this.logRequest(requestId, method, url, Date.now() - startTime, 0, error);
      throw this.enhanceError(error, method, url, requestId);
    }
  }

  private async executeRequest<T>(
    method: string,
    url: string,
    data?: any,
    config: RequestConfig = {},
    requestId: string = ''
  ): Promise<ApiResponse<T>> {
    // Build full URL
    const fullUrl = url.startsWith('http') ? url : `${this.config.baseURL}${url}`;

    // Prepare headers
    const headers = await this.buildHeaders(config);

    // Apply request interceptors
    let requestData = data;
    for (const interceptor of this.requestInterceptors) {
      const result = await interceptor({ method, url: fullUrl, data: requestData, headers });
      if (result) {
        requestData = result.data;
        Object.assign(headers, result.headers || {});
      }
    }

    // Setup request options
    const requestOptions: RequestInit = {
      method,
      headers,
      signal: config.signal,
    };

    if (requestData !== undefined) {
      if (requestData instanceof FormData) {
        requestOptions.body = requestData;
        delete headers['Content-Type']; // Let browser set it with boundary
      } else {
        requestOptions.body = JSON.stringify(requestData);
      }
    }

    // Create timeout controller
    const timeoutController = new AbortController();
    const timeout = config.timeout ?? this.config.timeout;
    const timeoutId = setTimeout(() => timeoutController.abort(), timeout);

    try {
      // Combine signals if both exist
      if (config.signal && !config.signal.aborted) {
        const combinedController = new AbortController();
        const abortHandler = () => combinedController.abort();
        
        config.signal.addEventListener('abort', abortHandler);
        timeoutController.signal.addEventListener('abort', abortHandler);
        
        requestOptions.signal = combinedController.signal;
      } else {
        requestOptions.signal = timeoutController.signal;
      }

      // Execute request
      const response = await fetch(fullUrl, requestOptions);
      clearTimeout(timeoutId);

      // Parse response
      const apiResponse = await this.parseResponse<T>(response);

      // Apply response interceptors
      let finalResponse = apiResponse;
      for (const interceptor of this.responseInterceptors) {
        const result = await interceptor(finalResponse);
        if (result) {
          finalResponse = result;
        }
      }

      return finalResponse;
    } catch (error) {
      clearTimeout(timeoutId);
      throw error;
    }
  }

  // ========== RETRY MECHANISM ==========

  private async executeWithRetry<T>(
    operation: () => Promise<T>,
    maxRetries: number,
    skipRetry: boolean
  ): Promise<T> {
    if (skipRetry) {
      return operation();
    }

    let lastError: Error;
    let attempt = 0;

    while (attempt <= maxRetries) {
      try {
        return await operation();
      } catch (error) {
        lastError = error as Error;
        attempt++;

        if (attempt > maxRetries || !this.shouldRetry(error, attempt)) {
          throw error;
        }

        const delay = this.calculateDelay(attempt);
        await this.sleep(delay);

        if (this.config.enableLogging) {
          console.warn(`Retrying request (attempt ${attempt}/${maxRetries}) after ${delay}ms delay`, error);
        }
      }
    }

    throw lastError!;
  }

  private shouldRetry(error: any, attempt: number): boolean {
    if (attempt > this.retryConfig.maxRetries) {
      return false;
    }

    // Don't retry certain error types
    if (error.name === 'AbortError') {
      return false;
    }

    // Check if status code is retryable
    if (error.status && this.retryConfig.retryableStatuses.includes(error.status)) {
      return true;
    }

    // Check if error type is retryable
    if (this.retryConfig.retryableErrors.includes(error.name)) {
      return true;
    }

    // Network errors are generally retryable
    if (!navigator.onLine || error.message?.includes('network')) {
      return true;
    }

    return false;
  }

  private calculateDelay(attempt: number): number {
    const delay = this.retryConfig.baseDelay * Math.pow(this.retryConfig.multiplier, attempt - 1);
    const jitter = Math.random() * 0.1 * delay; // Add 10% jitter
    return Math.min(delay + jitter, this.retryConfig.maxDelay);
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // ========== RESPONSE PARSING ==========

  private async parseResponse<T>(response: Response): Promise<ApiResponse<T>> {
    const contentType = response.headers.get('Content-Type') || '';
    let data: T;

    try {
      if (contentType.includes('application/json')) {
        const jsonData = await response.json();
        
        if (!response.ok) {
          // Handle API error response
          throw new ApiResponseError(jsonData, response.status, response.statusText);
        }
        
        data = jsonData;
      } else if (contentType.includes('text/')) {
        data = (await response.text()) as T;
      } else {
        data = (await response.blob()) as T;
      }
    } catch (error) {
      if (error instanceof ApiResponseError) {
        throw error;
      }
      throw new Error(`Failed to parse response: ${error.message}`);
    }

    if (!response.ok) {
      throw new ApiResponseError(
        { error: { code: 'HTTP_ERROR', message: response.statusText } },
        response.status,
        response.statusText
      );
    }

    return {
      data,
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    };
  }

  // ========== AUTHENTICATION ==========

  private async buildHeaders(config: RequestConfig): Promise<Record<string, string>> {
    const headers = {
      ...this.config.headers,
      ...config.headers,
    };

    // Add authentication token if not skipped
    if (!config.skipAuth && this.tokenManager) {
      const token = await this.tokenManager.getToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
    }

    // Add API key if configured
    const apiKey = import.meta.env.VITE_API_KEY;
    if (apiKey) {
      headers['X-API-Key'] = apiKey;
    }

    return headers;
  }

  // ========== UTILITIES ==========

  private flattenParams(params: Record<string, any>): Record<string, string> {
    const flattened: Record<string, string> = {};
    
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        if (Array.isArray(value)) {
          flattened[key] = value.join(',');
        } else if (typeof value === 'object') {
          flattened[key] = JSON.stringify(value);
        } else {
          flattened[key] = String(value);
        }
      }
    }
    
    return flattened;
  }

  private generateRequestId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private enhanceError(error: any, method: string, url: string, requestId: string): EnhancedStoreError {
    if (error instanceof ApiResponseError) {
      return createEnhancedError(error, `${method} ${url}`, undefined, {
        requestId,
        statusCode: error.status,
        apiError: error.data,
      });
    }

    return createEnhancedError(error, `${method} ${url}`, undefined, {
      requestId,
    });
  }

  private logRequest(
    requestId: string,
    method: string,
    url: string,
    duration: number,
    status: number,
    error?: any
  ): void {
    if (!this.config.enableLogging) return;

    const logData = {
      requestId,
      method,
      url,
      duration: `${duration}ms`,
      status,
    };

    if (error) {
      console.error('API Request Failed:', logData, error);
    } else {
      console.log('API Request:', logData);
    }
  }
}

// ========== ERROR CLASSES ==========

export class ApiResponseError extends Error {
  constructor(
    public data: ApiError,
    public status: number,
    public statusText: string
  ) {
    super(data.error?.message || statusText || 'API Error');
    this.name = 'ApiResponseError';
  }
}

// ========== INTERCEPTOR TYPES ==========

export interface RequestInterceptor {
  (config: {
    method: string;
    url: string;
    data?: any;
    headers: Record<string, string>;
  }): Promise<{ data?: any; headers?: Record<string, string> } | null>;
}

export interface ResponseInterceptor {
  (response: ApiResponse<any>): Promise<ApiResponse<any> | null>;
}

// ========== TOKEN MANAGER INTERFACE ==========

export interface TokenManager {
  getToken(): Promise<string | null>;
  refreshToken(): Promise<string | null>;
  clearToken(): Promise<void>;
  onTokenRefresh(callback: (token: string) => void): void;
  onTokenExpired(callback: () => void): void;
}

// ========== SINGLETON INSTANCE ==========

export const apiClient = new ApiClient();

// Add default interceptors for common functionality
apiClient.addResponseInterceptor(async (response) => {
  // Auto-refresh token on 401 responses
  if (response.status === 401) {
    const event = new CustomEvent('auth-token-expired');
    window.dispatchEvent(event);
  }
  return response;
});

export default apiClient;