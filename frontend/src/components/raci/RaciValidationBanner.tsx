import React from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, AlertTriangle, Info } from 'lucide-react';
import { RaciValidationResult } from '@/types/entities';

interface Props {
  result: RaciValidationResult;
  className?: string;
}

export const RaciValidationBanner: React.FC<Props> = ({ result, className }) => {
  const hasErrors = result.errors?.length > 0;
  const hasWarnings = result.warnings?.length > 0;

  if (!hasErrors && !hasWarnings) {
    return (
      <Alert className={className}>
        <CheckCircle2 className="h-4 w-4" />
        <AlertTitle>Looks good</AlertTitle>
        <AlertDescription>
          No validation issues detected. Each activity has exactly one Accountable and at least one Responsible.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Alert variant={hasErrors ? 'destructive' : 'default'} className={className}>
      {hasErrors ? <AlertTriangle className="h-4 w-4" /> : <Info className="h-4 w-4" />}
      <AlertTitle>{hasErrors ? 'Issues to fix' : 'Warnings'}</AlertTitle>
      <AlertDescription className="space-y-1">
        {hasErrors && (
          <div className="flex items-start gap-2">
            <Badge variant="destructive">Errors</Badge>
            <ul className="list-disc list-inside space-y-1 text-sm">
              {result.errors.map((err, idx) => (
                <li key={`err-${idx}`}>{err}</li>
              ))}
            </ul>
          </div>
        )}
        {hasWarnings && (
          <div className="flex items-start gap-2">
            <Badge variant="secondary">Warnings</Badge>
            <ul className="list-disc list-inside space-y-1 text-sm">
              {result.warnings.map((warn, idx) => (
                <li key={`warn-${idx}`}>{warn}</li>
              ))}
            </ul>
          </div>
        )}
      </AlertDescription>
    </Alert>
  );
};

