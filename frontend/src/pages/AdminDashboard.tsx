import { useState, useEffect } from 'react';
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BarChart, ClipboardList, Target, TrendingUp, TrendingDown, Calendar, UserCog } from "lucide-react";
import { EmployeeManagement } from '@/components/admin/EmployeeManagement';
import { RaciTaskDashboard } from '@/components/admin/RaciTaskDashboard';
import { UserMappingManager } from '@/components/admin/UserMappingManager';
import { KpiCard } from '@/components/ui/KpiCard';
import { Chart } from '@/components/ui/chart';
import { UserRole } from '@/types/user';
import { useDashboardSelectors } from '@/store';

interface Employee {
  id: string;
  name: string;
  email: string;
  role: string;
  department?: string;
  status: 'active' | 'pending';
}

interface Objective {
  id: string;
  name: string;
  progress: number;
  deadline: string;
  owner: string;
}

interface BusinessGoal {
  id: string;
  name: string;
  tags: string[];
}

const AdminDashboard = () => {
  const { user, session } = useAuth();
  const userRole = session?.user?.user_metadata?.role || session?.user?.app_metadata?.role;
  const navigate = useNavigate();
  
  console.log('AdminDashboard - user role check:', {
    userRole,
    user_metadata: session?.user?.user_metadata,
    app_metadata: session?.user?.app_metadata,
    email: session?.user?.email
  });
  
  // Get real data from normalized stores
  const {
    dashboardMetrics,
    taskStats,
    userStats,
    overdueTasks,
    tasksDueToday,
    teamPerformanceMetrics,
    userWorkloadAnalysis,
  } = useDashboardSelectors();

  // Sample objectives data
  const [objectives, setObjectives] = useState<Objective[]>([
    {
      id: "1",
      name: "Increase market share by 10%",
      progress: 65,
      deadline: "2025-06-30",
      owner: "Alex Johnson"
    },
    {
      id: "2",
      name: "Reduce customer churn",
      progress: 40,
      deadline: "2025-07-15",
      owner: "Emily Chen"
    },
    {
      id: "3",
      name: "Launch European market expansion",
      progress: 25,
      deadline: "2025-09-01",
      owner: "Michael Davis"
    }
  ]);
  
  // Sample short-term and long-term goals
  const [shortTermGoals, setShortTermGoals] = useState<BusinessGoal[]>([
    { id: "1", name: "Complete Q2 financial review", tags: ["Finance", "Priority"] },
    { id: "2", name: "Implement new CRM system", tags: ["Technology", "Operations"] },
    { id: "3", name: "Hire 3 senior engineers", tags: ["Recruitment", "Engineering"] }
  ]);
  
  const [longTermGoals, setLongTermGoals] = useState<BusinessGoal[]>([
    { id: "1", name: "Expand to Asian markets", tags: ["Strategy", "Growth"] },
    { id: "2", name: "Build secondary HQ", tags: ["Infrastructure", "Investment"] },
    { id: "3", name: "Achieve carbon neutral status", tags: ["Sustainability", "Corporate"] }
  ]);
  
  // Sample mission statement points
  const missionPoints = [
    "Deliver exceptional products that improve daily workflows",
    "Maintain industry-leading customer satisfaction",
    "Cultivate a culture of innovation and continuous improvement",
    "Act responsibly toward our environment and communities",
    "Drive sustainable growth through strategic partnerships"
  ];
  
  // Sample retention data
  const retentionData = [
    { day: "Day 0", retention: 100 },
    { day: "Day 1", retention: 86 },
    { day: "Day 2", retention: 72 },
    { day: "Day 3", retention: 65 },
    { day: "Day 4", retention: 60 },
    { day: "Day 5", retention: 58 },
    { day: "Day 6", retention: 55 }
  ];
  
  // Sample first month usage data
  const firstMonthData = [
    { week: "Week 0", usage: 32 },
    { week: "Week 1", usage: 45 },
    { week: "Week 2", usage: 58 }
  ];

  // Check if user has leadership role
  // TODO: Re-enable role check once roles are properly set in Supabase
  if (false && userRole !== 'admin' && userRole !== UserRole.ADMIN) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8">
        <h1 className="text-2xl font-semibold mb-4">Access Denied</h1>
        <p className="text-muted-foreground mb-6">You don't have permission to access the admin dashboard.</p>
        <Button onClick={() => navigate('/')}>Go to Home</Button>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
          <BarChart className="h-6 w-6 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold">Executive Dashboard</h1>
          <p className="text-muted-foreground">Key metrics, objectives, and business insights</p>
        </div>
      </div>
      
      <Tabs defaultValue="metrics" className="w-full">
        <TabsList className="mb-6">
          <TabsTrigger value="metrics" className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            Key Metrics
          </TabsTrigger>
          <TabsTrigger value="objectives" className="flex items-center gap-2">
            <Target className="h-4 w-4" />
            Objectives
          </TabsTrigger>
          <TabsTrigger value="business" className="flex items-center gap-2">
            <ClipboardList className="h-4 w-4" />
            Business Insights
          </TabsTrigger>
          <TabsTrigger value="admin" className="flex items-center gap-2">
            <UserCog className="h-4 w-4" />
            Admin
          </TabsTrigger>
        </TabsList>
        
        {/* Metrics Tab */}
        <TabsContent value="metrics">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
            <KpiCard 
              title="Total Tasks" 
              value={dashboardMetrics.totalTasks.toString()} 
              trend={dashboardMetrics.trends.tasksCreatedThisWeek > 0 ? "up" : "neutral"}
              description="Active tasks across all projects" 
            />
            <KpiCard 
              title="Completion Rate" 
              value={`${dashboardMetrics.completionRate}%`} 
              trend={dashboardMetrics.completionRate > 75 ? "up" : dashboardMetrics.completionRate > 50 ? "neutral" : "down"}
              description="Tasks completed vs. total tasks" 
            />
            <KpiCard 
              title="Total Users" 
              value={dashboardMetrics.totalUsers.toString()} 
              trend="up"
              description="Active users in the system" 
            />
            <KpiCard 
              title="Overdue Tasks" 
              value={dashboardMetrics.overdueCount.toString()} 
              trend={dashboardMetrics.overdueCount > 0 ? "down" : "up"}
              description="Tasks past their due date" 
            />
            <KpiCard 
              title="Tasks Due Today" 
              value={tasksDueToday.length.toString()} 
              trend="neutral"
              description="Tasks requiring attention today" 
            />
            <KpiCard 
              title="Team Performance" 
              value={`${Math.round(teamPerformanceMetrics.reduce((acc, team) => acc + team.performanceScore, 0) / Math.max(teamPerformanceMetrics.length, 1))}%`}
              trend="up"
              description="Average team performance score" 
            />
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="p-4">
              <h3 className="text-lg font-medium mb-4">Task Status Distribution</h3>
              <Chart 
                type="bar"
                data={Object.entries(taskStats.byStatus).map(([status, count]) => ({
                  status: status.replace('_', ' '),
                  count
                }))}
                xKey="status"
                yKeys={[{ key: "count", name: "Tasks", color: "#8B5CF6" }]}
                height={250}
              />
            </Card>
            
            <Card className="p-4">
              <h3 className="text-lg font-medium mb-4">Team Performance Metrics</h3>
              <Chart 
                type="bar"
                data={teamPerformanceMetrics.map(team => ({
                  team: team.teamId || 'No Team',
                  performance: team.performanceScore
                }))}
                xKey="team"
                yKeys={[{ key: "performance", name: "Performance %", color: "#F97316" }]}
                height={250}
              />
            </Card>
          </div>
        </TabsContent>
        
        {/* Objectives Tab */}
        <TabsContent value="objectives">
          <Card className="p-6">
            <h2 className="text-xl font-medium mb-4">Company Objectives</h2>
            <div className="space-y-6">
              {objectives.map((objective) => (
                <div key={objective.id} className="border-b pb-4 last:border-none last:pb-0">
                  <div className="flex justify-between items-start mb-2">
                    <h3 className="text-lg font-medium">{objective.name}</h3>
                    <span className="text-sm text-muted-foreground flex items-center gap-1">
                      <Calendar className="h-4 w-4" />
                      {new Date(objective.deadline).toLocaleDateString('en-US', { 
                        year: 'numeric', 
                        month: 'short', 
                        day: 'numeric' 
                      })}
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-2 mb-4">
                    <UserCog className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">Owner: {objective.owner}</span>
                  </div>
                  
                  <div className="w-full bg-gray-100 rounded-full h-2.5 mb-1">
                    <div 
                      className="bg-primary h-2.5 rounded-full" 
                      style={{ width: `${objective.progress}%` }}
                    ></div>
                  </div>
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>Progress</span>
                    <span>{objective.progress}%</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </TabsContent>
        
        {/* Business Insights Tab */}
        <TabsContent value="business">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="p-6">
              <h2 className="text-xl font-medium mb-4">Business Unlocks</h2>
              
              <div className="mb-6">
                <h3 className="text-md font-medium mb-2">Short-term Goals</h3>
                <div className="space-y-3">
                  {shortTermGoals.map((goal) => (
                    <div key={goal.id} className="border-b pb-2 last:border-none last:pb-0">
                      <div className="flex justify-between">
                        <span>{goal.name}</span>
                      </div>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {goal.tags.map((tag, idx) => (
                          <span 
                            key={idx} 
                            className="px-2 py-0.5 rounded-full text-xs bg-primary/10 text-primary"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              
              <div>
                <h3 className="text-md font-medium mb-2">Long-term Goals</h3>
                <div className="space-y-3">
                  {longTermGoals.map((goal) => (
                    <div key={goal.id} className="border-b pb-2 last:border-none last:pb-0">
                      <div className="flex justify-between">
                        <span>{goal.name}</span>
                      </div>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {goal.tags.map((tag, idx) => (
                          <span 
                            key={idx} 
                            className="px-2 py-0.5 rounded-full text-xs bg-primary/10 text-primary"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
            
            <div className="space-y-6">
              <Card className="p-6">
                <h2 className="text-xl font-medium mb-4">Mission Statement</h2>
                <ul className="list-disc pl-5 space-y-2">
                  {missionPoints.map((point, idx) => (
                    <li key={idx}>{point}</li>
                  ))}
                </ul>
              </Card>
              
            </div>
          </div>
        </TabsContent>
        
        {/* Admin Tab */}
        <TabsContent value="admin">
          <div className="grid grid-cols-1 gap-6">
            <UserMappingManager />
            
            <Card className="p-6">
              <h2 className="text-xl font-medium mb-4">Employee Management</h2>
              <p className="text-muted-foreground mb-6">
                Manage employees, approve new users, assign roles and departments.
              </p>
              <EmployeeManagement />
            </Card>
            
            <Card className="p-6">
              <h2 className="text-xl font-medium mb-4">Task Overview</h2>
              <p className="text-muted-foreground mb-6">
                Overview of tasks across all employees and departments.
              </p>
              <RaciTaskDashboard />
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AdminDashboard;
