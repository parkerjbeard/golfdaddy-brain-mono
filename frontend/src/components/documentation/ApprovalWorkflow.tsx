import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { 
  CheckCircle, 
  Clock, 
  XCircle, 
  MessageSquare,
  User,
  Calendar,
  FileText,
  Send,
  Eye,
  ThumbsUp,
  ThumbsDown,
  RotateCcw
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface ApprovalRequest {
  id: string;
  title: string;
  doc_type: string;
  author: string;
  status: 'pending' | 'approved' | 'rejected' | 'needs_review';
  created_at: string;
  expires_at?: string;
  quality_score?: number;
  reviewers: string[];
  reviews: Review[];
}

interface Review {
  reviewer_id: string;
  reviewer_role: string;
  decision: 'approve' | 'reject' | 'request_changes';
  comments: string;
  reviewed_at: string;
}

export function ApprovalWorkflow() {
  const [requests, setRequests] = useState<ApprovalRequest[]>([]);
  const [selectedRequest, setSelectedRequest] = useState<ApprovalRequest | null>(null);
  const [reviewDecision, setReviewDecision] = useState<string>('');
  const [reviewComments, setReviewComments] = useState('');
  const [loading, setLoading] = useState(true);
  const [submittingReview, setSubmittingReview] = useState(false);

  useEffect(() => {
    loadApprovalRequests();
  }, []);

  const loadApprovalRequests = async () => {
    try {
      setLoading(true);
      // TODO: Replace with actual API call
      const mockRequests: ApprovalRequest[] = [
        {
          id: '1',
          title: 'API Authentication Guide',
          doc_type: 'api',
          author: 'John Doe',
          status: 'pending',
          created_at: '2024-01-15T10:30:00Z',
          expires_at: '2024-01-18T10:30:00Z',
          quality_score: 85,
          reviewers: ['reviewer1', 'reviewer2'],
          reviews: []
        },
        {
          id: '2',
          title: 'User Onboarding Tutorial',
          doc_type: 'tutorial',
          author: 'Jane Smith',
          status: 'needs_review',
          created_at: '2024-01-14T15:45:00Z',
          quality_score: 78,
          reviewers: ['reviewer1'],
          reviews: [
            {
              reviewer_id: 'reviewer1',
              reviewer_role: 'technical_reviewer',
              decision: 'request_changes',
              comments: 'Please add more screenshots and clarify step 3.',
              reviewed_at: '2024-01-15T09:15:00Z'
            }
          ]
        },
        {
          id: '3',
          title: 'Database Schema Reference',
          doc_type: 'reference',
          author: 'Bob Johnson',
          status: 'approved',
          created_at: '2024-01-13T09:15:00Z',
          quality_score: 92,
          reviewers: ['reviewer1', 'reviewer2'],
          reviews: [
            {
              reviewer_id: 'reviewer1',
              reviewer_role: 'technical_reviewer',
              decision: 'approve',
              comments: 'Excellent documentation with clear examples.',
              reviewed_at: '2024-01-14T11:30:00Z'
            },
            {
              reviewer_id: 'reviewer2',
              reviewer_role: 'content_reviewer',
              decision: 'approve',
              comments: 'Well structured and easy to follow.',
              reviewed_at: '2024-01-14T14:20:00Z'
            }
          ]
        }
      ];
      setRequests(mockRequests);
    } catch (error) {
      console.error('Error loading approval requests:', error);
    } finally {
      setLoading(false);
    }
  };

  const submitReview = async () => {
    if (!selectedRequest || !reviewDecision) return;

    setSubmittingReview(true);
    try {
      // TODO: Replace with actual API call
      const response = await fetch(`/api/documentation/approvals/${selectedRequest.id}/review`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          decision: reviewDecision,
          comments: reviewComments,
          reviewer_role: 'technical_reviewer'
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to submit review');
      }

      // Reload requests
      await loadApprovalRequests();
      
      // Reset form
      setSelectedRequest(null);
      setReviewDecision('');
      setReviewComments('');
    } catch (error) {
      console.error('Error submitting review:', error);
    } finally {
      setSubmittingReview(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'approved':
        return <CheckCircle className="h-4 w-4 text-green-600" />;
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-600" />;
      case 'rejected':
        return <XCircle className="h-4 w-4 text-red-600" />;
      case 'needs_review':
        return <RotateCcw className="h-4 w-4 text-blue-600" />;
      default:
        return <Clock className="h-4 w-4 text-gray-600" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      approved: 'default',
      pending: 'secondary',
      rejected: 'destructive',
      needs_review: 'outline'
    };
    
    return (
      <Badge variant={variants[status] || 'outline'}>
        {status.replace('_', ' ').toUpperCase()}
      </Badge>
    );
  };

  const getDecisionIcon = (decision: string) => {
    switch (decision) {
      case 'approve':
        return <ThumbsUp className="h-4 w-4 text-green-600" />;
      case 'reject':
        return <ThumbsDown className="h-4 w-4 text-red-600" />;
      case 'request_changes':
        return <RotateCcw className="h-4 w-4 text-blue-600" />;
      default:
        return <MessageSquare className="h-4 w-4 text-gray-600" />;
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Approval Workflow</CardTitle>
          <CardDescription>
            Manage documentation review and approval process
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Document</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Author</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Quality Score</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Expires</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {requests.map((request) => (
                  <TableRow key={request.id}>
                    <TableCell>
                      <div className="flex items-center space-x-2">
                        <FileText className="h-4 w-4 text-muted-foreground" />
                        <div>
                          <div className="font-medium">{request.title}</div>
                          <div className="text-sm text-muted-foreground">
                            {request.reviews.length} review(s)
                          </div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{request.doc_type}</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center space-x-2">
                        <User className="h-4 w-4 text-muted-foreground" />
                        <span>{request.author}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center space-x-2">
                        {getStatusIcon(request.status)}
                        {getStatusBadge(request.status)}
                      </div>
                    </TableCell>
                    <TableCell>
                      {request.quality_score ? (
                        <span className="font-medium">
                          {request.quality_score}%
                        </span>
                      ) : (
                        <span className="text-muted-foreground">N/A</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center space-x-1 text-sm text-muted-foreground">
                        <Calendar className="h-3 w-3" />
                        <span>{new Date(request.created_at).toLocaleDateString()}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      {request.expires_at ? (
                        <div className="text-sm text-muted-foreground">
                          {new Date(request.expires_at).toLocaleDateString()}
                        </div>
                      ) : (
                        <span className="text-muted-foreground">No expiry</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center space-x-2">
                        <Dialog>
                          <DialogTrigger asChild>
                            <Button 
                              variant="outline" 
                              size="sm"
                              onClick={() => setSelectedRequest(request)}
                            >
                              <Eye className="h-4 w-4 mr-1" />
                              View
                            </Button>
                          </DialogTrigger>
                          <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
                            <DialogHeader>
                              <DialogTitle>{request.title}</DialogTitle>
                              <DialogDescription>
                                Review and approve documentation
                              </DialogDescription>
                            </DialogHeader>

                            <div className="space-y-6">
                              {/* Request Details */}
                              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <div>
                                  <Label className="text-sm font-medium">Type</Label>
                                  <div className="mt-1">
                                    <Badge variant="outline">{request.doc_type}</Badge>
                                  </div>
                                </div>
                                <div>
                                  <Label className="text-sm font-medium">Author</Label>
                                  <div className="mt-1 text-sm">{request.author}</div>
                                </div>
                                <div>
                                  <Label className="text-sm font-medium">Status</Label>
                                  <div className="mt-1">{getStatusBadge(request.status)}</div>
                                </div>
                                <div>
                                  <Label className="text-sm font-medium">Quality Score</Label>
                                  <div className="mt-1 text-sm font-medium">
                                    {request.quality_score}%
                                  </div>
                                </div>
                              </div>

                              {/* Existing Reviews */}
                              {request.reviews.length > 0 && (
                                <div>
                                  <Label className="text-sm font-medium mb-3 block">Previous Reviews</Label>
                                  <div className="space-y-3">
                                    {request.reviews.map((review, index) => (
                                      <div key={index} className="border rounded-lg p-4">
                                        <div className="flex items-center justify-between mb-2">
                                          <div className="flex items-center space-x-2">
                                            {getDecisionIcon(review.decision)}
                                            <span className="font-medium">{review.reviewer_id}</span>
                                            <Badge variant="outline" className="text-xs">
                                              {review.reviewer_role.replace('_', ' ')}
                                            </Badge>
                                          </div>
                                          <span className="text-sm text-muted-foreground">
                                            {new Date(review.reviewed_at).toLocaleDateString()}
                                          </span>
                                        </div>
                                        <div className="text-sm">
                                          <span className="font-medium">Decision: </span>
                                          <span className="capitalize">
                                            {review.decision.replace('_', ' ')}
                                          </span>
                                        </div>
                                        {review.comments && (
                                          <div className="mt-2 text-sm text-muted-foreground">
                                            {review.comments}
                                          </div>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Review Form */}
                              {request.status === 'pending' || request.status === 'needs_review' ? (
                                <div className="space-y-4 border-t pt-4">
                                  <Label className="text-sm font-medium">Submit Review</Label>
                                  
                                  <div className="space-y-2">
                                    <Label htmlFor="decision">Decision</Label>
                                    <Select value={reviewDecision} onValueChange={setReviewDecision}>
                                      <SelectTrigger>
                                        <SelectValue placeholder="Select your decision" />
                                      </SelectTrigger>
                                      <SelectContent>
                                        <SelectItem value="approve">Approve</SelectItem>
                                        <SelectItem value="request_changes">Request Changes</SelectItem>
                                        <SelectItem value="reject">Reject</SelectItem>
                                      </SelectContent>
                                    </Select>
                                  </div>

                                  <div className="space-y-2">
                                    <Label htmlFor="comments">Comments</Label>
                                    <Textarea
                                      id="comments"
                                      placeholder="Add your review comments..."
                                      value={reviewComments}
                                      onChange={(e) => setReviewComments(e.target.value)}
                                      rows={4}
                                    />
                                  </div>
                                </div>
                              ) : null}
                            </div>

                            <DialogFooter>
                              {(request.status === 'pending' || request.status === 'needs_review') && (
                                <Button 
                                  onClick={submitReview}
                                  disabled={!reviewDecision || submittingReview}
                                >
                                  {submittingReview ? (
                                    <>
                                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                                      Submitting...
                                    </>
                                  ) : (
                                    <>
                                      <Send className="mr-2 h-4 w-4" />
                                      Submit Review
                                    </>
                                  )}
                                </Button>
                              )}
                            </DialogFooter>
                          </DialogContent>
                        </Dialog>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {requests.length === 0 && (
            <div className="text-center py-8 text-muted-foreground">
              No approval requests found.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}