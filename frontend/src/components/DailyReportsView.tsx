import React, { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, FileText, Clock, Brain, MessageSquare } from 'lucide-react';
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { apiClient } from '@/services/api/client';

interface DailyReport {
  id: string;
  user_id: string;
  report_date: string;
  raw_text_input: string;
  clarified_tasks_summary?: string;
  ai_analysis?: {
    estimated_hours?: number;
    difficulty_level?: string;
    key_achievements?: string[];
    blockers_challenges?: string[];
    sentiment_score?: number;
    summary?: string;
  };
  final_estimated_hours?: number;
  commit_hours?: number;
  additional_hours?: number;
  deduplication_results?: any;
  created_at: string;
  updated_at: string;
}

interface PaginatedResponse {
  items: DailyReport[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

interface DailyReportsViewProps {
  userId: string;
  userName?: string;
}

export const DailyReportsView: React.FC<DailyReportsViewProps> = ({ userId, userName }) => {
  const [reports, setReports] = useState<DailyReport[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(5);
  const [totalPages, setTotalPages] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedReport, setSelectedReport] = useState<DailyReport | null>(null);

  useEffect(() => {
    fetchReports();
  }, [userId, currentPage]);

  const fetchReports = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await apiClient.get<PaginatedResponse>(
        `/api/reports/daily/user/${userId}?page=${currentPage}&page_size=${pageSize}`
      );
      
      if (response.error) {
        throw new Error(response.error);
      }
      
      if (response.data) {
        setReports(response.data.items);
        setTotalPages(response.data.total_pages);
        setHasNext(response.data.has_next);
        setHasPrevious(response.data.has_previous);
        
        // Auto-select first report if none selected
        if (!selectedReport && response.data.items.length > 0) {
          setSelectedReport(response.data.items[0]);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch daily reports');
      console.error('Error fetching daily reports:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setCurrentPage(newPage);
    }
  };

  const getSentimentBadge = (sentiment?: number) => {
    if (!sentiment) return null;
    if (sentiment >= 0.7) return <Badge className="bg-green-500">Positive</Badge>;
    if (sentiment >= 0.4) return <Badge className="bg-yellow-500">Neutral</Badge>;
    return <Badge className="bg-red-500">Challenging</Badge>;
  };

  const getDifficultyBadge = (difficulty?: string) => {
    if (!difficulty) return null;
    const colors = {
      low: 'bg-green-500',
      medium: 'bg-yellow-500',
      high: 'bg-red-500'
    };
    return <Badge className={colors[difficulty as keyof typeof colors] || 'bg-gray-500'}>{difficulty}</Badge>;
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Reports List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Daily Reports {userName && `for ${userName}`}
          </CardTitle>
          <CardDescription>Click on a report to view details</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading && <p className="text-center py-4">Loading reports...</p>}
          {error && <p className="text-destructive text-center py-4">{error}</p>}
          
          {!isLoading && !error && reports.length === 0 && (
            <p className="text-center py-4 text-muted-foreground">No reports found</p>
          )}
          
          {!isLoading && !error && reports.length > 0 && (
            <ScrollArea className="h-[400px]">
              <div className="space-y-3">
                {reports.map((report) => (
                  <Card
                    key={report.id}
                    className={`cursor-pointer transition-all hover:shadow-md ${
                      selectedReport?.id === report.id ? 'ring-2 ring-primary' : ''
                    }`}
                    onClick={() => setSelectedReport(report)}
                  >
                    <CardHeader className="pb-3">
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="font-semibold">{format(new Date(report.report_date), 'EEEE, MMMM d, yyyy')}</p>
                          <p className="text-sm text-muted-foreground">
                            Submitted {format(new Date(report.created_at), 'h:mm a')}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          {report.ai_analysis?.sentiment_score && getSentimentBadge(report.ai_analysis.sentiment_score)}
                          {report.ai_analysis?.difficulty_level && getDifficultyBadge(report.ai_analysis.difficulty_level)}
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <div className="flex items-center gap-4 text-sm">
                        <div className="flex items-center gap-1">
                          <Clock className="h-4 w-4 text-muted-foreground" />
                          <span>{report.final_estimated_hours?.toFixed(1) || '0'} hrs</span>
                        </div>
                        {report.ai_analysis?.key_achievements && (
                          <div className="flex items-center gap-1">
                            <Brain className="h-4 w-4 text-muted-foreground" />
                            <span>{report.ai_analysis.key_achievements.length} achievements</span>
                          </div>
                        )}
                      </div>
                      {report.ai_analysis?.summary && (
                        <p className="text-sm text-muted-foreground mt-2 line-clamp-2">
                          {report.ai_analysis.summary}
                        </p>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </ScrollArea>
          )}
        </CardContent>
        <CardFooter className="flex justify-between items-center">
          <div className="flex gap-1">
            <Button
              variant="outline"
              size="icon"
              onClick={() => handlePageChange(1)}
              disabled={!hasPrevious || isLoading}
            >
              <ChevronsLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={!hasPrevious || isLoading}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
          </div>
          
          <span className="text-sm text-muted-foreground">
            Page {currentPage} of {totalPages}
          </span>
          
          <div className="flex gap-1">
            <Button
              variant="outline"
              size="icon"
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={!hasNext || isLoading}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={() => handlePageChange(totalPages)}
              disabled={!hasNext || isLoading}
            >
              <ChevronsRight className="h-4 w-4" />
            </Button>
          </div>
        </CardFooter>
      </Card>

      {/* Report Details */}
      <Card>
        <CardHeader>
          <CardTitle>Report Details</CardTitle>
          <CardDescription>
            {selectedReport 
              ? format(new Date(selectedReport.report_date), 'EEEE, MMMM d, yyyy')
              : 'Select a report to view details'
            }
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!selectedReport ? (
            <p className="text-center py-8 text-muted-foreground">
              Select a report from the list to view its details
            </p>
          ) : (
            <ScrollArea className="h-[500px]">
              <div className="space-y-6">
                {/* Raw Input */}
                <div>
                  <h3 className="font-semibold mb-2 flex items-center gap-2">
                    <MessageSquare className="h-4 w-4" />
                    Employee Submission
                  </h3>
                  <Card className="bg-muted/50">
                    <CardContent className="pt-4">
                      <p className="whitespace-pre-wrap text-sm">{selectedReport.raw_text_input}</p>
                    </CardContent>
                  </Card>
                </div>

                <Separator />

                {/* AI Analysis */}
                {selectedReport.ai_analysis && (
                  <div>
                    <h3 className="font-semibold mb-2 flex items-center gap-2">
                      <Brain className="h-4 w-4" />
                      AI Analysis
                    </h3>
                    
                    <div className="space-y-4">
                      {/* Summary */}
                      {selectedReport.ai_analysis.summary && (
                        <div>
                          <p className="text-sm font-medium text-muted-foreground mb-1">Summary</p>
                          <p className="text-sm">{selectedReport.ai_analysis.summary}</p>
                        </div>
                      )}

                      {/* Time Breakdown */}
                      <div className="grid grid-cols-2 gap-4">
                        <Card>
                          <CardContent className="pt-4">
                            <p className="text-sm text-muted-foreground">Total Hours</p>
                            <p className="text-2xl font-bold">{selectedReport.final_estimated_hours?.toFixed(1) || '0'}</p>
                          </CardContent>
                        </Card>
                        
                        {selectedReport.commit_hours !== undefined && selectedReport.additional_hours !== undefined && (
                          <>
                            <Card>
                              <CardContent className="pt-4">
                                <p className="text-sm text-muted-foreground">Commit Hours</p>
                                <p className="text-2xl font-bold">{selectedReport.commit_hours.toFixed(1)}</p>
                              </CardContent>
                            </Card>
                            <Card>
                              <CardContent className="pt-4">
                                <p className="text-sm text-muted-foreground">Additional Hours</p>
                                <p className="text-2xl font-bold">{selectedReport.additional_hours.toFixed(1)}</p>
                              </CardContent>
                            </Card>
                            <Card>
                              <CardContent className="pt-4">
                                <p className="text-sm text-muted-foreground">Difficulty</p>
                                <p className="text-lg font-semibold capitalize">
                                  {selectedReport.ai_analysis.difficulty_level || 'Unknown'}
                                </p>
                              </CardContent>
                            </Card>
                          </>
                        )}
                      </div>

                      {/* Key Achievements */}
                      {selectedReport.ai_analysis.key_achievements && selectedReport.ai_analysis.key_achievements.length > 0 && (
                        <div>
                          <p className="text-sm font-medium text-muted-foreground mb-2">Key Achievements</p>
                          <ul className="list-disc list-inside space-y-1">
                            {selectedReport.ai_analysis.key_achievements.map((achievement, idx) => (
                              <li key={idx} className="text-sm">{achievement}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Blockers & Challenges */}
                      {selectedReport.ai_analysis.blockers_challenges && selectedReport.ai_analysis.blockers_challenges.length > 0 && (
                        <div>
                          <p className="text-sm font-medium text-muted-foreground mb-2">Blockers & Challenges</p>
                          <ul className="list-disc list-inside space-y-1">
                            {selectedReport.ai_analysis.blockers_challenges.map((blocker, idx) => (
                              <li key={idx} className="text-sm text-destructive">{blocker}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Deduplication Results */}
                {selectedReport.deduplication_results && (
                  <div>
                    <Separator className="my-4" />
                    <h3 className="font-semibold mb-2">Deduplication Analysis</h3>
                    <p className="text-sm text-muted-foreground">
                      Work items were analyzed to prevent double-counting between commits and EOD report
                    </p>
                  </div>
                )}
              </div>
            </ScrollArea>
          )}
        </CardContent>
      </Card>
    </div>
  );
};