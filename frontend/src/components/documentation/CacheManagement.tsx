import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { 
  Settings, 
  Trash2, 
  RefreshCw, 
  BarChart3,
  TrendingUp,
  TrendingDown,
  Zap,
  Database,
  Clock,
  Activity
} from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface CacheStats {
  enabled: boolean;
  entries_count: number;
  max_entries: number;
  hits: number;
  misses: number;
  hit_rate_percent: number;
  evictions: number;
  default_ttl_seconds: number;
}

interface CacheEntry {
  key: string;
  created_at: string;
  expires_at: string;
  access_count: number;
  last_accessed?: string;
  cache_level: string;
  content_hash?: string;
}

interface PerformanceAnalysis {
  stats: CacheStats;
  recommendations: string[];
  status: 'healthy' | 'needs_attention';
}

export function CacheManagement() {
  const [stats, setStats] = useState<CacheStats | null>(null);
  const [entries, setEntries] = useState<CacheEntry[]>([]);
  const [analysis, setAnalysis] = useState<PerformanceAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [operationLoading, setOperationLoading] = useState(false);

  useEffect(() => {
    loadCacheData();
  }, []);

  const loadCacheData = async () => {
    try {
      setLoading(true);
      // TODO: Replace with actual API calls
      
      // Mock cache stats
      const mockStats: CacheStats = {
        enabled: true,
        entries_count: 234,
        max_entries: 1000,
        hits: 1542,
        misses: 398,
        hit_rate_percent: 79.5,
        evictions: 12,
        default_ttl_seconds: 3600
      };

      // Mock cache entries
      const mockEntries: CacheEntry[] = [
        {
          key: 'quality_validation:content_hash_123',
          created_at: '2024-01-15T10:30:00Z',
          expires_at: '2024-01-15T11:30:00Z',
          access_count: 5,
          last_accessed: '2024-01-15T10:45:00Z',
          cache_level: 'memory',
          content_hash: 'abc123'
        },
        {
          key: 'improvement_suggestions:content_hash_456',
          created_at: '2024-01-15T09:15:00Z',
          expires_at: '2024-01-15T10:15:00Z',
          access_count: 3,
          last_accessed: '2024-01-15T09:30:00Z',
          cache_level: 'memory',
          content_hash: 'def456'
        },
        {
          key: 'quality_template:api',
          created_at: '2024-01-15T08:00:00Z',
          expires_at: '2024-01-15T16:00:00Z',
          access_count: 15,
          last_accessed: '2024-01-15T10:30:00Z',
          cache_level: 'memory'
        }
      ];

      // Mock performance analysis
      const mockAnalysis: PerformanceAnalysis = {
        stats: mockStats,
        recommendations: [
          'Consider increasing cache TTL for quality templates',
          'Monitor memory usage as cache is at 23% capacity'
        ],
        status: 'healthy'
      };

      setStats(mockStats);
      setEntries(mockEntries);
      setAnalysis(mockAnalysis);
    } catch (error) {
      console.error('Error loading cache data:', error);
    } finally {
      setLoading(false);
    }
  };

  const clearCache = async () => {
    try {
      setOperationLoading(true);
      // TODO: Replace with actual API call
      const response = await fetch('/api/documentation/cache', {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to clear cache');
      }

      await loadCacheData();
    } catch (error) {
      console.error('Error clearing cache:', error);
    } finally {
      setOperationLoading(false);
    }
  };

  const invalidateOperation = async (operation: string) => {
    try {
      setOperationLoading(true);
      // TODO: Replace with actual API call
      const response = await fetch(`/api/documentation/cache/${operation}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to invalidate cache');
      }

      await loadCacheData();
    } catch (error) {
      console.error('Error invalidating cache:', error);
    } finally {
      setOperationLoading(false);
    }
  };

  const warmupCache = async () => {
    try {
      setOperationLoading(true);
      // TODO: Replace with actual API call
      const response = await fetch('/api/documentation/cache/warmup', {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to warm up cache');
      }

      await loadCacheData();
    } catch (error) {
      console.error('Error warming up cache:', error);
    } finally {
      setOperationLoading(false);
    }
  };

  const getUsagePercentage = () => {
    if (!stats) return 0;
    return (stats.entries_count / stats.max_entries) * 100;
  };

  const getOperationFromKey = (key: string) => {
    return key.split(':')[0];
  };

  const formatTTL = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    return `${Math.floor(seconds / 3600)}h`;
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

  if (!stats) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-center text-muted-foreground">
            Failed to load cache data
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Cache Statistics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Hit Rate</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {stats.hit_rate_percent}%
            </div>
            <p className="text-xs text-muted-foreground">
              {stats.hits} hits, {stats.misses} misses
            </p>
            <Progress value={stats.hit_rate_percent} className="mt-2" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cache Usage</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats.entries_count}
            </div>
            <p className="text-xs text-muted-foreground">
              of {stats.max_entries} max entries
            </p>
            <Progress value={getUsagePercentage()} className="mt-2" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Evictions</CardTitle>
            <TrendingDown className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats.evictions}
            </div>
            <p className="text-xs text-muted-foreground">
              Entries removed
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">TTL</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatTTL(stats.default_ttl_seconds)}
            </div>
            <p className="text-xs text-muted-foreground">
              Default time to live
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Performance Analysis */}
      {analysis && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Activity className="h-5 w-5" />
              <span>Performance Analysis</span>
              <Badge variant={analysis.status === 'healthy' ? 'default' : 'destructive'}>
                {analysis.status === 'healthy' ? 'Healthy' : 'Needs Attention'}
              </Badge>
            </CardTitle>
            <CardDescription>
              Cache performance insights and recommendations
            </CardDescription>
          </CardHeader>
          <CardContent>
            {analysis.recommendations.length > 0 ? (
              <div className="space-y-2">
                {analysis.recommendations.map((recommendation, index) => (
                  <Alert key={index}>
                    <BarChart3 className="h-4 w-4" />
                    <AlertDescription>{recommendation}</AlertDescription>
                  </Alert>
                ))}
              </div>
            ) : (
              <Alert>
                <BarChart3 className="h-4 w-4" />
                <AlertTitle>All Good!</AlertTitle>
                <AlertDescription>
                  Cache is performing optimally with no recommendations at this time.
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {/* Cache Management Actions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Settings className="h-5 w-5" />
            <span>Cache Management</span>
          </CardTitle>
          <CardDescription>
            Manage cache operations and optimization
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <Button 
              onClick={warmupCache}
              disabled={operationLoading}
            >
              <Zap className="mr-2 h-4 w-4" />
              Warm Up Cache
            </Button>
            
            <Button 
              variant="outline"
              onClick={() => invalidateOperation('quality_validation')}
              disabled={operationLoading}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Clear Quality Cache
            </Button>

            <Button 
              variant="outline"
              onClick={() => invalidateOperation('improvement_suggestions')}
              disabled={operationLoading}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Clear Suggestions Cache
            </Button>

            <Button 
              variant="destructive"
              onClick={clearCache}
              disabled={operationLoading}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Clear All Cache
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Cache Entries */}
      <Card>
        <CardHeader>
          <CardTitle>Cache Entries</CardTitle>
          <CardDescription>
            Current cached items and their statistics
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Operation</TableHead>
                  <TableHead>Key</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Expires</TableHead>
                  <TableHead>Access Count</TableHead>
                  <TableHead>Last Accessed</TableHead>
                  <TableHead>Level</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.map((entry, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      <Badge variant="outline">
                        {getOperationFromKey(entry.key)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="font-mono text-xs max-w-xs truncate">
                        {entry.key}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm text-muted-foreground">
                        {new Date(entry.created_at).toLocaleString()}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm text-muted-foreground">
                        {new Date(entry.expires_at).toLocaleString()}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-center">
                        <span className="font-medium">{entry.access_count}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm text-muted-foreground">
                        {entry.last_accessed 
                          ? new Date(entry.last_accessed).toLocaleString()
                          : 'Never'
                        }
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="capitalize">
                        {entry.cache_level}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {entries.length === 0 && (
            <div className="text-center py-8 text-muted-foreground">
              No cache entries found.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}