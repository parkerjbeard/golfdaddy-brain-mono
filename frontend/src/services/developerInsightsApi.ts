import { z } from \'zod\';

// Define Zod schemas for robust validation (matching backend Pydantic models)
const CommitSummarySchema = z.object({
  commit_hash: z.string(),
  commit_message: z.string().nullable().optional(),
  ai_estimated_hours: z.number().nullable().optional(), // Backend sends Decimal, frontend receives as number
  seniority_score: z.number().int().nullable().optional(),
  commit_timestamp: z.string().datetime(), // Keep as string for simplicity, format if needed
});

const DeveloperDailySummarySchema = z.object({
  user_id: z.string().uuid(),
  report_date: z.string(), // Keep as string YYYY-MM-DD
  total_estimated_hours: z.number(),
  commit_estimated_hours: z.number(),
  eod_estimated_hours: z.number(),
  average_seniority_score: z.number().nullable().optional(),
  commit_count: z.number().int(),
  individual_commits: z.array(CommitSummarySchema),
  eod_summary: z.string().nullable().optional(),
  low_seniority_flag: z.boolean(),
});

// Define TypeScript types inferred from Zod schemas
export type CommitSummary = z.infer<typeof CommitSummarySchema>;
export type DeveloperDailySummary = z.infer<typeof DeveloperDailySummarySchema>;

// --- API Fetch Function ---

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || \'/api/v1\'; // Get base URL from env or default

/**
 * Fetches the developer daily summary from the backend.
 * @param userId - The UUID of the user.
 * @param reportDate - The date in \\"YYYY-MM-DD\\" format.
 * @param token - Optional JWT token for authorization.
 * @returns A promise that resolves to the DeveloperDailySummary.
 * @throws Throws an error if the fetch or parsing fails.
 */
export const getDeveloperDailySummary = async (
  userId: string,
  reportDate: string, // Expects "YYYY-MM-DD"
  token?: string 
): Promise<DeveloperDailySummary> => {
  const url = `${API_BASE_URL}/insights/developer/${userId}/daily_summary/${reportDate}`;
  
  const headers: HeadersInit = {
    \'Content-Type\': \'application/json\',
  };
  if (token) {
    headers[\'Authorization\'] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(url, {
      method: \'GET\',
      headers: headers,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: \'Unknown error\' }));
      console.error(\'API Error Response:\', errorData);
      throw new Error(`API Error (${response.status}): ${errorData.detail || response.statusText}`);
    }

    const data = await response.json();
    
    // Validate the response data with Zod
    const validationResult = DeveloperDailySummarySchema.safeParse(data);
    
    if (!validationResult.success) {
        console.error(\'API Response Validation Error:\', validationResult.error.errors);
        throw new Error(`API response validation failed: ${validationResult.error.message}`);
    }
    
    return validationResult.data;

  } catch (error) {
    console.error(\'Error fetching developer daily summary:\', error);
    // Rethrow the error so the calling component can handle it
    if (error instanceof Error) {
        throw error; 
    } else {
        throw new Error(\'An unexpected error occurred during fetch.\');
    }
  }
};

// Placeholder function to get users - replace with actual API call
// In a real app, this would likely fetch from a /users endpoint
export const getUsers = async (token?: string): Promise<{ id: string; name: string }[]> => {
  const url = `${API_BASE_URL}/users`;

  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, { headers });
  if (!response.ok) {
    throw new Error(`Failed to fetch users (${response.status})`);
  }

  const data = await response.json();
  if (!Array.isArray(data)) {
    throw new Error('Unexpected response format when fetching users');
  }

  return data.map((u: any) => ({ id: u.id, name: u.name ?? u.email ?? u.id }));
};
