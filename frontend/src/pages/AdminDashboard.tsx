import { useAuth } from "@/contexts/AuthContext";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BarChart, UserCog, Grid } from "lucide-react";
import { EmployeeManagement } from '@/components/admin/EmployeeManagement';
import { RaciTaskDashboard } from '@/components/admin/RaciTaskDashboard';


const AdminDashboard = () => {
  const { session } = useAuth();


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
      
      <Tabs defaultValue="employees" className="w-full">
        <TabsList className="mb-6">
          <TabsTrigger value="employees" className="flex items-center gap-2">
            <UserCog className="h-4 w-4" />
            Employee Management
          </TabsTrigger>
          <TabsTrigger value="raci" className="flex items-center gap-2">
            <Grid className="h-4 w-4" />
            RACI Matrix
          </TabsTrigger>
        </TabsList>
        
        {/* Employee Management Tab */}
        <TabsContent value="employees">
          <EmployeeManagement />
        </TabsContent>
        
        {/* RACI Matrix Tab */}
        <TabsContent value="raci">
          <RaciTaskDashboard />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AdminDashboard;
