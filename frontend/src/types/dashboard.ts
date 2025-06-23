export interface DashboardOwner {
  name: string;
  initials: string;
  email: string;
}

export interface ProjectKeyResult {
  name: string;
  completed: boolean;
}

export interface ProjectChecklist {
  total: number;
  completed: number;
  items: ProjectKeyResult[];
}

export interface DashboardProject {
  id: string;
  name: string;
  owner: DashboardOwner;
  team: string;
  progress: number;
  status: string;
  dueDate?: string;
  originalDueDate?: string;
  keyResults: string[];
  sparkline: string;
  checklist?: ProjectChecklist;
}

export interface DashboardKPIs {
  csat: {
    current: number;
    previous: number;
    trend: 'up' | 'down' | 'neutral';
    change: number;
  };
  socialMedia: {
    totalViews: number;
    platforms: Array<{
      id: string;
      views: number;
    }>;
  };
  retention: {
    week0: number;
    week1: number;
    week2: number;
    week1Target: number;
  };
}

export interface DashboardIssues {
  customerSupport: string[];
}

export interface DashboardInsights {
  weekly: string;
}

export interface TeamStats {
  [teamName: string]: {
    active: number;
    archived: number;
  };
}

export interface DashboardData {
  dashboard: {
    lastUpdated: string;
    kpis: DashboardKPIs;
    projects: {
      active: DashboardProject[];
      archived: DashboardProject[];
    };
    issues: DashboardIssues;
    insights: DashboardInsights;
    teamStats: TeamStats;
  };
} 