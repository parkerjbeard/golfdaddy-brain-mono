// frontend/src/types/user.ts

// Matches backend UserRole enum
export enum UserRole {
  USER = "USER",
  VIEWER = "VIEWER",
  DEVELOPER = "DEVELOPER",
  LEAD = "LEAD",
  MANAGER = "MANAGER",
  ADMIN = "ADMIN",
  SERVICE_ACCOUNT = "SERVICE_ACCOUNT",
}

// Matches backend UserResponse Pydantic model
export interface UserResponse {
  id: string; // UUID
  name?: string | null;
  email?: string | null;
  slack_id?: string | null;
  github_username?: string | null;
  role: UserRole;
  team?: string | null;
  avatar_url?: string | null; // HttpUrl
  created_at?: string | null; // datetime
  updated_at?: string | null; // datetime
}

// Matches backend UserListResponse Pydantic model
export interface UserListResponse {
  users: UserResponse[];
  total: number;
  page: number;
  size: number;
}

// Matches backend UserUpdateByAdminPayload Pydantic model
export interface UserUpdateByAdminPayload {
  name?: string | null;
  email?: string | null; // Note: Backend mentions auth email is separate. This updates display email.
  slack_id?: string | null;
  github_username?: string | null;
  role?: UserRole | null;
  team?: string | null;
  avatar_url?: string | null;
} 