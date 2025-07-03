import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Clock, 
  CheckCircle, 
  XCircle,
  GitBranch,
  FileText,
  AlertCircle,
  ChevronRight,
  Loader2,
  RefreshCw,
  Eye,
  MessageSquare,
  User,
  Calendar
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/use-toast';
import { formatDistanceToNow } from 'date-fns';

interface DocApproval {
  id: string;
  commitHash: string;
  repository: string;
  diffContent: string;
  patchContent: string;
  status: 'pending' | 'approved' | 'rejected' | 'expired';
  createdAt: string;
  expiresAt: string;
  metadata: {
    commitMessage?: string;
    filesAffected?: number;
    additions?: number;
    deletions?: number;
  };
  approvedBy?: string;
  approvedAt?: string;
  rejectionReason?: string;
  prUrl?: string;
}

export function ApprovalQueue() {
  const [approvals, setApprovals] = useState<DocApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedApproval, setSelectedApproval] = useState<DocApproval | null>(null);
  const [showDiffDialog, setShowDiffDialog] = useState(false);
  const [showRejectDialog, setShowRejectDialog] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('pending');
  const { toast } = useToast();

  useEffect(() => {
    loadApprovals();
    // Poll for updates every 30 seconds
    const interval = setInterval(loadApprovals, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadApprovals = async () => {
    try {
      setLoading(true);
      // TODO: Fetch from API
      const mockApprovals: DocApproval[] = [
        {
          id: '1',
          commitHash: 'abc123def456',
          repository: 'golfdaddy/brain',
          diffContent: `--- a/docs/api.md
+++ b/docs/api.md
@@ -10,6 +10,14 @@ The GolfDaddy Brain API provides endpoints for documentation management.

 All requests require authentication via JWT tokens.

+### Rate Limiting
+
+API requests are rate limited to:
+- 1000 requests per hour for authenticated users
+- 100 requests per hour for unauthenticated users
+
+Exceeded limits return HTTP 429.
+
 ## Endpoints

 ### GET /api/v1/docs`,
          patchContent: `@@ -10,6 +10,14 @@ The GolfDaddy Brain API provides endpoints for documentation management.
 
 All requests require authentication via JWT tokens.
 
+### Rate Limiting
+
+API requests are rate limited to:
+- 1000 requests per hour for authenticated users  
+- 100 requests per hour for unauthenticated users
+
+Exceeded limits return HTTP 429.
+
 ## Endpoints
 
 ### GET /api/v1/docs`,
          status: 'pending',
          createdAt: new Date(Date.now() - 1000 * 60 * 30).toISOString(), // 30 mins ago
          expiresAt: new Date(Date.now() + 1000 * 60 * 60 * 23.5).toISOString(), // 23.5 hours from now
          metadata: {
            commitMessage: 'Add rate limiting documentation',
            filesAffected: 1,
            additions: 8,
            deletions: 0
          }
        },
        {
          id: '2',
          commitHash: 'def789ghi012',
          repository: 'golfdaddy/brain',
          diffContent: `--- a/README.md
+++ b/README.md
@@ -1,4 +1,4 @@
-# GolfDaddy Brain
+# GolfDaddy Brain - AI Documentation Assistant
 
 Automated documentation management system.`,
          patchContent: `@@ -1,4 +1,4 @@
-# GolfDaddy Brain
+# GolfDaddy Brain - AI Documentation Assistant
 
 Automated documentation management system.`,
          status: 'approved',
          createdAt: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), // 2 hours ago
          expiresAt: new Date(Date.now() + 1000 * 60 * 60 * 22).toISOString(),
          metadata: {
            commitMessage: 'Update project title',
            filesAffected: 1,
            additions: 1,
            deletions: 1
          },
          approvedBy: 'user123',
          approvedAt: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
          prUrl: 'https://github.com/golfdaddy/brain/pull/123'
        }
      ];
      setApprovals(mockApprovals);
    } catch (error) {
      console.error('Error loading approvals:', error);
      toast({
        title: 'Error',
        description: 'Failed to load approval queue',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (approval: DocApproval) => {
    try {
      setProcessingId(approval.id);
      // TODO: Call API to approve
      await new Promise(resolve => setTimeout(resolve, 1500)); // Simulate API call
      
      toast({
        title: 'Approved!',
        description: 'Documentation update has been approved and PR created.',
      });
      
      await loadApprovals();
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to approve documentation update',
        variant: 'destructive'
      });
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async () => {
    if (!selectedApproval || !rejectionReason.trim()) return;
    
    try {
      setProcessingId(selectedApproval.id);
      // TODO: Call API to reject with reason
      await new Promise(resolve => setTimeout(resolve, 1500)); // Simulate API call
      
      toast({
        title: 'Rejected',
        description: 'Documentation update has been rejected.',
      });
      
      setShowRejectDialog(false);
      setRejectionReason('');
      setSelectedApproval(null);
      await loadApprovals();
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to reject documentation update',
        variant: 'destructive'
      });
    } finally {
      setProcessingId(null);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'approved':
        return <CheckCircle className="h-4 w-4 text-green-600" />;
      case 'rejected':
        return <XCircle className="h-4 w-4 text-red-600" />;
      case 'expired':
        return <AlertCircle className="h-4 w-4 text-gray-600" />;
      default:
        return <Clock className="h-4 w-4 text-yellow-600" />;
    }
  };

  const getTimeRemaining = (expiresAt: string) => {
    const now = new Date();
    const expiry = new Date(expiresAt);
    const hoursRemaining = Math.floor((expiry.getTime() - now.getTime()) / (1000 * 60 * 60));
    
    if (hoursRemaining < 1) {
      return <span className="text-red-600">Expires soon</span>;
    } else if (hoursRemaining < 6) {
      return <span className="text-orange-600">{hoursRemaining}h remaining</span>;
    } else {
      return <span className="text-muted-foreground">{hoursRemaining}h remaining</span>;
    }
  };

  const filteredApprovals = approvals.filter(approval => {
    if (activeTab === 'pending') return approval.status === 'pending';
    if (activeTab === 'processed') return approval.status !== 'pending';
    return true;
  });

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-center h-32">
            <Loader2 className="h-8 w-8 animate-spin" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Documentation Approval Queue</CardTitle>
              <CardDescription>
                Review and approve AI-generated documentation updates
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={loadApprovals}
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="mb-4">
              <TabsTrigger value="pending">
                Pending ({approvals.filter(a => a.status === 'pending').length})
              </TabsTrigger>
              <TabsTrigger value="processed">
                Processed ({approvals.filter(a => a.status !== 'pending').length})
              </TabsTrigger>
              <TabsTrigger value="all">
                All ({approvals.length})
              </TabsTrigger>
            </TabsList>

            <TabsContent value={activeTab} className="mt-0">
              <ScrollArea className="h-[500px] pr-4">
                <div className="space-y-4">
                  {filteredApprovals.length === 0 ? (
                    <div className="text-center py-12 text-muted-foreground">
                      <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                      <p>No {activeTab === 'pending' ? 'pending' : activeTab === 'processed' ? 'processed' : ''} approvals</p>
                    </div>
                  ) : (
                    filteredApprovals.map((approval) => (
                      <Card key={approval.id} className="relative">
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between mb-3">
                            <div className="flex items-start gap-3">
                              {getStatusIcon(approval.status)}
                              <div>
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="font-medium">{approval.repository}</span>
                                  <Badge variant="outline" className="text-xs">
                                    <GitBranch className="h-3 w-3 mr-1" />
                                    {approval.commitHash.substring(0, 7)}
                                  </Badge>
                                </div>
                                <p className="text-sm text-muted-foreground">
                                  {approval.metadata.commitMessage || 'No commit message'}
                                </p>
                              </div>
                            </div>
                            {approval.status === 'pending' && (
                              <div className="text-sm">
                                {getTimeRemaining(approval.expiresAt)}
                              </div>
                            )}
                          </div>

                          <div className="flex items-center gap-4 text-sm text-muted-foreground mb-3">
                            <span className="flex items-center gap-1">
                              <FileText className="h-3 w-3" />
                              {approval.metadata.filesAffected || 0} files
                            </span>
                            <span className="text-green-600">
                              +{approval.metadata.additions || 0}
                            </span>
                            <span className="text-red-600">
                              -{approval.metadata.deletions || 0}
                            </span>
                            <span className="flex items-center gap-1">
                              <Calendar className="h-3 w-3" />
                              {formatDistanceToNow(new Date(approval.createdAt), { addSuffix: true })}
                            </span>
                          </div>

                          <div className="flex items-center gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setSelectedApproval(approval);
                                setShowDiffDialog(true);
                              }}
                            >
                              <Eye className="h-4 w-4 mr-1" />
                              View Diff
                            </Button>
                            
                            {approval.status === 'pending' && (
                              <>
                                <Button
                                  size="sm"
                                  variant="default"
                                  onClick={() => handleApprove(approval)}
                                  disabled={processingId === approval.id}
                                >
                                  {processingId === approval.id ? (
                                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                                  ) : (
                                    <CheckCircle className="h-4 w-4 mr-1" />
                                  )}
                                  Approve
                                </Button>
                                <Button
                                  size="sm"
                                  variant="destructive"
                                  onClick={() => {
                                    setSelectedApproval(approval);
                                    setShowRejectDialog(true);
                                  }}
                                  disabled={processingId === approval.id}
                                >
                                  <XCircle className="h-4 w-4 mr-1" />
                                  Reject
                                </Button>
                              </>
                            )}

                            {approval.status === 'approved' && approval.prUrl && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => window.open(approval.prUrl, '_blank')}
                              >
                                <GitBranch className="h-4 w-4 mr-1" />
                                View PR
                              </Button>
                            )}
                          </div>

                          {approval.status === 'approved' && approval.approvedBy && (
                            <div className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
                              <User className="h-3 w-3" />
                              Approved by {approval.approvedBy} {approval.approvedAt && formatDistanceToNow(new Date(approval.approvedAt), { addSuffix: true })}
                            </div>
                          )}

                          {approval.status === 'rejected' && approval.rejectionReason && (
                            <div className="mt-3 p-3 bg-destructive/10 rounded-md">
                              <p className="text-sm">
                                <span className="font-medium">Rejection reason:</span> {approval.rejectionReason}
                              </p>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    ))
                  )}
                </div>
              </ScrollArea>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Diff Dialog */}
      <Dialog open={showDiffDialog} onOpenChange={setShowDiffDialog}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Documentation Changes</DialogTitle>
            <DialogDescription>
              Review the proposed documentation updates
            </DialogDescription>
          </DialogHeader>
          <ScrollArea className="flex-1 my-4">
            <pre className="bg-muted p-4 rounded-lg overflow-x-auto text-sm">
              <code>{selectedApproval?.diffContent}</code>
            </pre>
          </ScrollArea>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDiffDialog(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reject Dialog */}
      <Dialog open={showRejectDialog} onOpenChange={setShowRejectDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject Documentation Update</DialogTitle>
            <DialogDescription>
              Please provide a reason for rejecting this update
            </DialogDescription>
          </DialogHeader>
          <div className="my-4">
            <Textarea
              placeholder="Enter rejection reason..."
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              rows={4}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowRejectDialog(false);
                setRejectionReason('');
              }}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleReject}
              disabled={!rejectionReason.trim() || processingId !== null}
            >
              {processingId ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <XCircle className="h-4 w-4 mr-2" />
              )}
              Reject
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}