import { useState, useCallback } from 'react'
import { apiClient, ApiResponse } from '../services/api/client'

interface UseApiOptions {
  onSuccess?: (data: any) => void
  onError?: (error: string) => void
}

export function useApi<T = any>(options: UseApiOptions = {}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<T | null>(null)

  const execute = useCallback(
    async (
      method: 'get' | 'post' | 'put' | 'patch' | 'delete',
      endpoint: string,
      body?: any
    ): Promise<ApiResponse<T>> => {
      setLoading(true)
      setError(null)

      try {
        let response: ApiResponse<T>

        switch (method) {
          case 'get':
            response = await apiClient.get<T>(endpoint)
            break
          case 'post':
            response = await apiClient.post<T>(endpoint, body)
            break
          case 'put':
            response = await apiClient.put<T>(endpoint, body)
            break
          case 'patch':
            response = await apiClient.patch<T>(endpoint, body)
            break
          case 'delete':
            response = await apiClient.delete<T>(endpoint)
            break
          default:
            throw new Error(`Unsupported method: ${method}`)
        }

        if (response.error) {
          setError(response.error)
          options.onError?.(response.error)
        } else {
          setData(response.data || null)
          options.onSuccess?.(response.data)
        }

        return response
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'An error occurred'
        setError(errorMessage)
        options.onError?.(errorMessage)
        return { error: errorMessage, status: 0 }
      } finally {
        setLoading(false)
      }
    },
    [options]
  )

  const get = useCallback((endpoint: string) => execute('get', endpoint), [execute])
  const post = useCallback((endpoint: string, body?: any) => execute('post', endpoint, body), [execute])
  const put = useCallback((endpoint: string, body?: any) => execute('put', endpoint, body), [execute])
  const patch = useCallback((endpoint: string, body?: any) => execute('patch', endpoint, body), [execute])
  const del = useCallback((endpoint: string) => execute('delete', endpoint), [execute])

  return {
    loading,
    error,
    data,
    get,
    post,
    put,
    patch,
    delete: del,
  }
}