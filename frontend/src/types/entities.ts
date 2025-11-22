export interface User {
  id: string; // UUID
  name: string;
  email?: string;
  slack_id?: string;
  github_username?: string;
  avatar_url?: string;
  role?: string;
}



// RACI Matrix Types
export enum RaciRoleType {
  RESPONSIBLE = "R",
  ACCOUNTABLE = "A",
  CONSULTED = "C",
  INFORMED = "I",
}

export enum RaciMatrixType {
  INVENTORY_INBOUND = "inventory_inbound",
  SHIPBOB_ISSUES = "shipbob_issues",
  DATA_COLLECTION = "data_collection",
  RETAIL_LOGISTICS = "retail_logistics",
  CUSTOM = "custom",
}

export interface RaciAssignment {
  activity_id: string;
  role_id: string;
  role: RaciRoleType;
  notes?: string;
}

export interface RaciActivity {
  id: string;
  name: string;
  description?: string;
  order: number;
}

export interface RaciRole {
  id: string;
  name: string;
  title?: string;
  user_id?: string;
  is_person: boolean;
  order: number;
}

export interface RaciMatrix {
  id: string;
  name: string;
  description?: string;
  matrix_type: RaciMatrixType;
  activities: RaciActivity[];
  roles: RaciRole[];
  assignments: RaciAssignment[];
  metadata?: Record<string, any>;
  is_active: boolean;
  created_by?: string;
  created_at?: string;
  updated_at?: string;
}

export interface RaciValidationStats {
  total_activities: number;
  total_roles: number;
  total_assignments: number;
  assignments_by_type: Record<string, number>;
}

export interface RaciValidationResult {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  stats?: RaciValidationStats;
}

export interface RaciMatrixTemplate {
  template_id: string;
  name: string;
  description: string;
  matrix_type: RaciMatrixType;
  activities: RaciActivity[];
  roles: RaciRole[];
  assignments: RaciAssignment[];
}

export interface CreateRaciMatrixPayload {
  name: string;
  description?: string;
  matrix_type: RaciMatrixType;
  activities: RaciActivity[];
  roles: RaciRole[];
  assignments: RaciAssignment[];
  metadata?: Record<string, any>;
}

export interface UpdateRaciMatrixPayload {
  name?: string;
  description?: string;
  activities?: RaciActivity[];
  roles?: RaciRole[];
  assignments?: RaciAssignment[];
  metadata?: Record<string, any>;
  is_active?: boolean;
}

export interface CreateRaciMatrixResponse {
  matrix: RaciMatrix;
  warnings: string[];
} 
