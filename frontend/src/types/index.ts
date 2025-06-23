export interface User {
  id: string;
  name: string;
  teamId?: string; // Optional: user might not be in a team
}

export interface Team {
  id: string;
  name: string;
  members: User[];
}

// Export dashboard types
export * from './dashboard'; 