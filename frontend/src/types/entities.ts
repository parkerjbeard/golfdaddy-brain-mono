export interface User {
  id: string; // UUID
  name: string;
  email?: string;
  slack_id?: string;
  github_username?: string;
  avatar_url?: string;
  role?: string;
}

export enum TaskStatus {
  OPEN = "OPEN",
  ASSIGNED = "ASSIGNED",
  IN_PROGRESS = "IN_PROGRESS",
  BLOCKED = "BLOCKED",
  UNDER_REVIEW = "UNDER_REVIEW",
  DONE = "DONE",
  ARCHIVED = "ARCHIVED",
}

export interface Task {
  id: string; // UUID
  title: string;
  description: string;
  status: TaskStatus;
  assignee_id: string; // UUID
  responsible_id: string; // UUID
  accountable_id: string; // UUID
  consulted_ids?: string[]; // Array of UUIDs
  informed_ids?: string[]; // Array of UUIDs
  creator_id: string; // UUID
  due_date?: string | null; // ISO date string
  created_at: string; // ISO date string
  updated_at: string; // ISO date string
  task_type?: string | null;
  metadata?: Record<string, any>;
  priority?: string | null; // Assuming 'URGENT', 'HIGH', 'MEDIUM', 'LOW'
  estimated_hours?: number | null;
  actual_hours?: number | null;
  tags?: string[];
  blocked?: boolean;
  blocked_reason?: string | null;
  doc_references?: string[]; // Array of Doc UUIDs

  // Optional hydrated fields for display
  assignee?: User;
  responsible?: User;
  accountable?: User;
  consulted?: User[];
  informed?: User[];
  creator?: User;
}

export interface CreateTaskPayload {
  title: string;
  description: string;
  assignee_id: string; // UUID
  responsible_id?: string | null; // UUID
  accountable_id?: string | null; // UUID
  consulted_ids?: string[]; // Array of UUIDs
  informed_ids?: string[]; // Array of UUIDs
  creator_id: string; // UUID - This might be set by the backend based on authenticated user
  due_date?: string | null; // ISO date string
  task_type?: string | null;
  metadata?: Record<string, any>;
  priority?: string | null;
}

// Response from the backend when a task is created, including warnings
export interface CreateTaskResponse {
  task: Task;
  warnings: string[];
} 