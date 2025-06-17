
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

interface WorkSummary {
  id: number;
  date: string;
  content: string;
  aiSummary?: string;
}

interface WorkSummariesProps {
  logs: WorkSummary[];
}

export const WorkSummaries = ({ logs }: WorkSummariesProps) => {
  return (
    <div>
      <Card className="p-6">
        <h2 className="text-xl font-medium mb-4">Work Summaries</h2>
        
        {logs.length === 0 ? (
          <div className="text-center p-8 text-muted-foreground">
            No work summaries available for this employee.
          </div>
        ) : (
          <div className="space-y-6">
            {logs.map((log) => (
              <div key={log.id} className="border rounded-lg p-4">
                <div className="flex justify-between items-start mb-2">
                  <div className="font-medium">
                    {new Date(log.date).toLocaleDateString('en-US', {
                      weekday: 'long',
                      month: 'long',
                      day: 'numeric',
                      year: 'numeric'
                    })}
                  </div>
                  <Badge variant="outline" className="bg-blue-50 text-blue-800 border-blue-200">
                    Daily Log
                  </Badge>
                </div>
                <p className="text-sm mb-4 whitespace-pre-line">{log.content}</p>
                {log.aiSummary && (
                  <div className="bg-muted/30 p-3 rounded-md border border-muted">
                    <div className="text-xs font-medium text-muted-foreground mb-1">AI Summary</div>
                    <p className="text-sm">{log.aiSummary}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};
