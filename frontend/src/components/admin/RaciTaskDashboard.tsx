import React, { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, Plus, Grid } from "lucide-react";
import { RaciMatrix } from '@/types/entities';
import { RaciMatrixView } from '../raci/RaciMatrixView';
import { RaciMatrixForm } from '../raci/RaciMatrixForm';
import raciMatrixService from '@/services/raciMatrixService';
import { useToast } from '@/components/ui/use-toast';

export const RaciTaskDashboard: React.FC = () => {
  const { user } = useAuth();
  const { toast } = useToast();

  // RACI Matrices state
  const [matrices, setMatrices] = useState<RaciMatrix[]>([]);
  const [matricesLoading, setMatricesLoading] = useState(true);
  const [matricesError, setMatricesError] = useState<string | null>(null);
  const [selectedMatrix, setSelectedMatrix] = useState<RaciMatrix | null>(null);
  const [showMatrixForm, setShowMatrixForm] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    // Load matrices on component mount
    loadMatrices();
  }, []);

  const loadMatrices = async () => {
    try {
      setMatricesLoading(true);
      setMatricesError(null);
      const data = await raciMatrixService.getAllMatrices();
      setMatrices(data);
    } catch (error) {
      console.error('Failed to load RACI matrices:', error);
      setMatricesError('Failed to load RACI matrices');
      toast({
        title: "Error",
        description: "Failed to load RACI matrices",
        variant: "destructive",
      });
    } finally {
      setMatricesLoading(false);
    }
  };

  const handleCreateMatrix = async (payload: any) => {
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

      setShowMatrixForm(false);
      await loadMatrices();
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

  const handleEditMatrix = (matrix: RaciMatrix) => {
    setSelectedMatrix(matrix);
    setShowMatrixForm(true);
  };

  const handleDeleteMatrix = async (matrixId: string) => {
    try {
      await raciMatrixService.deleteMatrix(matrixId);
      toast({
        title: "Success",
        description: "RACI matrix deleted successfully",
      });
      await loadMatrices();
    } catch (error) {
      console.error('Failed to delete RACI matrix:', error);
      toast({
        title: "Error",
        description: "Failed to delete RACI matrix",
        variant: "destructive",
      });
    }
  };

  const handleValidateMatrix = async (matrixId: string) => {
    try {
      const result = await raciMatrixService.validateMatrix(matrixId);
      
      if (result.is_valid) {
        toast({
          title: "Validation Success",
          description: "RACI matrix is valid",
        });
      } else {
        toast({
          title: "Validation Issues",
          description: result.errors.join(', '),
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to validate RACI matrix:', error);
      toast({
        title: "Error",
        description: "Failed to validate RACI matrix",
        variant: "destructive",
      });
    }
  };

  if (matricesLoading) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-8 w-1/4" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  if (matricesError) {
    return (
      <Alert variant="destructive" className="m-4">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{matricesError}</AlertDescription>
      </Alert>
    );
  }

  if (showMatrixForm) {
    return (
      <div className="p-6">
        <Card>
          <CardHeader>
            <CardTitle>{selectedMatrix ? 'Edit RACI Matrix' : 'Create New RACI Matrix'}</CardTitle>
            <CardDescription>
              {selectedMatrix ? 'Modify the existing RACI matrix' : 'Define a new process workflow with RACI assignments'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <RaciMatrixForm
              matrix={selectedMatrix}
              onSubmit={handleCreateMatrix}
              onCancel={() => {
                setShowMatrixForm(false);
                setSelectedMatrix(null);
              }}
              isSubmitting={isSubmitting}
            />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">RACI Management</h1>
          <p className="text-muted-foreground">Manage RACI matrices for process workflows</p>
        </div>
        <Button onClick={() => setShowMatrixForm(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Create Matrix
        </Button>
      </div>

      <div className="space-y-6">
        {matrices.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Grid className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold">No RACI Matrices</h3>
              <p className="text-muted-foreground text-center max-w-md">
                Get started by creating your first RACI matrix to define process workflows and responsibilities.
              </p>
              <Button className="mt-4" onClick={() => setShowMatrixForm(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Create Your First Matrix
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-6">
            {matrices.map((matrix) => (
              <RaciMatrixView
                key={matrix.id}
                matrix={matrix}
                showActions={true}
                onEdit={() => handleEditMatrix(matrix)}
                onDelete={() => handleDeleteMatrix(matrix.id)}
                onValidate={() => handleValidateMatrix(matrix.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}; 