
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/use-toast";
import { useAuth } from "@/contexts/AuthContext";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TaskAssignment } from '@/components/admin/TaskAssignment';
import { WorkSummaries } from '@/components/admin/WorkSummaries';
import { employees, tasks as allTasks, dailyLogs } from '@/data/mockData';
import { ArrowLeft } from 'lucide-react';

const EmployeeDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [employee, setEmployee] = useState<any | null>(null);
  const [employeeTasks, setEmployeeTasks] = useState<any[]>([]);
  const [employeeLogs, setEmployeeLogs] = useState<any[]>([]);

  // Check if user has leadership role
  if (user?.role !== 'leadership') {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8">
        <h1 className="text-2xl font-semibold mb-4">Access Denied</h1>
        <p className="text-muted-foreground mb-6">You don't have permission to access this page.</p>
        <Button onClick={() => navigate('/my-dashboard')}>Go to My Dashboard</Button>
      </div>
    );
  }

  useEffect(() => {
    // In a real app, this would be an API call
    const foundEmployee = employees.find(emp => emp.id === id);
    if (foundEmployee) {
      setEmployee(foundEmployee);
      
      // Get tasks assigned to this employee
      const employeeTaskList = allTasks.filter(task => task.assignee === foundEmployee.name);
      setEmployeeTasks(employeeTaskList);
      
      // Get work logs for this employee
      // In a real app, this would come from the database
      setEmployeeLogs(dailyLogs);
    }
  }, [id]);

  if (!employee) {
    return <div className="p-8">Loading employee details...</div>;
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-6">
        <Button variant="ghost" size="sm" onClick={() => navigate('/admin')}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Admin
        </Button>
      </div>

      <div className="flex items-center gap-4 mb-6">
        <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center text-2xl font-semibold">
          {employee.avatar ? (
            <img src={employee.avatar} alt={employee.name} className="h-16 w-16 rounded-full object-cover" />
          ) : (
            employee.name.charAt(0)
          )}
        </div>
        <div>
          <h1 className="text-2xl font-semibold">{employee.name}</h1>
          <p className="text-muted-foreground">
            {employee.role.charAt(0).toUpperCase() + employee.role.slice(1)}
            {employee.department && ` • ${employee.department}`}
          </p>
        </div>
      </div>

      <Tabs defaultValue="tasks" className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="tasks">Manage Tasks</TabsTrigger>
          <TabsTrigger value="summaries">Work Summaries</TabsTrigger>
        </TabsList>
        
        <TabsContent value="tasks">
          <TaskAssignment employee={employee} tasks={employeeTasks} setTasks={setEmployeeTasks} />
        </TabsContent>
        
        <TabsContent value="summaries">
          <WorkSummaries logs={employeeLogs} />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default EmployeeDetail;
