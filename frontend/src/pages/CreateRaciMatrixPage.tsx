import React, { useState } from 'react';
import { RaciMatrixForm } from "@/components/raci/RaciMatrixForm";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/use-toast";
import { ArrowLeft } from "lucide-react";
import raciMatrixService from '@/services/raciMatrixService';
import { CreateRaciMatrixPayload } from '@/types/entities';

export default function CreateRaciMatrixPage() {
  const { user, loading: authLoading, session } = useAuth();
  const { toast } = useToast();
  const token = session?.access_token;
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleMatrixSubmit = async (payload: CreateRaciMatrixPayload) => {
    try {
      setIsSubmitting(true);
      const response = await raciMatrixService.createMatrix(payload);
      
      toast({
        title: "Success",
        description: `RACI matrix "${response.matrix.name}" created successfully!`,
        duration: 5000,
      });

      if (response.warnings.length > 0) {
        toast({
          title: "Warnings",
          description: response.warnings.join(', '),
          variant: "default",
          duration: 7000,
        });
      }

      // Optionally navigate back or reset form
      // router.push('/raci-dashboard');
    } catch (error) {
      console.error('Failed to create RACI matrix:', error);
      toast({
        title: "Error",
        description: "Failed to create RACI matrix",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (authLoading) {
    return (
      <div className="container mx-auto p-4 md:p-8">
        <Card className="max-w-5xl mx-auto">
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
    console.warn("CreateRaciMatrixPage: No authenticated user or token found after auth check. User:", user, "Token exists:", !!token);
    return (
      <div className="container mx-auto p-4">
        <Card className="max-w-5xl mx-auto">
          <CardHeader>
            <CardTitle>Access Denied</CardTitle>
          </CardHeader>
          <CardContent>
            <p>User information not available or you are not logged in. Please ensure you are logged in to create RACI matrices.</p>
            {/* Optionally, add a button to redirect to login */}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-4 md:p-8">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center gap-4 mb-4">
            <Button variant="ghost" size="sm" onClick={() => window.history.back()}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Button>
            <div>
              <h1 className="text-3xl font-bold">Create RACI Matrix</h1>
              <p className="text-muted-foreground">Define a complete process workflow with multiple activities and role assignments</p>
            </div>
          </div>
        </div>

        {/* RACI Matrix Form */}
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl">Create New RACI Matrix</CardTitle>
            <CardDescription>
              Define a complete process workflow with multiple activities and role assignments.
              This creates a comprehensive RACI matrix similar to the ones shown in your workflow examples.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <RaciMatrixForm
              onSubmit={handleMatrixSubmit}
              onCancel={() => window.history.back()}
              isSubmitting={isSubmitting}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
} 