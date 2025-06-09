import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { format } from "date-fns";
import { CalendarIcon } from "@radix-ui/react-icons";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useToast } from "@/components/ui/use-toast";
import { UserSelector } from "./UserSelector";
import { MultiUserSelector } from "./MultiUserSelector";
import { User, CreateTaskPayload, CreateTaskResponse } from "@/types/entities";
import { useAuth } from "@/contexts/AuthContext";
import api from "@/services/api";
import { Skeleton } from "@/components/ui/skeleton";

// Define the form schema using Zod
const raciFormSchema = z.object({
  title: z.string().min(3, { message: "Title must be at least 3 characters." }).max(100),
  description: z.string().min(10, { message: "Description must be at least 10 characters." }).max(1000),
  assignee: z.custom<User>((val) => val instanceof Object && val !== null && 'id' in val, {
    message: "Assignee is required.",
  }),
  responsible: z.custom<User | null>().optional().nullable(),
  accountable: z.custom<User | null>().optional().nullable(),
  consulted: z.array(z.custom<User>()).optional(),
  informed: z.array(z.custom<User>()).optional(),
  creator_id: z.string().uuid({ message: "Valid Creator ID is required." }),
  due_date: z.date().optional().nullable(),
  task_type: z.string().optional().nullable(),
  priority: z.string().optional().nullable(),
});

export type RaciFormValues = z.infer<typeof raciFormSchema>;

interface RaciFormProps {
  currentUserId: string;
  onSubmitSuccess?: (createdTask: any, warnings: string[]) => void;
  className?: string;
}

export function RaciForm({ currentUserId, onSubmitSuccess, className }: RaciFormProps) {
  const { toast } = useToast();
  const { session, loading: authLoading } = useAuth();
  const token = session?.access_token || null;
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  
  const [allUsers, setAllUsers] = React.useState<User[]>([]);
  const [usersLoading, setUsersLoading] = React.useState(true);
  const [usersError, setUsersError] = React.useState<string | null>(null);

  const form = useForm<RaciFormValues>({
    resolver: zodResolver(raciFormSchema),
    defaultValues: {
      title: "",
      description: "",
      consulted: [],
      informed: [],
      creator_id: currentUserId,
      due_date: null,
      task_type: "",
      priority: "",
    },
  });

  React.useEffect(() => {
    if (authLoading) {
      return;
    }
    
    if (!session || !token) {
      console.warn("RaciForm: No session/token available, cannot fetch users for selectors.");
      setUsersLoading(false);
      setUsersError("Authentication token not available.");
      setAllUsers([]);
      return;
    }

    async function loadAllUsers() {
      console.log("RaciForm: Attempting to load all users for selectors.");
      setUsersLoading(true);
      setUsersError(null);
      try {
        const fetchedUsers = await api.users.getUsers();
        setAllUsers(fetchedUsers);
        console.log("RaciForm: Successfully fetched all users:", fetchedUsers.length);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : "Failed to load users for form";
        console.error("RaciForm: Error fetching all users:", error);
        setUsersError(errorMessage);
        setAllUsers([]);
      }
      setUsersLoading(false);
    }

    loadAllUsers();
  }, [token, authLoading]);

  async function onSubmit(data: RaciFormValues) {
    if (!token) {
        toast({
            title: "Authentication Error",
            description: "Cannot create task. Missing authentication token.",
            variant: "destructive",
        });
        return;
    }
    setIsSubmitting(true);
    const payload: CreateTaskPayload = {
      title: data.title,
      description: data.description,
      assignee_id: data.assignee.id,
      responsible_id: data.responsible?.id || null,
      accountable_id: data.accountable?.id || null,
      consulted_ids: data.consulted?.map(u => u.id) || [],
      informed_ids: data.informed?.map(u => u.id) || [],
      creator_id: data.creator_id,
      due_date: data.due_date ? format(data.due_date, "yyyy-MM-dd'T'HH:mm:ss.SSSxxx") : null,
      task_type: data.task_type || null,
      priority: data.priority || null,
      metadata: {},
    };

    try {
      const { task: createdTask, warnings: apiWarnings } = await api.tasks.createRaciTask(payload);
      
      // Log the createdTask object to inspect its structure and values
      console.log("API Response - createdTask:", createdTask);

      // Ensure warnings is an array, defaulting to an empty array if nullish
      const warnings = Array.isArray(apiWarnings) ? apiWarnings : [];

      // Safely access title for the toast message
      const taskTitle = createdTask?.title ?? data.title;
      const successMessage = `Task "${taskTitle}" has been assigned.`;
      
      toast({
        title: "Task Created Successfully!",
        description: successMessage + 
                     (warnings.length > 0 ? ` Warnings: ${warnings.join(", ")}` : ""),
        variant: warnings.length > 0 ? "default" : "default",
        duration: 7000,
      });
      form.reset();
      if (onSubmitSuccess) {
        onSubmitSuccess(createdTask, warnings);
      }
    } catch (error) {
      console.error("Failed to create task:", error);
      toast({
        title: "Error Creating Task",
        description: error instanceof Error ? error.message : "An unexpected error occurred.",
        variant: "destructive",
      });
    }
    setIsSubmitting(false);
  }

  if (usersLoading && !authLoading) {
    return (
      <div className="space-y-8">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full mt-4" />
      </div>
    );
  }

  if (usersError) {
    return (
        <div className="text-red-600 p-4 border border-red-300 rounded-md bg-red-50">
            <p className="font-semibold">Error loading user data for selectors:</p>
            <p>{usersError}</p>
            <p className="mt-2 text-sm">Please try refreshing the page. If the issue persists, contact support.</p>
        </div>
    );
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className={cn("space-y-8", className)}>
        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Title</FormLabel>
              <FormControl>
                <Input placeholder="Enter task title" {...field} disabled={isSubmitting}/>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description</FormLabel>
              <FormControl>
                <Textarea placeholder="Describe the task in detail" {...field} rows={5} disabled={isSubmitting}/>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        
        <FormField
            control={form.control}
            name="creator_id"
            render={({ field }) => (
                <FormItem className="hidden">
                    <FormControl>
                        <Input {...field} />
                    </FormControl>
                </FormItem>
            )}
        />

        <FormField
          control={form.control}
          name="assignee"
          render={({ field }) => (
            <FormItem className="flex flex-col">
              <FormLabel>Assignee (Required)</FormLabel>
              <UserSelector 
                selectedUser={field.value}
                onSelectUser={field.onChange}
                placeholder="Select Assignee"
                allUsersList={allUsers}
                isLoading={usersLoading}
                error={usersError}
                disabled={isSubmitting || usersLoading || !!usersError}
              />
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="responsible"
          render={({ field }) => (
            <FormItem className="flex flex-col">
              <FormLabel>Responsible (Optional - defaults to Assignee)</FormLabel>
              <UserSelector 
                selectedUser={field.value}
                onSelectUser={field.onChange}
                placeholder="Select Responsible User"
                allUsersList={allUsers}
                isLoading={usersLoading}
                error={usersError}
                disabled={isSubmitting || usersLoading || !!usersError}
              />
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="accountable"
          render={({ field }) => (
            <FormItem className="flex flex-col">
              <FormLabel>Accountable (Optional - defaults to Assignee)</FormLabel>
              <UserSelector 
                selectedUser={field.value}
                onSelectUser={field.onChange}
                placeholder="Select Accountable User"
                allUsersList={allUsers}
                isLoading={usersLoading}
                error={usersError}
                disabled={isSubmitting || usersLoading || !!usersError}
              />
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="consulted"
          render={({ field }) => (
            <FormItem className="flex flex-col">
              <FormLabel>Consulted (Optional)</FormLabel>
              <MultiUserSelector
                selectedUsers={field.value || []}
                onSelectedUsersChange={field.onChange}
                placeholder="Select Consulted Users"
                allUsersList={allUsers}
                isLoading={usersLoading}
                error={usersError}
                disabled={isSubmitting || usersLoading || !!usersError}
              />
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="informed"
          render={({ field }) => (
            <FormItem className="flex flex-col">
              <FormLabel>Informed (Optional)</FormLabel>
              <MultiUserSelector
                selectedUsers={field.value || []}
                onSelectedUsersChange={field.onChange}
                placeholder="Select Informed Users"
                allUsersList={allUsers}
                isLoading={usersLoading}
                error={usersError}
                disabled={isSubmitting || usersLoading || !!usersError}
              />
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="due_date"
          render={({ field }) => (
            <FormItem className="flex flex-col">
              <FormLabel>Due Date (Optional)</FormLabel>
              <Popover>
                <PopoverTrigger asChild>
                  <FormControl>
                    <Button
                      variant={"outline"}
                      className={cn(
                        "w-full pl-3 text-left font-normal",
                        !field.value && "text-muted-foreground"
                      )}
                      disabled={isSubmitting}
                    >
                      {field.value ? (
                        format(field.value, "PPP")
                      ) : (
                        <span>Pick a date</span>
                      )}
                      <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                    </Button>
                  </FormControl>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <Calendar
                    mode="single"
                    selected={field.value}
                    onSelect={field.onChange}
                    disabled={(date) => date < new Date(new Date().setDate(new Date().getDate() -1)) || isSubmitting}
                    initialFocus
                  />
                </PopoverContent>
              </Popover>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="task_type"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Task Type (Optional)</FormLabel>
              <FormControl>
                <Input placeholder="e.g., Feature, Bug, Chore" {...field} value={field.value || ''} disabled={isSubmitting}/>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        
        <FormField
          control={form.control}
          name="priority"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Priority (Optional)</FormLabel>
              <FormControl>
                <Input placeholder="e.g., High, Medium, Low" {...field} value={field.value || ''} disabled={isSubmitting}/>
              </FormControl>
              <FormDescription>
                Standard values could be: URGENT, HIGH, MEDIUM, LOW.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit" className="w-full" disabled={isSubmitting || usersLoading || !!usersError}>
          {isSubmitting ? "Submitting..." : "Create Task"}
        </Button>
      </form>
    </Form>
  );
} 