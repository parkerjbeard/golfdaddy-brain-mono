import React, { useState, useEffect } from 'react';
import { useForm, useFieldArray } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import {
  RaciMatrix,
  RaciMatrixType,
  RaciRoleType,
  RaciActivity,
  RaciRole,
  RaciAssignment,
  CreateRaciMatrixPayload,
  User
} from '@/types/entities';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Plus, Trash2, Users, Target } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { UserSelector } from './UserSelector';

// Form validation schema
const raciMatrixFormSchema = z.object({
  name: z.string().min(3, 'Name must be at least 3 characters').max(100),
  description: z.string().optional(),
  matrix_type: z.nativeEnum(RaciMatrixType),
  activities: z.array(z.object({
    id: z.string(),
    name: z.string().min(1, 'Activity name is required'),
    description: z.string().optional(),
    order: z.number()
  })).min(1, 'At least one activity is required'),
  roles: z.array(z.object({
    id: z.string(),
    name: z.string().min(1, 'Role name is required'),
    title: z.string().optional(),
    user_id: z.string().optional(),
    is_person: z.boolean(),
    order: z.number()
  })).min(1, 'At least one role is required'),
  assignments: z.array(z.object({
    activity_id: z.string(),
    role_id: z.string(),
    role: z.nativeEnum(RaciRoleType),
    notes: z.string().optional()
  }))
});

type RaciMatrixFormValues = z.infer<typeof raciMatrixFormSchema>;

interface RaciMatrixFormProps {
  matrix?: RaciMatrix | null;
  allUsers?: User[];
  onSubmit: (payload: CreateRaciMatrixPayload) => void;
  onCancel?: () => void;
  isSubmitting?: boolean;
}

export const RaciMatrixForm: React.FC<RaciMatrixFormProps> = ({
  matrix,
  allUsers = [],
  onSubmit,
  onCancel,
  isSubmitting = false
}) => {
  const { toast } = useToast();
  const [assignments, setAssignments] = useState<Record<string, RaciRoleType>>({});

  const form = useForm<RaciMatrixFormValues>({
    resolver: zodResolver(raciMatrixFormSchema),
    defaultValues: {
      name: matrix?.name || '',
      description: matrix?.description || '',
      matrix_type: matrix?.matrix_type || RaciMatrixType.CUSTOM,
      activities: matrix?.activities || [{ id: 'activity-1', name: '', description: '', order: 1 }],
      roles: matrix?.roles || [{ id: 'role-1', name: '', title: '', user_id: '', is_person: false, order: 1 }],
      assignments: matrix?.assignments || []
    }
  });

  const { fields: activityFields, append: appendActivity, remove: removeActivity } = useFieldArray({
    control: form.control,
    name: 'activities'
  });

  const { fields: roleFields, append: appendRole, remove: removeRole } = useFieldArray({
    control: form.control,
    name: 'roles'
  });

  // Initialize assignments state from matrix data
  useEffect(() => {
    if (matrix?.assignments) {
      const assignmentMap: Record<string, RaciRoleType> = {};
      matrix.assignments.forEach(assignment => {
        assignmentMap[`${assignment.activity_id}-${assignment.role_id}`] = assignment.role;
      });
      setAssignments(assignmentMap);
    }
  }, [matrix]);

  // Handle assignment changes in the grid
  const handleAssignmentChange = (activityId: string, roleId: string, role: RaciRoleType | null) => {
    const key = `${activityId}-${roleId}`;
    const newAssignments = { ...assignments };
    
    if (role) {
      newAssignments[key] = role;
    } else {
      delete newAssignments[key];
    }
    
    setAssignments(newAssignments);
  };

  // Get current assignment for a cell
  const getAssignment = (activityId: string, roleId: string): RaciRoleType | null => {
    return assignments[`${activityId}-${roleId}`] || null;
  };

  // Add new activity
  const addActivity = () => {
    const newOrder = activityFields.length + 1;
    appendActivity({
      id: `activity-${Date.now()}`,
      name: '',
      description: '',
      order: newOrder
    });
  };

  // Add new role
  const addRole = () => {
    const newOrder = roleFields.length + 1;
    appendRole({
      id: `role-${Date.now()}`,
      name: '',
      title: '',
      user_id: '',
      is_person: false,
      order: newOrder
    });
  };

  // Handle form submission
  const handleSubmit = (data: RaciMatrixFormValues) => {
    // Convert assignments object to array
    const assignmentArray: RaciAssignment[] = Object.entries(assignments).map(([key, role]) => {
      const [activityId, roleId] = key.split('-');
      return {
        activity_id: activityId,
        role_id: roleId,
        role,
        notes: ''
      };
    });

    // Explicitly construct the payload to match CreateRaciMatrixPayload type
    const payload: CreateRaciMatrixPayload = {
      name: data.name,
      description: data.description || '',  // Ensure description is always a string
      matrix_type: data.matrix_type,
      activities: data.activities.map(activity => ({
        ...activity,
        description: activity.description || ''  // Ensure activity descriptions are strings
      })) as RaciActivity[],
      roles: data.roles.map(role => ({
        ...role,
        title: role.title || ''  // Ensure role titles are strings
      })) as RaciRole[],
      assignments: assignmentArray,
      metadata: {}
    };

    onSubmit(payload);
  };

  const watchedActivities = form.watch('activities');
  const watchedRoles = form.watch('roles');

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
        {/* Basic Information */}
        <Card>
          <CardHeader>
            <CardTitle>Basic Information</CardTitle>
            <CardDescription>Define the basic details of your RACI matrix</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Matrix Name</FormLabel>
                  <FormControl>
                    <Input placeholder="Enter matrix name" {...field} disabled={isSubmitting} />
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
                  <FormLabel>Description (Optional)</FormLabel>
                  <FormControl>
                    <Textarea placeholder="Describe the process or workflow" {...field} disabled={isSubmitting} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="matrix_type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Matrix Type</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value} disabled={isSubmitting}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select matrix type" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value={RaciMatrixType.INVENTORY_INBOUND}>Inventory Inbound</SelectItem>
                      <SelectItem value={RaciMatrixType.SHIPBOB_ISSUES}>Shipbob Issues</SelectItem>
                      <SelectItem value={RaciMatrixType.DATA_COLLECTION}>Data Collection</SelectItem>
                      <SelectItem value={RaciMatrixType.RETAIL_LOGISTICS}>Retail Logistics</SelectItem>
                      <SelectItem value={RaciMatrixType.CUSTOM}>Custom</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        {/* Activities */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Target className="h-5 w-5" />
                  Activities
                </CardTitle>
                <CardDescription>Define the process activities</CardDescription>
              </div>
              <Button type="button" variant="outline" size="sm" onClick={addActivity} disabled={isSubmitting}>
                <Plus className="h-4 w-4 mr-1" />
                Add Activity
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {activityFields.map((field, index) => (
                <div key={field.id} className="flex items-end gap-4 p-4 border rounded-lg">
                  <FormField
                    control={form.control}
                    name={`activities.${index}.name`}
                    render={({ field }) => (
                      <FormItem className="flex-1">
                        <FormLabel>Activity Name</FormLabel>
                        <FormControl>
                          <Input placeholder="Enter activity name" {...field} disabled={isSubmitting} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  
                  <FormField
                    control={form.control}
                    name={`activities.${index}.description`}
                    render={({ field }) => (
                      <FormItem className="flex-1">
                        <FormLabel>Description (Optional)</FormLabel>
                        <FormControl>
                          <Input placeholder="Activity description" {...field} disabled={isSubmitting} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  {activityFields.length > 1 && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => removeActivity(index)}
                      disabled={isSubmitting}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Roles */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  Roles
                </CardTitle>
                <CardDescription>Define the roles and people involved</CardDescription>
              </div>
              <Button type="button" variant="outline" size="sm" onClick={addRole} disabled={isSubmitting}>
                <Plus className="h-4 w-4 mr-1" />
                Add Role
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {roleFields.map((field, index) => (
                <div key={field.id} className="flex items-end gap-4 p-4 border rounded-lg">
                  <FormField
                    control={form.control}
                    name={`roles.${index}.name`}
                    render={({ field }) => (
                      <FormItem className="flex-1">
                        <FormLabel>Role Name</FormLabel>
                        <FormControl>
                          <Input placeholder="Enter role name" {...field} disabled={isSubmitting} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  
                  <FormField
                    control={form.control}
                    name={`roles.${index}.title`}
                    render={({ field }) => (
                      <FormItem className="flex-1">
                        <FormLabel>Title (Optional)</FormLabel>
                        <FormControl>
                          <Input placeholder="Job title" {...field} disabled={isSubmitting} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name={`roles.${index}.is_person`}
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center space-x-3 space-y-0">
                        <FormControl>
                          <Checkbox
                            checked={field.value}
                            onCheckedChange={field.onChange}
                            disabled={isSubmitting}
                          />
                        </FormControl>
                        <div className="space-y-1 leading-none">
                          <FormLabel>Specific Person</FormLabel>
                        </div>
                      </FormItem>
                    )}
                  />

                  {roleFields.length > 1 && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => removeRole(index)}
                      disabled={isSubmitting}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* RACI Assignments Grid */}
        {watchedActivities.length > 0 && watchedRoles.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>RACI Assignments</CardTitle>
              <CardDescription>Assign RACI roles for each activity-role combination</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse border border-gray-300">
                  <thead>
                    <tr className="bg-gray-100">
                      <th className="border border-gray-300 p-3 text-left font-semibold min-w-[200px]">
                        Activity
                      </th>
                      {watchedRoles.map((role, roleIndex) => (
                        <th key={role.id} className="border border-gray-300 p-3 text-center font-semibold min-w-[120px]">
                          {role.name || `Role ${roleIndex + 1}`}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {watchedActivities.map((activity, activityIndex) => (
                      <tr key={activity.id} className="hover:bg-gray-50">
                        <td className="border border-gray-300 p-3 font-medium">
                          {activity.name || `Activity ${activityIndex + 1}`}
                        </td>
                        {watchedRoles.map((role) => {
                          const currentAssignment = getAssignment(activity.id, role.id);
                          return (
                            <td key={`${activity.id}-${role.id}`} className="border border-gray-300 p-3 text-center">
                              <Select
                                value={currentAssignment || 'none'}
                                onValueChange={(value) => 
                                  handleAssignmentChange(activity.id, role.id, value === 'none' ? null : value as RaciRoleType)
                                }
                                disabled={isSubmitting}
                              >
                                <SelectTrigger className="w-full">
                                  <SelectValue placeholder="None" />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="none">None</SelectItem>
                                  <SelectItem value={RaciRoleType.RESPONSIBLE}>R - Responsible</SelectItem>
                                  <SelectItem value={RaciRoleType.ACCOUNTABLE}>A - Accountable</SelectItem>
                                  <SelectItem value={RaciRoleType.CONSULTED}>C - Consulted</SelectItem>
                                  <SelectItem value={RaciRoleType.INFORMED}>I - Informed</SelectItem>
                                </SelectContent>
                              </Select>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Form Actions */}
        <div className="flex justify-end gap-4">
          {onCancel && (
            <Button type="button" variant="outline" onClick={onCancel} disabled={isSubmitting}>
              Cancel
            </Button>
          )}
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Saving...' : matrix ? 'Update Matrix' : 'Create Matrix'}
          </Button>
        </div>
      </form>
    </Form>
  );
}; 