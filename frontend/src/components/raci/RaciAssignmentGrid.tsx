import React from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { RaciActivity, RaciRole, RaciRoleType } from '@/types/entities';
import { cn } from '@/lib/utils';
import { Eraser, Rows, Columns } from 'lucide-react';

type AssignmentsMap = Record<string, RaciRoleType>;

interface Props {
  activities: RaciActivity[];
  roles: RaciRole[];
  assignments: AssignmentsMap;
  onChange: (assignments: AssignmentsMap) => void;
  disabled?: boolean;
  errorActivities?: Set<string>;
}

const roleOptions = [
  { value: RaciRoleType.RESPONSIBLE, label: 'R - Responsible' },
  { value: RaciRoleType.ACCOUNTABLE, label: 'A - Accountable' },
  { value: RaciRoleType.CONSULTED, label: 'C - Consulted' },
  { value: RaciRoleType.INFORMED, label: 'I - Informed' },
];

export const RaciAssignmentGrid: React.FC<Props> = ({
  activities,
  roles,
  assignments,
  onChange,
  disabled,
  errorActivities,
}) => {
  const handleSet = (activityId: string, roleId: string, value: RaciRoleType | null) => {
    const key = `${activityId}-${roleId}`;
    const next = { ...assignments };
    if (value) {
      next[key] = value;
    } else {
      delete next[key];
    }
    onChange(next);
  };

  const fillRow = (activityId: string, value: RaciRoleType | null) => {
    const next = { ...assignments };
    roles.forEach((role) => {
      const key = `${activityId}-${role.id}`;
      if (value) next[key] = value; else delete next[key];
    });
    onChange(next);
  };

  const fillColumn = (roleId: string, value: RaciRoleType | null) => {
    const next = { ...assignments };
    activities.forEach((activity) => {
      const key = `${activity.id}-${roleId}`;
      if (value) next[key] = value; else delete next[key];
    });
    onChange(next);
  };

  const getAssignment = (activityId: string, roleId: string) => assignments[`${activityId}-${roleId}`] || null;

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse border border-border text-sm">
          <thead>
            <tr className="bg-muted sticky top-0 z-10">
              <th className="border border-border p-3 text-left font-semibold min-w-[200px]">
                Activity
              </th>
              {roles.map((role) => (
                <th key={role.id} className="border border-border p-3 text-center font-semibold min-w-[140px]">
                  <div className="flex flex-col items-center gap-1">
                    <span>{role.name}</span>
                    {role.title && <span className="text-[11px] text-muted-foreground">{role.title}</span>}
                    <div className="flex items-center gap-1 flex-wrap justify-center">
                      {role.is_person && <Badge variant="secondary">Person</Badge>}
                      {roleOptions.map((opt) => (
                        <Button
                          type="button"
                          key={`${role.id}-${opt.value}`}
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => fillColumn(role.id, opt.value)}
                          disabled={disabled}
                          aria-label={`Fill ${role.name} column with ${opt.value}`}
                        >
                          {opt.value}
                        </Button>
                      ))}
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => fillColumn(role.id, null)}
                        disabled={disabled}
                        aria-label={`Clear column for ${role.name}`}
                      >
                        <Eraser className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {activities.map((activity) => (
              <tr key={activity.id} className={cn('hover:bg-muted/30', errorActivities?.has(activity.id) && 'bg-destructive/5')}>
                <td className="border border-border p-3 align-top">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-medium">{activity.name}</div>
                      {activity.description && <div className="text-xs text-muted-foreground mt-1">{activity.description}</div>}
                    </div>
                    <div className="flex items-center gap-1 flex-wrap justify-end">
                      {roleOptions.map((opt) => (
                        <Button
                          type="button"
                          key={`${activity.id}-${opt.value}`}
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => fillRow(activity.id, opt.value)}
                          disabled={disabled}
                          aria-label={`Fill row ${activity.name} with ${opt.value}`}
                        >
                          {opt.value}
                        </Button>
                      ))}
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => fillRow(activity.id, null)}
                        disabled={disabled}
                        aria-label={`Clear row for ${activity.name}`}
                      >
                        <Eraser className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-2 text-[11px] text-muted-foreground">
                    <Badge variant="outline" className="flex items-center gap-1"><Rows className="h-3 w-3" /> Row fill</Badge>
                    <span>Use bulk buttons above per column or clear</span>
                  </div>
                </td>
                {roles.map((role) => (
                  <td key={`${activity.id}-${role.id}`} className="border border-border p-2 text-center align-middle">
                    <Select
                      value={getAssignment(activity.id, role.id) || 'none'}
                      onValueChange={(val) => handleSet(activity.id, role.id, val === 'none' ? null : (val as RaciRoleType))}
                      disabled={disabled}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="None" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">None</SelectItem>
                        {roleOptions.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
        <Badge variant="outline" className="flex items-center gap-1">
          <Rows className="h-3 w-3" /> Row clear button on left
        </Badge>
        <Badge variant="outline" className="flex items-center gap-1">
          <Columns className="h-3 w-3" /> Column clear in headers
        </Badge>
      </div>
    </div>
  );
};
