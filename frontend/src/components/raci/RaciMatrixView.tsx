import React from 'react';
import { RaciMatrix, RaciRoleType, RaciActivity, RaciRole, RaciAssignment } from '@/types/entities';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Edit, Trash2, CheckCircle } from "lucide-react";

interface RaciMatrixViewProps {
  matrix: RaciMatrix;
  onEdit?: () => void;
  onDelete?: () => void;
  onValidate?: () => void;
  showActions?: boolean;
}

export const RaciMatrixView: React.FC<RaciMatrixViewProps> = ({
  matrix,
  onEdit,
  onDelete,
  onValidate,
  showActions = false,
}) => {
  // Helper function to get assignments for a specific activity-role combination
  const getAssignments = (activityId: string, roleId: string): RaciAssignment[] => {
    return matrix.assignments.filter(
      (assignment) => assignment.activity_id === activityId && assignment.role_id === roleId
    );
  };

  // Helper function to get the badge variant based on RACI role
  const getRoleVariant = (role: RaciRoleType) => {
    switch (role) {
      case RaciRoleType.RESPONSIBLE:
        return 'destructive'; // Red background
      case RaciRoleType.ACCOUNTABLE:
        return 'default'; // Yellow/orange background
      case RaciRoleType.CONSULTED:
        return 'secondary'; // Green background
      case RaciRoleType.INFORMED:
        return 'outline'; // Blue background
      default:
        return 'outline';
    }
  };

  // Helper function to get cell background color based on RACI role
  const getCellColor = (role: RaciRoleType) => {
    switch (role) {
      case RaciRoleType.RESPONSIBLE:
        return 'bg-red-200 text-red-900'; // Pink/Red background
      case RaciRoleType.ACCOUNTABLE:
        return 'bg-yellow-200 text-yellow-900'; // Yellow background
      case RaciRoleType.CONSULTED:
        return 'bg-green-200 text-green-900'; // Green background
      case RaciRoleType.INFORMED:
        return 'bg-blue-200 text-blue-900'; // Blue background
      default:
        return 'bg-gray-50 text-gray-400';
    }
  };

  // Sort activities and roles by order
  const sortedActivities = [...matrix.activities].sort((a, b) => a.order - b.order);
  const sortedRoles = [...matrix.roles].sort((a, b) => a.order - b.order);

  const validation = React.useMemo(() => {
    const errors: string[] = [];
    const warnings: string[] = [];
    sortedActivities.forEach((activity) => {
      const activityAssignments = matrix.assignments.filter((a) => a.activity_id === activity.id);
      const accountable = activityAssignments.filter((a) => a.role === RaciRoleType.ACCOUNTABLE).length;
      const responsible = activityAssignments.filter((a) => a.role === RaciRoleType.RESPONSIBLE).length;
      if (accountable === 0) errors.push(`${activity.name} missing Accountable`);
      if (accountable > 1) warnings.push(`${activity.name} has multiple Accountables`);
      if (responsible === 0) errors.push(`${activity.name} missing Responsible`);
    });
    sortedRoles.forEach((role) => {
      const used = matrix.assignments.some((a) => a.role_id === role.id);
      if (!used) warnings.push(`${role.name} unassigned`);
    });
    const stats = {
      R: matrix.assignments.filter((a) => a.role === RaciRoleType.RESPONSIBLE).length,
      A: matrix.assignments.filter((a) => a.role === RaciRoleType.ACCOUNTABLE).length,
      C: matrix.assignments.filter((a) => a.role === RaciRoleType.CONSULTED).length,
      I: matrix.assignments.filter((a) => a.role === RaciRoleType.INFORMED).length,
    };
    return { errors, warnings, stats };
  }, [matrix.assignments, sortedActivities, sortedRoles]);

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-3xl font-bold text-gray-900">{matrix.name}</CardTitle>
            {matrix.description && (
              <CardDescription className="mt-2 text-base">{matrix.description}</CardDescription>
            )}
          </div>
          {showActions && (
            <div className="flex gap-2">
              {onValidate && (
                <Button variant="outline" size="sm" onClick={onValidate}>
                  <CheckCircle className="h-4 w-4 mr-1" />
                  Validate
                </Button>
              )}
              {onEdit && (
                <Button variant="outline" size="sm" onClick={onEdit}>
                  <Edit className="h-4 w-4 mr-1" />
                  Edit
                </Button>
              )}
              {onDelete && (
                <Button variant="destructive" size="sm" onClick={onDelete}>
                  <Trash2 className="h-4 w-4 mr-1" />
                  Delete
                </Button>
              )}
            </div>
          )}
        </div>
        
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <Badge variant={validation.errors.length ? 'destructive' : 'secondary'}>
            {validation.errors.length ? `${validation.errors.length} errors` : 'No critical errors'}
          </Badge>
          {validation.warnings.length > 0 && (
            <Badge variant="outline">{validation.warnings.length} warnings</Badge>
          )}
          <Badge variant="outline">R:{validation.stats.R}</Badge>
          <Badge variant="outline">A:{validation.stats.A}</Badge>
          <Badge variant="outline">C:{validation.stats.C}</Badge>
          <Badge variant="outline">I:{validation.stats.I}</Badge>
        </div>

        {/* RACI Legend */}
        <div className="flex items-center gap-4 mt-4 p-4 bg-gray-50 rounded-lg">
          <div className="text-sm font-medium text-gray-700">Legend:</div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1">
              <div className="w-6 h-6 bg-red-200 text-red-900 rounded flex items-center justify-center text-xs font-bold">R</div>
              <span className="text-xs">Responsible</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-6 h-6 bg-yellow-200 text-yellow-900 rounded flex items-center justify-center text-xs font-bold">A</div>
              <span className="text-xs">Accountable</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-6 h-6 bg-green-200 text-green-900 rounded flex items-center justify-center text-xs font-bold">C</div>
              <span className="text-xs">Consulted</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-6 h-6 bg-blue-200 text-blue-900 rounded flex items-center justify-center text-xs font-bold">I</div>
              <span className="text-xs">Informed</span>
            </div>
          </div>
        </div>
      </CardHeader>
      
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse border border-gray-300">
            {/* Header Row */}
            <thead>
              <tr className="bg-gray-50">
                <th className="border border-gray-300 p-4 text-left font-semibold text-gray-900 min-w-[200px]">
                  Project Activity
                </th>
                {sortedRoles.map((role) => (
                  <th key={role.id} className="border border-gray-300 p-4 text-center font-semibold text-gray-900 min-w-[140px]">
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-base">{role.name}</span>
                      {role.title && (
                        <span className="text-xs text-gray-600 font-normal">{role.title}</span>
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            
            {/* Matrix Body */}
            <tbody>
              {sortedActivities.map((activity) => (
                <tr key={activity.id} className="hover:bg-gray-50">
                  <td className="border border-gray-300 p-3 font-medium text-gray-800">
                    <div>
                      <div className="font-semibold">{activity.name}</div>
                      {activity.description && (
                        <div className="text-sm text-gray-600 mt-1">{activity.description}</div>
                      )}
                    </div>
                  </td>
                  {sortedRoles.map((role) => {
                    const assignments = getAssignments(activity.id, role.id);
                    const isOtherColumn = role.name.toLowerCase().includes('other');
                    
                    return (
                      <td key={`${activity.id}-${role.id}`} className="border border-gray-300 p-2 text-center">
                        {assignments.length > 0 ? (
                          isOtherColumn && assignments[0].notes ? (
                            // For "Other" column with notes, display the notes text
                            <div className="text-sm text-green-700 font-medium">
                              {assignments[0].notes}
                            </div>
                          ) : assignments.length > 1 ? (
                            // Multiple RACI assignments (e.g., R/A)
                            <div className="w-12 h-12 mx-auto rounded-sm flex items-center justify-center font-bold text-lg bg-gradient-to-br from-red-200 to-yellow-200 text-gray-900">
                              {assignments.map(a => a.role).join('/')}
                            </div>
                          ) : (
                            // Single RACI assignment
                            <div className={`w-12 h-12 mx-auto rounded-sm flex items-center justify-center font-bold text-lg ${getCellColor(assignments[0].role)}`}>
                              {assignments[0].role}
                            </div>
                          )
                        ) : (
                          // Empty cell
                          <div className="w-12 h-12 mx-auto rounded-sm flex items-center justify-center text-gray-300 text-lg">
                            {isOtherColumn ? '' : '/'}
                          </div>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        {/* Matrix Info */}
        <div className="mt-6 flex flex-wrap gap-4 text-sm text-gray-600">
          <div>
            <strong>Activities:</strong> {matrix.activities.length}
          </div>
          <div>
            <strong>Roles:</strong> {matrix.roles.length}
          </div>
          <div>
            <strong>Assignments:</strong> {matrix.assignments.length}
          </div>
          <div>
            <strong>Type:</strong> {matrix.matrix_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
          </div>
          {matrix.created_at && (
            <div>
              <strong>Created:</strong> {new Date(matrix.created_at).toLocaleDateString()}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}; 
