import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { 
  CheckCircle, 
  AlertCircle, 
  XCircle, 
  BarChart3,
  Lightbulb,
  FileText,
  Target,
  TrendingUp
} from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface QualityMetrics {
  overall_score: number;
  completeness_score: number;
  clarity_score: number;
  accuracy_score: number;
  consistency_score: number;
  grammar_score: number;
  structure_score: number;
  level: string;
  issues: string[];
  suggestions: string[];
  word_count: number;
  readability_score: number;
}

export function QualityValidation() {
  const [content, setContent] = useState('');
  const [docType, setDocType] = useState('general');
  const [metrics, setMetrics] = useState<QualityMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [improvements, setImprovements] = useState<string[]>([]);

  const validateQuality = async () => {
    if (!content.trim()) {
      return;
    }

    setLoading(true);
    try {
      // TODO: Replace with actual API call
      const response = await fetch('/api/documentation/quality/validate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          content,
          doc_type: docType,
          context: {}
        }),
      });

      if (!response.ok) {
        throw new Error('Quality validation failed');
      }

      const data = await response.json();
      setMetrics(data.metrics);
      setImprovements(data.improvement_suggestions);
    } catch (error) {
      console.error('Error validating quality:', error);
      // Mock data for demo
      setMetrics({
        overall_score: 78.5,
        completeness_score: 82,
        clarity_score: 75,
        accuracy_score: 85,
        consistency_score: 72,
        grammar_score: 88,
        structure_score: 70,
        level: 'good',
        issues: [
          'Missing code examples',
          'Some sections lack detail',
          'Inconsistent terminology'
        ],
        suggestions: [
          'Add more code examples',
          'Expand the introduction section',
          'Use consistent terminology throughout'
        ],
        word_count: 342,
        readability_score: 68
      });
      setImprovements([
        'Add more detailed examples to improve clarity',
        'Consider breaking long paragraphs into smaller sections',
        'Use bullet points for lists instead of paragraph format'
      ]);
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-green-600';
    if (score >= 80) return 'text-blue-600';
    if (score >= 70) return 'text-yellow-600';
    if (score >= 60) return 'text-orange-600';
    return 'text-red-600';
  };

  const getQualityBadge = (level: string) => {
    const badges = {
      excellent: { variant: 'default', color: 'bg-green-500' },
      good: { variant: 'default', color: 'bg-blue-500' },
      fair: { variant: 'secondary', color: 'bg-yellow-500' },
      poor: { variant: 'destructive', color: 'bg-orange-500' },
      critical: { variant: 'destructive', color: 'bg-red-500' }
    };
    
    const badge = badges[level as keyof typeof badges] || badges.fair;
    
    return (
      <Badge variant={badge.variant as any}>
        {level.charAt(0).toUpperCase() + level.slice(1)}
      </Badge>
    );
  };

  return (
    <div className="space-y-6">
      {/* Quality Validation Form */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <BarChart3 className="h-5 w-5" />
            <span>Quality Validation</span>
          </CardTitle>
          <CardDescription>
            Analyze documentation quality and get improvement suggestions
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="doc-type">Document Type</Label>
            <Select value={docType} onValueChange={setDocType}>
              <SelectTrigger>
                <SelectValue placeholder="Select document type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="api">API Documentation</SelectItem>
                <SelectItem value="guide">User Guide</SelectItem>
                <SelectItem value="reference">Reference Manual</SelectItem>
                <SelectItem value="tutorial">Tutorial</SelectItem>
                <SelectItem value="general">General Documentation</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="content">Documentation Content</Label>
            <Textarea
              id="content"
              placeholder="Paste your documentation content here..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={8}
              className="min-h-[200px]"
            />
            <div className="text-sm text-muted-foreground">
              {content.split(/\s+/).filter(word => word.length > 0).length} words
            </div>
          </div>

          <Button 
            onClick={validateQuality} 
            disabled={!content.trim() || loading}
            className="w-full"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Analyzing Quality...
              </>
            ) : (
              <>
                <Target className="mr-2 h-4 w-4" />
                Validate Quality
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Quality Results */}
      {metrics && (
        <div className="space-y-6">
          {/* Overall Score */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Quality Assessment</span>
                {getQualityBadge(metrics.level)}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="text-center">
                  <div className={`text-4xl font-bold ${getScoreColor(metrics.overall_score)}`}>
                    {metrics.overall_score}%
                  </div>
                  <div className="text-sm text-muted-foreground">Overall Quality Score</div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div className="text-center space-y-1">
                    <div className="text-sm font-medium">Completeness</div>
                    <div className={`text-lg font-semibold ${getScoreColor(metrics.completeness_score)}`}>
                      {metrics.completeness_score}%
                    </div>
                    <Progress value={metrics.completeness_score} className="h-2" />
                  </div>

                  <div className="text-center space-y-1">
                    <div className="text-sm font-medium">Clarity</div>
                    <div className={`text-lg font-semibold ${getScoreColor(metrics.clarity_score)}`}>
                      {metrics.clarity_score}%
                    </div>
                    <Progress value={metrics.clarity_score} className="h-2" />
                  </div>

                  <div className="text-center space-y-1">
                    <div className="text-sm font-medium">Accuracy</div>
                    <div className={`text-lg font-semibold ${getScoreColor(metrics.accuracy_score)}`}>
                      {metrics.accuracy_score}%
                    </div>
                    <Progress value={metrics.accuracy_score} className="h-2" />
                  </div>

                  <div className="text-center space-y-1">
                    <div className="text-sm font-medium">Grammar</div>
                    <div className={`text-lg font-semibold ${getScoreColor(metrics.grammar_score)}`}>
                      {metrics.grammar_score}%
                    </div>
                    <Progress value={metrics.grammar_score} className="h-2" />
                  </div>

                  <div className="text-center space-y-1">
                    <div className="text-sm font-medium">Structure</div>
                    <div className={`text-lg font-semibold ${getScoreColor(metrics.structure_score)}`}>
                      {metrics.structure_score}%
                    </div>
                    <Progress value={metrics.structure_score} className="h-2" />
                  </div>

                  <div className="text-center space-y-1">
                    <div className="text-sm font-medium">Consistency</div>
                    <div className={`text-lg font-semibold ${getScoreColor(metrics.consistency_score)}`}>
                      {metrics.consistency_score}%
                    </div>
                    <Progress value={metrics.consistency_score} className="h-2" />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 pt-4 border-t">
                  <div className="text-center">
                    <div className="text-lg font-semibold">{metrics.word_count}</div>
                    <div className="text-sm text-muted-foreground">Words</div>
                  </div>
                  <div className="text-center">
                    <div className={`text-lg font-semibold ${getScoreColor(metrics.readability_score)}`}>
                      {metrics.readability_score}%
                    </div>
                    <div className="text-sm text-muted-foreground">Readability</div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Issues and Suggestions */}
          <div className="grid md:grid-cols-2 gap-6">
            {/* Issues */}
            {metrics.issues.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center space-x-2">
                    <AlertCircle className="h-5 w-5 text-orange-500" />
                    <span>Issues Found</span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {metrics.issues.map((issue, index) => (
                      <Alert key={index}>
                        <XCircle className="h-4 w-4" />
                        <AlertDescription>{issue}</AlertDescription>
                      </Alert>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Suggestions */}
            {metrics.suggestions.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center space-x-2">
                    <Lightbulb className="h-5 w-5 text-blue-500" />
                    <span>Suggestions</span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {metrics.suggestions.map((suggestion, index) => (
                      <Alert key={index}>
                        <CheckCircle className="h-4 w-4" />
                        <AlertDescription>{suggestion}</AlertDescription>
                      </Alert>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* AI-Powered Improvements */}
          {improvements.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <TrendingUp className="h-5 w-5 text-green-500" />
                  <span>AI-Powered Improvements</span>
                </CardTitle>
                <CardDescription>
                  Specific recommendations to enhance your documentation
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {improvements.map((improvement, index) => (
                    <div key={index} className="flex items-start space-x-3 p-3 bg-muted rounded-lg">
                      <div className="flex-shrink-0 w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm font-medium">
                        {index + 1}
                      </div>
                      <div className="flex-1 text-sm">{improvement}</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}