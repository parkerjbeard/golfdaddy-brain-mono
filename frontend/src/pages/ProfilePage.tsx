
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/contexts/AuthContext";
import { ArrowLeft, Mail, Building, User as UserIcon, Calendar, Briefcase, Award } from 'lucide-react';
import { employees, tasks, dailyLogs } from '@/data/mockData';

const ProfilePage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user: currentUser } = useAuth();
  const [employee, setEmployee] = useState<any | null>(null);
  const [employeeTasks, setEmployeeTasks] = useState<any[]>([]);
  const [employeeLogs, setEmployeeLogs] = useState<any[]>([]);
  
  useEffect(() => {
    // If no ID is provided, show the current user's profile
    const targetId = id || currentUser?.id;
    if (!targetId) return;
    
    // In a real app, this would be an API call
    const foundEmployee = employees.find(emp => emp.id === targetId);
    if (foundEmployee) {
      setEmployee(foundEmployee);
      
      // Get tasks assigned to this employee
      const employeeTaskList = tasks.filter(task => task.assignee === foundEmployee.name);
      setEmployeeTasks(employeeTaskList);
      
      // Get work logs for this employee
      // Fixed: using id instead of userId which doesn't exist
      setEmployeeLogs(dailyLogs.filter(log => log.id.toString() === targetId));
    }
  }, [id, currentUser]);

  if (!employee) {
    return <div className="p-8">Loading profile...</div>;
  }

  // Calculate performance metrics
  const completedTasks = employeeTasks.filter(task => task.status === 'done').length;
  const totalTasks = employeeTasks.length;
  const completionRate = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

  return (
    <div>
      {id && (
        <div className="flex items-center gap-2 mb-6">
          <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Profile Information */}
        <Card className="p-6 md:col-span-1">
          <div className="flex flex-col items-center text-center mb-6">
            <Avatar className="h-24 w-24 mb-4">
              {employee.avatar ? (
                <AvatarImage src={employee.avatar} alt={employee.name} />
              ) : (
                <AvatarFallback className="text-xl">
                  {employee.name.charAt(0)}
                </AvatarFallback>
              )}
            </Avatar>
            <h1 className="text-2xl font-semibold">{employee.name}</h1>
            <p className="text-muted-foreground">
              {employee.title || employee.role.charAt(0).toUpperCase() + employee.role.slice(1)}
            </p>
            <div className="flex items-center gap-2 mt-2">
              <Badge variant="outline" className="capitalize">
                {employee.role}
              </Badge>
              {employee.department && (
                <Badge variant="outline" className="bg-primary/10">
                  {employee.department}
                </Badge>
              )}
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <Mail className="h-5 w-5 text-muted-foreground" />
              <span>{employee.email}</span>
            </div>
            {employee.department && (
              <div className="flex items-center gap-3">
                <Building className="h-5 w-5 text-muted-foreground" />
                <span>{employee.department}</span>
              </div>
            )}
            {employee.joinDate && (
              <div className="flex items-center gap-3">
                <Calendar className="h-5 w-5 text-muted-foreground" />
                <span>Joined {new Date(employee.joinDate).toLocaleDateString()}</span>
              </div>
            )}
            {employee.manager && (
              <div className="flex items-center gap-3">
                <UserIcon className="h-5 w-5 text-muted-foreground" />
                <span>Reports to {employee.manager}</span>
              </div>
            )}
          </div>

          <div className="mt-6 pt-6 border-t">
            <h2 className="text-lg font-medium mb-4">Skills & Expertise</h2>
            <div className="flex flex-wrap gap-2">
              {(employee.skills || ['Communication', 'Teamwork', 'Problem Solving']).map((skill: string) => (
                <Badge key={skill} variant="secondary" className="px-3 py-1">
                  {skill}
                </Badge>
              ))}
            </div>
          </div>
        </Card>

        {/* Performance & Activity */}
        <Card className="p-6 md:col-span-2">
          <Tabs defaultValue="performance">
            <TabsList className="mb-4">
              <TabsTrigger value="performance">Performance</TabsTrigger>
              <TabsTrigger value="activity">Recent Activity</TabsTrigger>
              <TabsTrigger value="summaries">Work Summaries</TabsTrigger>
            </TabsList>

            <TabsContent value="performance">
              <div className="space-y-6">
                <div>
                  <h3 className="text-lg font-medium mb-2">Performance Overview</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <Card className="p-4 bg-muted/30">
                      <div className="text-sm text-muted-foreground">Tasks Completed</div>
                      <div className="text-2xl font-bold mt-1">{completedTasks}</div>
                    </Card>
                    <Card className="p-4 bg-muted/30">
                      <div className="text-sm text-muted-foreground">Completion Rate</div>
                      <div className="text-2xl font-bold mt-1">{completionRate}%</div>
                    </Card>
                    <Card className="p-4 bg-muted/30">
                      <div className="text-sm text-muted-foreground">Active Tasks</div>
                      <div className="text-2xl font-bold mt-1">{totalTasks - completedTasks}</div>
                    </Card>
                  </div>
                </div>

                <div>
                  <h3 className="text-lg font-medium mb-2">Recent Achievements</h3>
                  {(employee.achievements || []).length > 0 ? (
                    <div className="space-y-4">
                      {(employee.achievements || []).map((achievement: any, index: number) => (
                        <div key={index} className="flex items-start gap-3 p-3 border rounded-lg">
                          <Award className="h-5 w-5 text-primary" />
                          <div>
                            <div className="font-medium">{achievement.title}</div>
                            <div className="text-sm text-muted-foreground">{achievement.description}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center p-8 text-muted-foreground">
                      No achievements recorded yet.
                    </div>
                  )}
                </div>
              </div>
            </TabsContent>

            <TabsContent value="activity">
              <div className="space-y-6">
                <h3 className="text-lg font-medium mb-2">Current Tasks</h3>
                {employeeTasks.length > 0 ? (
                  <div className="border rounded-lg overflow-hidden">
                    <table className="w-full">
                      <thead className="bg-muted/50">
                        <tr>
                          <th className="px-4 py-2 text-left font-medium">Task</th>
                          <th className="px-4 py-2 text-left font-medium">Category</th>
                          <th className="px-4 py-2 text-left font-medium">Status</th>
                          <th className="px-4 py-2 text-left font-medium">Due Date</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {employeeTasks.map((task) => (
                          <tr key={task.id}>
                            <td className="px-4 py-3">{task.title}</td>
                            <td className="px-4 py-3">
                              <Badge variant="outline">{task.category}</Badge>
                            </td>
                            <td className="px-4 py-3">
                              <Badge 
                                variant={
                                  task.status === 'done' ? 'secondary' : 
                                  task.status === 'in-progress' ? 'default' : 
                                  'outline'
                                }
                              >
                                {task.status === 'in-progress' ? 'In Progress' : 
                                  task.status.charAt(0).toUpperCase() + task.status.slice(1)}
                              </Badge>
                            </td>
                            <td className="px-4 py-3 text-sm text-muted-foreground">
                              {task.dueDate ? new Date(task.dueDate).toLocaleDateString() : 'No date'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center p-8 text-muted-foreground">
                    No tasks assigned yet.
                  </div>
                )}
              </div>
            </TabsContent>

            <TabsContent value="summaries">
              <h3 className="text-lg font-medium mb-2">Work Summaries</h3>
              {employeeLogs.length > 0 ? (
                <div className="space-y-4">
                  {employeeLogs.map((log) => (
                    <div key={log.id} className="border rounded-lg p-4">
                      <div className="flex justify-between items-start mb-2">
                        <div className="font-medium">
                          {new Date(log.date).toLocaleDateString('en-US', {
                            weekday: 'long',
                            month: 'long',
                            day: 'numeric',
                            year: 'numeric'
                          })}
                        </div>
                        <Badge variant="outline" className="bg-blue-50 text-blue-800 border-blue-200">
                          Daily Log
                        </Badge>
                      </div>
                      <p className="text-sm whitespace-pre-line">{log.content}</p>
                      {log.aiSummary && (
                        <div className="bg-muted/30 p-3 mt-3 rounded-md border border-muted">
                          <div className="text-xs font-medium text-muted-foreground mb-1">AI Summary</div>
                          <p className="text-sm">{log.aiSummary}</p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center p-8 text-muted-foreground">
                  No work summaries available.
                </div>
              )}
            </TabsContent>
          </Tabs>
        </Card>
      </div>
    </div>
  );
};

export default ProfilePage;
