import React, { useEffect, useMemo, useState } from 'react';
import { useForm, useFieldArray } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import {
  CreateRaciMatrixPayload,
  RaciActivity,
  RaciAssignment,
  RaciMatrix,
  RaciMatrixTemplate,
  RaciMatrixType,
  RaciRole,
  RaciRoleType,
  RaciValidationResult,
} from '@/types/entities';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Plus, Trash2, Users, Target, ArrowLeft, ArrowRight, ArrowUp, ArrowDown } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { RaciTemplatePicker } from './RaciTemplatePicker';
import { RaciAssignmentGrid } from './RaciAssignmentGrid';
import { RaciValidationBanner } from './RaciValidationBanner';

// Validation schema
const raciMatrixFormSchema = z.object({
  name: z.string().min(3, 'Name must be at least 3 characters').max(100),
  description: z.string().optional(),
  matrix_type: z.nativeEnum(RaciMatrixType),
  activities: z.array(
    z.object({
      id: z.string(),
      name: z.string().min(1, 'Activity name is required'),
      description: z.string().optional(),
      order: z.number(),
    })
  ).min(1, 'At least one activity is required'),
  roles: z.array(
    z.object({
      id: z.string(),
      name: z.string().min(1, 'Role name is required'),
      title: z.string().optional(),
      user_id: z.string().optional(),
      is_person: z.boolean(),
      order: z.number(),
    })
  ).min(1, 'At least one role is required'),
  assignments: z.array(
    z.object({
      activity_id: z.string(),
      role_id: z.string(),
      role: z.nativeEnum(RaciRoleType),
      notes: z.string().optional(),
    })
  ),
});

type RaciMatrixFormValues = z.infer<typeof raciMatrixFormSchema>;

interface RaciMatrixFormProps {
  matrix?: RaciMatrix | null;
  templates?: RaciMatrixTemplate[];
  initialTemplate?: RaciMatrixTemplate | null;
  onSubmit: (payload: CreateRaciMatrixPayload) => void;
  onCancel?: () => void;
  isSubmitting?: boolean;
}

export const RaciMatrixForm: React.FC<RaciMatrixFormProps> = ({
  matrix,
  templates = [],
  initialTemplate = null,
  onSubmit,
  onCancel,
  isSubmitting = false,
}) => {
  const { toast } = useToast();
  const [assignments, setAssignments] = useState<Record<string, RaciRoleType>>({});
  const [step, setStep] = useState(matrix ? 2 : 1);
  const [selectedTemplate, setSelectedTemplate] = useState<RaciMatrixTemplate | null>(null);

  const form = useForm<RaciMatrixFormValues>({
    resolver: zodResolver(raciMatrixFormSchema),
    defaultValues: {
      name: matrix?.name || '',
      description: matrix?.description || '',
      matrix_type: matrix?.matrix_type || RaciMatrixType.CUSTOM,
      activities:
        matrix?.activities || [{ id: `activity-${Date.now()}`, name: '', description: '', order: 1 }],
      roles: matrix?.roles || [{ id: `role-${Date.now()}`, name: '', title: '', user_id: '', is_person: false, order: 1 }],
      assignments: matrix?.assignments || [],
    },
  });

  const { fields: activityFields, append: appendActivity, remove: removeActivity, move: moveActivity } = useFieldArray({
    control: form.control,
    name: 'activities',
  });

  const { fields: roleFields, append: appendRole, remove: removeRole, move: moveRole } = useFieldArray({
    control: form.control,
    name: 'roles',
  });

  // Hydrate assignments from matrix or template
  useEffect(() => {
    // Prefer the selected template when present so edits can reuse its defaults
    const sourceAssignments = selectedTemplate?.assignments || matrix?.assignments;
    if (sourceAssignments) {
      const map: Record<string, RaciRoleType> = {};
      sourceAssignments.forEach((a) => {
        map[`${a.activity_id}-${a.role_id}`] = a.role as RaciRoleType;
      });
      setAssignments(map);
    }
  }, [matrix, selectedTemplate]);

  const watchedActivities = form.watch('activities');
  const watchedRoles = form.watch('roles');

  const applyTemplate = (tpl: RaciMatrixTemplate) => {
    setSelectedTemplate(tpl);
    form.reset({
      name: tpl.name,
      description: tpl.description,
      matrix_type: tpl.matrix_type,
      activities: tpl.activities,
      roles: tpl.roles,
      assignments: tpl.assignments,
    });
    setStep(2);
  };

  const startCustom = () => {
    setSelectedTemplate(null);
    form.reset({
      name: '',
      description: '',
      matrix_type: RaciMatrixType.CUSTOM,
      activities: [{ id: `activity-${Date.now()}`, name: '', description: '', order: 1 }],
      roles: [{ id: `role-${Date.now()}`, name: '', title: '', user_id: '', is_person: false, order: 1 }],
      assignments: [],
    });
    setAssignments({});
    setStep(2);
  };

  useEffect(() => {
    if (!matrix && initialTemplate && !selectedTemplate) {
      applyTemplate(initialTemplate);
    }
  }, [initialTemplate, matrix, selectedTemplate]);

  const addActivity = () => {
    const newOrder = activityFields.length + 1;
    appendActivity({ id: `activity-${Date.now()}`, name: '', description: '', order: newOrder });
    syncActivityOrder();
  };

  const addRole = () => {
    const newOrder = roleFields.length + 1;
    appendRole({ id: `role-${Date.now()}`, name: '', title: '', user_id: '', is_person: false, order: newOrder });
    syncRoleOrder();
  };

  const syncActivityOrder = () => {
    const current = form.getValues('activities');
    current.forEach((a, idx) => form.setValue(`activities.${idx}.order`, idx + 1));
  };

  const syncRoleOrder = () => {
    const current = form.getValues('roles');
    current.forEach((r, idx) => form.setValue(`roles.${idx}.order`, idx + 1));
  };

  const { validationResult, errorActivities } = useMemo(() => {
    const errors: string[] = [];
    const warnings: string[] = [];
    const activityErrorIds = new Set<string>();

    watchedActivities.forEach((activity) => {
      const activityAssignments = watchedRoles
        .map((r) => assignments[`${activity.id}-${r.id}`])
        .filter(Boolean) as RaciRoleType[];
      const accountable = activityAssignments.filter((a) => a === RaciRoleType.ACCOUNTABLE).length;
      const responsible = activityAssignments.filter((a) => a === RaciRoleType.RESPONSIBLE).length;
      const label = activity.name || 'Untitled activity';
      if (accountable === 0) {
        errors.push(`${label} needs exactly one Accountable (A).`);
        activityErrorIds.add(activity.id);
      }
      if (accountable > 1) {
        errors.push(`${label} has multiple Accountables.`);
        activityErrorIds.add(activity.id);
      }
      if (responsible === 0) {
        errors.push(`${label} needs at least one Responsible (R).`);
        activityErrorIds.add(activity.id);
      }
    });

    watchedRoles.forEach((role) => {
      const used = watchedActivities.some((a) => assignments[`${a.id}-${role.id}`]);
      if (!used) warnings.push(`${role.name || 'Untitled role'} has no assignments.`);
    });

    const stats = {
      total_activities: watchedActivities.length,
      total_roles: watchedRoles.length,
      total_assignments: Object.keys(assignments).length,
      assignments_by_type: {
        R: Object.values(assignments).filter((v) => v === RaciRoleType.RESPONSIBLE).length,
        A: Object.values(assignments).filter((v) => v === RaciRoleType.ACCOUNTABLE).length,
        C: Object.values(assignments).filter((v) => v === RaciRoleType.CONSULTED).length,
        I: Object.values(assignments).filter((v) => v === RaciRoleType.INFORMED).length,
      },
    };

    return {
      validationResult: { is_valid: errors.length === 0, errors, warnings, stats },
      errorActivities: activityErrorIds,
    };
  }, [assignments, watchedActivities, watchedRoles]);

  const handleAssignmentChange = (activityId: string, roleId: string, role: RaciRoleType | null) => {
    const key = `${activityId}-${roleId}`;
    const next = { ...assignments };
    if (role) next[key] = role; else delete next[key];
    setAssignments(next);
  };

  const buildPayload = (data: RaciMatrixFormValues): CreateRaciMatrixPayload => {
    const assignmentArray: RaciAssignment[] = Object.entries(assignments).map(([key, role]) => {
      const [activity_id, role_id] = key.split('-');
      return { activity_id, role_id, role, notes: '' };
    });

    return {
      name: data.name,
      description: data.description || '',
      matrix_type: data.matrix_type,
      activities: data.activities.map((a) => ({ ...a, description: a.description || '' })) as RaciActivity[],
      roles: data.roles.map((r) => ({ ...r, title: r.title || '' })) as RaciRole[],
      assignments: assignmentArray,
      metadata: selectedTemplate ? { created_from_template: selectedTemplate.template_id } : {},
    };
  };

  const handleSubmit = (data: RaciMatrixFormValues) => {
    if (!validationResult.is_valid) {
      toast({
        title: 'Fix validation issues first',
        description: 'Each activity needs exactly one A and at least one R.',
        variant: 'destructive',
      });
      setStep(3);
      return;
    }
    onSubmit(buildPayload(data));
  };

  const stepTitles = ['Choose Template', 'Activities & Roles', 'Assignments'];

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          {stepTitles.map((title, idx) => (
            <React.Fragment key={title}>
              <Badge variant={idx + 1 === step ? 'default' : 'outline'}>{idx + 1}</Badge>
              <span className={idx + 1 === step ? 'text-foreground font-medium' : ''}>{title}</span>
              {idx < stepTitles.length - 1 && <span className="text-muted-foreground">/</span>}
            </React.Fragment>
          ))}
        </div>

        {step === 1 && (
          <Card>
            <CardHeader>
              <CardTitle>Select a starting point</CardTitle>
              <CardDescription>Use a template tuned for common workflows or start from scratch.</CardDescription>
            </CardHeader>
            <CardContent>
              <RaciTemplatePicker
                templates={templates}
                selectedTemplateId={selectedTemplate?.template_id || null}
                selectedType={selectedTemplate?.matrix_type}
                onSelectTemplate={applyTemplate}
                onChooseCustom={startCustom}
              />
              <div className="mt-6 flex justify-end">
                <Button type="button" onClick={() => setStep(2)} disabled={!selectedTemplate && !templates.length}>
                  <ArrowRight className="h-4 w-4 mr-2" />
                  Continue
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step >= 2 && (
          <>
            <Card>
              <CardHeader>
                <CardTitle>Basic Information</CardTitle>
                <CardDescription>Name and describe the workflow you are mapping.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Matrix Name</FormLabel>
                      <FormControl>
                        <Input placeholder="Inventory inbound playbook" {...field} disabled={isSubmitting} />
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
                        <Textarea placeholder="Describe the process or scope" {...field} disabled={isSubmitting} />
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
                      <Select onValueChange={field.onChange} value={field.value} disabled={isSubmitting}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select matrix type" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value={RaciMatrixType.INVENTORY_INBOUND}>Inventory Inbound</SelectItem>
                          <SelectItem value={RaciMatrixType.SHIPBOB_ISSUES}>ShipBob Issues</SelectItem>
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

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Target className="h-5 w-5" /> Activities
                    </CardTitle>
                    <CardDescription>List the steps in order. Use arrows to reorder.</CardDescription>
                  </div>
                  <Button type="button" variant="outline" size="sm" onClick={addActivity} disabled={isSubmitting}>
                    <Plus className="h-4 w-4 mr-1" /> Add Activity
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {activityFields.map((field, index) => (
                  <div key={field.id} className="grid gap-3 md:grid-cols-[1fr,1fr,auto] items-end border rounded-lg p-4">
                    <FormField
                      control={form.control}
                      name={`activities.${index}.name`}
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Activity Name</FormLabel>
                          <FormControl>
                            <Input placeholder={`Activity ${index + 1}`} {...field} disabled={isSubmitting} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name={`activities.${index}.description`}
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Description</FormLabel>
                          <FormControl>
                            <Input placeholder="Optional details" {...field} disabled={isSubmitting} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <div className="flex items-center gap-2 justify-end">
                      <Button type="button" variant="ghost" size="icon" disabled={isSubmitting || index === 0} onClick={() => { moveActivity(index, index - 1); syncActivityOrder(); }}>
                        <ArrowUp className="h-4 w-4" />
                      </Button>
                      <Button type="button" variant="ghost" size="icon" disabled={isSubmitting || index === activityFields.length - 1} onClick={() => { moveActivity(index, index + 1); syncActivityOrder(); }}>
                        <ArrowDown className="h-4 w-4" />
                      </Button>
                      <Button type="button" variant="ghost" size="icon" disabled={isSubmitting || activityFields.length === 1} onClick={() => { removeActivity(index); syncActivityOrder(); }}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Users className="h-5 w-5" /> Roles
                    </CardTitle>
                    <CardDescription>Add roles or people. Mark individuals with the checkbox.</CardDescription>
                  </div>
                  <Button type="button" variant="outline" size="sm" onClick={addRole} disabled={isSubmitting}>
                    <Plus className="h-4 w-4 mr-1" /> Add Role
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {roleFields.map((field, index) => (
                  <div key={field.id} className="grid gap-3 md:grid-cols-[1fr,1fr,auto] items-end border rounded-lg p-4">
                    <FormField
                      control={form.control}
                      name={`roles.${index}.name`}
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Role Name</FormLabel>
                          <FormControl>
                            <Input placeholder="Role or person" {...field} disabled={isSubmitting} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name={`roles.${index}.title`}
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Title</FormLabel>
                          <FormControl>
                            <Input placeholder="Optional" {...field} disabled={isSubmitting} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <div className="flex items-center gap-2 justify-end">
                      <FormField
                        control={form.control}
                        name={`roles.${index}.is_person`}
                        render={({ field }) => (
                          <FormItem className="flex items-center space-x-2">
                            <FormControl>
                              <Checkbox checked={field.value} onCheckedChange={field.onChange} disabled={isSubmitting} />
                            </FormControl>
                            <FormLabel>Person</FormLabel>
                          </FormItem>
                        )}
                      />
                      <div className="flex items-center gap-1">
                        <Button type="button" variant="ghost" size="icon" disabled={isSubmitting || index === 0} onClick={() => { moveRole(index, index - 1); syncRoleOrder(); }}>
                          <ArrowUp className="h-4 w-4" />
                        </Button>
                        <Button type="button" variant="ghost" size="icon" disabled={isSubmitting || index === roleFields.length - 1} onClick={() => { moveRole(index, index + 1); syncRoleOrder(); }}>
                          <ArrowDown className="h-4 w-4" />
                        </Button>
                        <Button type="button" variant="ghost" size="icon" disabled={isSubmitting || roleFields.length === 1} onClick={() => { removeRole(index); syncRoleOrder(); }}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </>
        )}

        {step >= 3 && watchedActivities.length > 0 && watchedRoles.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Assignments</CardTitle>
              <CardDescription>Fill the grid quickly with bulk buttons. Each activity needs one A and at least one R.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <RaciAssignmentGrid
                activities={watchedActivities}
                roles={watchedRoles}
                assignments={assignments}
                onChange={(map) => setAssignments(map)}
                disabled={isSubmitting}
                errorActivities={errorActivities}
              />
              <RaciValidationBanner result={validationResult} />
            </CardContent>
          </Card>
        )}

        <div className="flex justify-between gap-3">
          <div className="flex gap-2">
            {step > 1 && (
              <Button type="button" variant="ghost" onClick={() => setStep(step - 1)} disabled={isSubmitting}>
                <ArrowLeft className="h-4 w-4 mr-2" /> Previous
              </Button>
            )}
            {onCancel && (
              <Button type="button" variant="outline" onClick={onCancel} disabled={isSubmitting}>
                Cancel
              </Button>
            )}
          </div>
          <div className="flex gap-2">
            {step < 3 && (
              <Button type="button" onClick={() => setStep(step + 1)} disabled={isSubmitting}>
                Next <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            )}
            {step === 3 && (
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? 'Saving...' : matrix ? 'Update Matrix' : 'Create Matrix'}
              </Button>
            )}
          </div>
        </div>
      </form>
    </Form>
  );
};
