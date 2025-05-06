
import { useState } from 'react';
import { Card } from "@/components/ui/card";
import { KpiCard } from '@/components/ui/KpiCard';
import { TaskList } from '@/components/ui/TaskList';
import { toast } from "@/components/ui/use-toast";

const DepartmentDashboard = () => {
  const [tasks, setTasks] = useState([
    { 
      id: 1, 
      title: 'Review PRs', 
      description: 'Review open pull requests from the team',
      dueDate: '2023-12-17',
      status: 'open',
      category: 'review'
    },
    { 
      id: 2, 
      title: 'Update Documentation', 
      description: 'Update the API documentation with new endpoints',
      dueDate: '2023-12-10',
      status: 'done',
      category: 'planning'
    },
    { 
      id: 3, 
      title: 'Refactor Code', 
      description: 'Refactor the authentication module',
      dueDate: '2023-12-22',
      status: 'in-progress',
      category: 'bug'
    },
  ]);

  const handleStatusChange = (id: number, status: string) => {
    const updatedTasks = tasks.map(task => 
      task.id === id ? {...task, status} : task
    );
    setTasks(updatedTasks);
    const task = tasks.find(t => t.id === id);
    toast({
      title: "Task Status Updated",
      description: `"${task?.title}" status changed to ${status === 'in-progress' ? 'In Progress' : status.charAt(0).toUpperCase() + status.slice(1)}`
    });
  };

  const kpis = [
    { title: 'Team Morale', value: '8/10', description: 'Based on recent survey' },
    { title: 'Project Completion Rate', value: '95%', description: 'Last quarter' },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {/* KPIs */}
      {kpis.map((kpi, index) => (
        <KpiCard 
          key={index} 
          title={kpi.title} 
          value={kpi.value} 
          description={kpi.description} 
        />
      ))}

      {/* Task List */}
      <Card className="md:col-span-2 lg:col-span-4">
        <TaskList 
          tasks={tasks} 
          onStatusChange={handleStatusChange} 
        />
      </Card>
    </div>
  );
};

export default DepartmentDashboard;
