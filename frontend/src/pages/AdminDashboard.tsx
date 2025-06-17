import { Card } from "@/components/ui/card";
import { useAuth } from "@/contexts/AuthContext";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BarChart, Users, UserCog, Grid } from "lucide-react";
import { EmployeeManagement } from '@/components/admin/EmployeeManagement';
import { RaciTaskDashboard } from '@/components/admin/RaciTaskDashboard';
import { KpiCard } from '@/components/ui/KpiCard';
import { Chart } from '@/components/ui/chart';
import { useDashboardSelectors } from '@/store';


const AdminDashboard = () => {
  const { session } = useAuth();
  
  // Get real data from normalized stores
  const {
    dashboardMetrics,
    userStats,
    roleDistribution,
    teamMetrics,
  } = useDashboardSelectors();


  // Check if user has leadership role
  // TODO: Re-enable role check once roles are properly set in Supabase
  // if (userRole !== 'admin' && userRole !== UserRole.ADMIN) {
  //   return (
  //     <div className="flex flex-col items-center justify-center h-full p-8">
  //       <h1 className="text-2xl font-semibold mb-4">Access Denied</h1>
  //       <p className="text-muted-foreground mb-6">You don't have permission to access the admin dashboard.</p>
  //       <Button onClick={() => navigate('/')}>Go to Home</Button>
  //     </div>
  //   );
  // }

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
          <BarChart className="h-6 w-6 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold">Admin Dashboard</h1>
          <p className="text-muted-foreground">Manage employees and view key metrics</p>
        </div>
      </div>
      
      <Tabs defaultValue="metrics" className="w-full">
        <TabsList className="mb-6">
          <TabsTrigger value="metrics" className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            User Metrics
          </TabsTrigger>
          <TabsTrigger value="raci" className="flex items-center gap-2">
            <Grid className="h-4 w-4" />
            RACI Matrix
          </TabsTrigger>
          <TabsTrigger value="employees" className="flex items-center gap-2">
            <UserCog className="h-4 w-4" />
            Employee Management
          </TabsTrigger>
        </TabsList>
        
        {/* Metrics Tab */}
        <TabsContent value="metrics">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
            <KpiCard 
              title="Total Users" 
              value={dashboardMetrics.totalUsers.toString()} 
              trend="up"
              description="Active users in the system" 
            />
            <KpiCard 
              title="New Users This Month" 
              value={dashboardMetrics.trends.newUsersThisMonth.toString()} 
              trend="up"
              description="Recently registered users" 
            />
            <KpiCard 
              title="Active Teams" 
              value={teamMetrics.length.toString()} 
              trend="neutral"
              description="Teams with members assigned" 
            />
            <KpiCard 
              title="Average Team Size" 
              value={teamMetrics.length > 0 ? Math.round(teamMetrics.reduce((acc, team) => acc + team.memberCount, 0) / teamMetrics.length).toString() : "0"} 
              trend="neutral"
              description="Average members per team" 
            />
            <KpiCard 
              title="Role Types" 
              value={roleDistribution.length.toString()} 
              trend="neutral"
              description="Different roles in system" 
            />
            <KpiCard 
              title="System Health" 
              value="Good" 
              trend="up"
              description="Overall system status" 
            />
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="p-4">
              <h3 className="text-lg font-medium mb-4">Role Distribution</h3>
              <Chart 
                type="bar"
                data={roleDistribution.map(item => ({
                  role: item.role.replace('_', ' '),
                  count: item.count
                }))}
                xKey="role"
                yKeys={[{ key: "count", name: "Users", color: "#8B5CF6" }]}
                height={250}
              />
            </Card>
            
            <Card className="p-4">
              <h3 className="text-lg font-medium mb-4">Team Size Distribution</h3>
              <Chart 
                type="bar"
                data={teamMetrics.map(team => ({
                  team: team.teamId || 'No Team',
                  size: team.memberCount
                }))}
                xKey="team"
                yKeys={[{ key: "size", name: "Members", color: "#F97316" }]}
                height={250}
              />
            </Card>
          </div>
        </TabsContent>
        
        
        {/* RACI Matrix Tab */}
        <TabsContent value="raci">
          <RaciTaskDashboard />
        </TabsContent>
        
        {/* Employee Management Tab */}
        <TabsContent value="employees">
          <EmployeeManagement />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AdminDashboard;
