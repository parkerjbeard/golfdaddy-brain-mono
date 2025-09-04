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
  team_id?: string | null; // UUID, Foreign key to Team model
  reports_to_id?: string | null; // UUID, ID of the user this user reports to
  avatar_url?: string | null; // HttpUrl
  metadata?: Record<string, any> | null; // Arbitrary user metadata
  created_at?: string | null; // datetime
  updated_at?: string | null; // datetime
  last_login_at?: string | null; // datetime
  is_active?: boolean;
  preferences?: Record<string, any> | null; // User-specific settings
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
  team_id?: string | null; // Added
  avatar_url?: string | null;
  reports_to_id?: string | null; // Added
  metadata?: Record<string, any> | null; // Added
  is_active?: boolean | null; // Added
  preferences?: Record<string, any> | null; // Added
}
