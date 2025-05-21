import { RaciForm } from "@/components/raci/RaciForm";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/hooks/useAuth";
import { Skeleton } from "@/components/ui/skeleton";

export default function CreateRaciTaskPage() {
  const { user, loading: authLoading, token } = useAuth();

  const handleFormSubmitSuccess = (createdTask: any, warnings: string[]) => {
    console.log("Task created:", createdTask);
    if (warnings.length > 0) {
      console.warn("Task creation warnings:", warnings);
    }
    // Optionally, navigate to another page or clear some state.
    // e.g., router.push(`/tasks/${createdTask.id}`);
  };

  if (authLoading) {
    return (
      <div className="container mx-auto p-4 md:p-8">
        <Card className="max-w-3xl mx-auto">
          <CardHeader>
            <Skeleton className="h-8 w-3/4" />
            <Skeleton className="h-4 w-1/2 mt-2" />
          </CardHeader>
          <CardContent className="space-y-8">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full mt-4" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!user || !user.id || !token) {
    console.warn("CreateRaciTaskPage: No authenticated user or token found after auth check. User:", user, "Token exists:", !!token);
    return (
      <div className="container mx-auto p-4">
        <Card className="max-w-3xl mx-auto">
          <CardHeader>
            <CardTitle>Access Denied</CardTitle>
          </CardHeader>
          <CardContent>
            <p>User information not available or you are not logged in. Please ensure you are logged in to create a task.</p>
            {/* Optionally, add a button to redirect to login */}
          </CardContent>
        </Card>
      </div>
    );
  }
  
  const currentUserId = user.id;

  return (
    <div className="container mx-auto p-4 md:p-8">
      <Card className="max-w-3xl mx-auto">
        <CardHeader>
          <CardTitle className="text-2xl">Create New Task with RACI</CardTitle>
          <CardDescription>
            Fill out the details below to create a new task and assign RACI responsibilities.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <RaciForm 
            currentUserId={currentUserId}
            onSubmitSuccess={handleFormSubmitSuccess} 
          />
        </CardContent>
      </Card>
    </div>
  );
} 