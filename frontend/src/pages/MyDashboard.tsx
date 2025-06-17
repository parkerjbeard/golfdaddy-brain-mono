
import { useState } from 'react';
import { Card } from "@/components/ui/card";
import { KpiCard } from '@/components/ui/KpiCard';
import { TaskList } from '@/components/ui/TaskList';
import { toast } from "@/components/ui/use-toast";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as z from "zod";

// Form schema for daily summary validation
const dailySummarySchema = z.object({
  summary: z.string().min(10, "Summary must be at least 10 characters long").max(500, "Summary cannot exceed 500 characters")
});

const MyDashboard = () => {
  const [tasks, setTasks] = useState([
    { 
      id: 1, 
      title: 'Complete Project Proposal', 
      description: 'Finish the proposal for the new client project',
      dueDate: '2023-12-20',
      status: 'open',
      category: 'planning' 
    },
    { 
      id: 2, 
      title: 'Review Code Changes', 
      description: 'Review pull request for the frontend updates',
      dueDate: '2023-12-15',
      status: 'done',
      category: 'review' 
    },
    { 
      id: 3, 
      title: 'Prepare Presentation Slides', 
      description: 'Create slides for the team meeting',
      dueDate: '2023-12-18',
      status: 'in-progress',
      category: 'planning' 
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

  // Daily summary form handling
  const form = useForm<z.infer<typeof dailySummarySchema>>({
    resolver: zodResolver(dailySummarySchema),
    defaultValues: {
      summary: ""
    }
  });

  const onSubmitSummary = (data: z.infer<typeof dailySummarySchema>) => {
    // In a real app, you would send this to an API
    console.log("Daily summary submitted:", data);
    
    toast({
      title: "Daily Summary Submitted",
      description: "Your work summary has been submitted successfully."
    });
    
    // Reset the form after submission
    form.reset();
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-4">My Dashboard</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <KpiCard title="Tasks Completed" value="15" description="Out of 20 assigned" />
        <KpiCard title="Projects Assigned" value="8" description="2 in progress" />
        <KpiCard title="Meetings Attended" value="30" description="All required meetings" />
      </div>

      <div className="mt-6">
        <Card>
          <TaskList 
            tasks={tasks} 
            onStatusChange={handleStatusChange} 
          />
        </Card>
      </div>

      {/* Daily Summary Section */}
      <div className="mt-6">
        <Card>
          <div className="p-4">
            <h2 className="text-xl font-semibold mb-4">Daily Work Summary</h2>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmitSummary)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="summary"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>What did you accomplish today?</FormLabel>
                      <FormControl>
                        <Textarea 
                          placeholder="Summarize your work activities for today..." 
                          className="min-h-[120px]" 
                          {...field} 
                        />
                      </FormControl>
                      <div className="text-xs text-muted-foreground text-right mt-1">
                        {field.value.length}/500 characters
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button type="submit">
                  Submit Daily Summary
                </Button>
              </form>
            </Form>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default MyDashboard;
