import { User, CreateTaskPayload, CreateTaskResponse } from '@/types/entities';

const API_BASE_URL = '/api/v1'; // Adjust if your API base URL is different

// Helper function to handle API responses
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
    throw new Error(errorData.message || `API request failed with status ${response.status}`);
  }
  return response.json();
}

/**
 * Fetches a list of users from the backend.
 */
export async function fetchUsers(): Promise<User[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/users`);
    return await handleResponse<User[]>(response);
  } catch (error) {
    console.error('Failed to fetch users:', error);
    // In a real app, you might want to throw a custom error or handle it differently
    // For now, returning an empty array or re-throwing
    throw error;
  }
}

/**
 * Creates a new task with RACI assignments.
 * The backend endpoint is assumed to be POST /api/v1/raci/register based on raci_service.py
 * This might need adjustment based on the actual backend API route.
 * @param payload - The task creation data.
 * @returns The created task and any warnings from the backend.
 */
export async function createRaciTask(payload: CreateTaskPayload): Promise<CreateTaskResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/tasks`, { // Corrected endpoint to /tasks
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // Add Authorization header if required, e.g.:
        // 'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
      },
      body: JSON.stringify(payload),
    });
    return await handleResponse<CreateTaskResponse>(response);
  } catch (error) {
    console.error('Failed to create RACI task:', error);
    throw error; // Re-throw to be handled by the caller (e.g., in the UI)
  }
}

// Placeholder for other potential task-related API calls:

// export async function fetchTaskById(taskId: string): Promise<Task> { ... }
// export async function updateTask(taskId: string, payload: Partial<Task>): Promise<Task> { ... }
// export async function deleteTask(taskId: string): Promise<void> { ... } 