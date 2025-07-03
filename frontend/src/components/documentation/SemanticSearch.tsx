import React, { useState, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { 
  Search, 
  FileText, 
  Code,
  BookOpen,
  TrendingUp,
  AlertCircle,
  Loader2,
  ChevronRight,
  ExternalLink,
  GitBranch,
  FolderOpen,
  CheckCircle,
  XCircle
} from 'lucide-react';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { useToast } from '@/components/ui/use-toast';
import { useDebounce } from '@/hooks/useDebounce';

interface SearchResult {
  id: string;
  title: string;
  content: string;
  type: string;
  repository: string;
  file_path: string;
  similarity: number;
  metadata: any;
  related_code?: Array<{
    file_path: string;
    module: string;
    classes: string[];
    functions: string[];
    similarity: number;
  }>;
}

interface DocumentationGap {
  file_path: string;
  module?: string;
  classes: number;
  functions: number;
  complexity: number;
}

interface CoverageInfo {
  repository: string;
  total_files: number;
  documented_files: number;
  undocumented_files: number;
  coverage_percentage: number;
  quality_score: number;
  recommendations: Array<{
    type: string;
    message: string;
    priority: string;
  }>;
}

export function SemanticSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [gaps, setGaps] = useState<DocumentationGap[]>([]);
  const [coverage, setCoverage] = useState<CoverageInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('search');
  const [selectedRepository, setSelectedRepository] = useState<string>('');
  const { toast } = useToast();
  
  const debouncedQuery = useDebounce(query, 500);

  const handleSearch = useCallback(async () => {
    if (!debouncedQuery.trim()) return;
    
    setLoading(true);
    try {
      const response = await fetch('/api/v1/search/documents', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          query: debouncedQuery,
          repository: selectedRepository || undefined,
          limit: 20,
          include_context: true
        })
      });

      if (!response.ok) throw new Error('Search failed');

      const data = await response.json();
      setResults(data.results);
    } catch (error) {
      toast({
        title: 'Search Error',
        description: 'Failed to search documentation',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  }, [debouncedQuery, selectedRepository, toast]);

  const analyzeGaps = async (repository: string) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/v1/search/gaps/${repository}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) throw new Error('Analysis failed');

      const data = await response.json();
      setGaps(data.undocumented_files);
      
      // Also fetch coverage
      const coverageResponse = await fetch(`/api/v1/search/coverage/${repository}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (coverageResponse.ok) {
        const coverageData = await coverageResponse.json();
        setCoverage(coverageData);
      }
    } catch (error) {
      toast({
        title: 'Analysis Error',
        description: 'Failed to analyze documentation gaps',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'text-green-600';
    if (score >= 0.6) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high': return 'destructive';
      case 'medium': return 'secondary';
      default: return 'outline';
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Semantic Documentation Search</CardTitle>
          <CardDescription>
            Use AI-powered search to find relevant documentation and discover gaps
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="search">
                <Search className="h-4 w-4 mr-2" />
                Search
              </TabsTrigger>
              <TabsTrigger value="gaps">
                <AlertCircle className="h-4 w-4 mr-2" />
                Gaps Analysis
              </TabsTrigger>
              <TabsTrigger value="insights">
                <TrendingUp className="h-4 w-4 mr-2" />
                Insights
              </TabsTrigger>
            </TabsList>

            <TabsContent value="search" className="space-y-4">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
                  <Input
                    placeholder="Search documentation using natural language..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                    className="pl-10"
                  />
                </div>
                <Button onClick={handleSearch} disabled={loading}>
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Search'}
                </Button>
              </div>

              {results.length > 0 && (
                <ScrollArea className="h-[600px]">
                  <div className="space-y-4">
                    {results.map((result) => (
                      <Card key={result.id} className="cursor-pointer hover:shadow-md transition-shadow">
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex-1">
                              <h3 className="font-semibold flex items-center gap-2">
                                <FileText className="h-4 w-4" />
                                {result.title}
                              </h3>
                              <div className="flex items-center gap-2 text-sm text-muted-foreground mt-1">
                                <GitBranch className="h-3 w-3" />
                                {result.repository}
                                {result.file_path && (
                                  <>
                                    <span>•</span>
                                    <span>{result.file_path}</span>
                                  </>
                                )}
                              </div>
                            </div>
                            <Badge variant="outline" className={getScoreColor(result.similarity)}>
                              {(result.similarity * 100).toFixed(0)}% match
                            </Badge>
                          </div>
                          
                          <p className="text-sm text-muted-foreground line-clamp-3 mb-3">
                            {result.content}
                          </p>

                          {result.related_code && result.related_code.length > 0 && (
                            <Collapsible>
                              <CollapsibleTrigger className="flex items-center gap-2 text-sm text-primary hover:underline">
                                <Code className="h-3 w-3" />
                                Related code ({result.related_code.length} files)
                                <ChevronRight className="h-3 w-3" />
                              </CollapsibleTrigger>
                              <CollapsibleContent className="mt-2">
                                <div className="pl-4 space-y-1">
                                  {result.related_code.map((code, idx) => (
                                    <div key={idx} className="text-xs flex items-center gap-2">
                                      <FolderOpen className="h-3 w-3" />
                                      <span className="font-mono">{code.file_path}</span>
                                      <Badge variant="outline" className="text-xs">
                                        {(code.similarity * 100).toFixed(0)}%
                                      </Badge>
                                    </div>
                                  ))}
                                </div>
                              </CollapsibleContent>
                            </Collapsible>
                          )}
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </ScrollArea>
              )}

              {debouncedQuery && results.length === 0 && !loading && (
                <div className="text-center py-8 text-muted-foreground">
                  <Search className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No results found for "{debouncedQuery}"</p>
                  <p className="text-sm mt-2">Try different keywords or check the repository filter</p>
                </div>
              )}
            </TabsContent>

            <TabsContent value="gaps" className="space-y-4">
              <div className="flex gap-2">
                <Input
                  placeholder="Enter repository name (e.g., owner/repo)"
                  value={selectedRepository}
                  onChange={(e) => setSelectedRepository(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && analyzeGaps(selectedRepository)}
                />
                <Button 
                  onClick={() => analyzeGaps(selectedRepository)} 
                  disabled={loading || !selectedRepository}
                >
                  Analyze
                </Button>
              </div>

              {coverage && (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-medium">Coverage</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">{coverage.coverage_percentage.toFixed(1)}%</div>
                      <Progress value={coverage.coverage_percentage} className="mt-2" />
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-medium">Quality Score</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className={`text-2xl font-bold ${getScoreColor(coverage.quality_score / 100)}`}>
                        {coverage.quality_score.toFixed(0)}
                      </div>
                      <p className="text-xs text-muted-foreground">out of 100</p>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-medium">Documented</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">{coverage.documented_files}</div>
                      <p className="text-xs text-muted-foreground">of {coverage.total_files} files</p>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-medium">Gaps Found</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold text-red-600">{coverage.undocumented_files}</div>
                      <p className="text-xs text-muted-foreground">files need docs</p>
                    </CardContent>
                  </Card>
                </div>
              )}

              {coverage?.recommendations && coverage.recommendations.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Recommendations</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {coverage.recommendations.map((rec, idx) => (
                        <div key={idx} className="flex items-start gap-2">
                          <Badge variant={getPriorityColor(rec.priority)} className="mt-0.5">
                            {rec.priority}
                          </Badge>
                          <p className="text-sm">{rec.message}</p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {gaps.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Undocumented Files</CardTitle>
                    <CardDescription>
                      Files that need documentation, sorted by complexity
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[400px]">
                      <div className="space-y-2">
                        {gaps.map((gap, idx) => (
                          <div key={idx} className="border rounded-lg p-3 hover:bg-muted/50">
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <p className="font-mono text-sm">{gap.file_path}</p>
                                {gap.module && (
                                  <p className="text-xs text-muted-foreground mt-1">
                                    Module: {gap.module}
                                  </p>
                                )}
                              </div>
                              <Badge variant="outline" className="ml-2">
                                Complexity: {gap.complexity.toFixed(1)}
                              </Badge>
                            </div>
                            <div className="flex gap-4 mt-2 text-xs text-muted-foreground">
                              <span>{gap.classes} classes</span>
                              <span>{gap.functions} functions</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </ScrollArea>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            <TabsContent value="insights" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Documentation Insights</CardTitle>
                  <CardDescription>
                    AI-powered insights about your documentation
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="text-center py-12 text-muted-foreground">
                    <BookOpen className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>Select a repository to generate insights</p>
                    <p className="text-sm mt-2">
                      We'll analyze patterns, suggest improvements, and identify connections
                    </p>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}