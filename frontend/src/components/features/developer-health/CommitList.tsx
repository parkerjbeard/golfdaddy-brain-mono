import React from 'react';
import { CommitSummary } from '@/services/developerInsightsApi';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ExternalLink } from 'lucide-react'; // Assuming you might link to commit URLs later

interface CommitListProps {
  commits: CommitSummary[];
  isLoading: boolean; // Pass loading state if list is loaded separately
}

// Helper to format timestamp
const formatTimestamp = (isoString: string) => {
  try {
    return new Date(isoString).toLocaleString();
  } catch (e) {
    return isoString; // Fallback
  }
};

const CommitList: React.FC<CommitListProps> = ({ commits, isLoading }) => {
  if (isLoading) {
      // Basic loading state for the table
    return (
        <Card>
            <CardHeader><CardTitle>Commits</CardTitle></CardHeader>
            <CardContent>
                 <div className="h-40 bg-gray-200 rounded animate-pulse"></div>
            </CardContent>
        </Card>
    );
  }
  
  if (!commits || commits.length === 0) {
    return (
      <Card>
        <CardHeader><CardTitle>Commits</CardTitle></CardHeader>
        <CardContent>
          <p className="text-center text-gray-500">No commits found for the selected date.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Commits ({commits.length})</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[100px]">Hash</TableHead>
              <TableHead>Message</TableHead>
              <TableHead className="text-right">Hours</TableHead>
              <TableHead className="text-right">Seniority</TableHead>
              <TableHead className="text-right">Timestamp</TableHead>
              {/* <TableHead className="text-right">Link</TableHead> Add if commit URL is available */}
            </TableRow>
          </TableHeader>
          <TableBody>
            {commits.map((commit) => (
              <TableRow key={commit.commit_hash}>
                <TableCell className="font-mono text-xs">{commit.commit_hash.substring(0, 7)}</TableCell>
                <TableCell className="max-w-xs truncate" title={commit.commit_message || ''}>
                    {commit.commit_message || <span className="italic text-gray-400">No message</span>}
                </TableCell>
                <TableCell className="text-right">{commit.ai_estimated_hours?.toFixed(1) ?? 'N/A'}</TableCell>
                <TableCell className="text-right">{commit.seniority_score ?? 'N/A'}</TableCell>
                <TableCell className="text-right text-xs">{formatTimestamp(commit.commit_timestamp)}</TableCell>
                {/* <TableCell className="text-right"><a href={commit.commit_url} target="_blank" rel="noopener noreferrer"><ExternalLink className="h-4 w-4" /></a></TableCell> */}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
};

export default CommitList; 