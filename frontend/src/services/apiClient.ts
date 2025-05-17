import { toast } from "@/components/ui/use-toast";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

interface ApiClientOptions extends RequestInit {
  // You can add custom options here if needed
}

async function request<T>(endpoint: string, options: ApiClientOptions = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const { headers: customHeaders, ...restOptions } = options;

  const defaultHeaders: HeadersInit = {
    'Content-Type': 'application/json',
    // Add other default headers like Authorization if needed
    // Example: 'Authorization': `Bearer ${localStorage.getItem('token')}`,
  };

  const headers = {
    ...defaultHeaders,
    ...customHeaders,
  };

  try {
    const response = await fetch(url, {
      ...restOptions,
      headers,
    });

    if (!response.ok) {
      let errorData;
      try {
        errorData = await response.json();
      } catch (e) {
        // If response is not JSON, use text as a fallback
        errorData = { message: await response.text() };
      }
      
      const errorMessage = errorData?.detail || errorData?.message || `HTTP error! status: ${response.status}`;
      console.error("API Error:", errorMessage, "URL:", url, "Options:", options, "Response Status:", response.status);
      
      toast({
        variant: "destructive",
        title: "API Request Failed",
        description: typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage),
      });
      
      throw new Error(typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage));
    }

    // Handle cases where response might be empty (e.g., 204 No Content)
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.indexOf("application/json") !== -1) {
      return await response.json() as T;
    } else {
      // For non-JSON responses, you might return text or handle differently
      // If a 204 or similar, response.text() might be empty. Ensure T can handle this.
      return await response.text() as unknown as T; // Or handle appropriately
    }

  } catch (error) {
    console.error('Network or other error in apiClient:', error);
    // Re-throw the error so that calling code can handle it, or handle it here
    // If already an Error object from response.ok check, it will be re-thrown.
    // If it's a network error, it will be thrown here.
    if (!(error instanceof Error)) { // Ensure it's an error object
        throw new Error(String(error));
    }
    throw error;
  }
}

export const apiClient = {
  get: <T>(endpoint: string, options?: ApiClientOptions) => 
    request<T>(endpoint, { ...options, method: 'GET' }),
  
  post: <T>(endpoint: string, body: any, options?: ApiClientOptions) => 
    request<T>(endpoint, { ...options, method: 'POST', body: JSON.stringify(body) }),
  
  put: <T>(endpoint: string, body: any, options?: ApiClientOptions) => 
    request<T>(endpoint, { ...options, method: 'PUT', body: JSON.stringify(body) }),
  
  delete: <T>(endpoint: string, options?: ApiClientOptions) => 
    request<T>(endpoint, { ...options, method: 'DELETE' }),
  
  patch: <T>(endpoint: string, body: any, options?: ApiClientOptions) => 
    request<T>(endpoint, { ...options, method: 'PATCH', body: JSON.stringify(body) }),
}; 