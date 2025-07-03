import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { 
  FileText, 
  CheckCircle, 
  Clock, 
  AlertCircle, 
  GitBranch,
  BarChart3,
  Settings,
  Plus,
  Search,
  Filter
} from 'lucide-react';

// Import documentation management components
import { QualityValidation } from '@/components/documentation/QualityValidation';
import { ApprovalWorkflow } from '@/components/documentation/ApprovalWorkflow';
import { ApprovalQueue } from '@/components/documentation/ApprovalQueue';
import { VersionControl } from '@/components/documentation/VersionControl';
import { CacheManagement } from '@/components/documentation/CacheManagement';
import { DocumentationOverview } from '@/components/documentation/DocumentationOverview';
import { SemanticSearch } from '@/components/documentation/SemanticSearch';

export default function DocumentationPage() {
  const [activeTab, setActiveTab] = useState('overview');
  const [stats, setStats] = useState({
    totalDocuments: 0,
    pendingApprovals: 0,
    qualityScore: 0,
    cacheHitRate: 0
  });

  useEffect(() => {
    // Load dashboard statistics
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      // TODO: Fetch real stats from API
      setStats({
        totalDocuments: 42,
        pendingApprovals: 3,
        qualityScore: 85.2,
        cacheHitRate: 78.5
      });
    } catch (error) {
      console.error('Error loading documentation stats:', error);
    }
  };

  return (
    <div className="flex-1 space-y-6 p-8 pt-6">
      {/* Header */}
      <div className="flex items-center justify-between space-y-2">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Documentation Management</h2>
          <p className="text-muted-foreground">
            Manage documentation quality, approvals, and version control
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            New Document
          </Button>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Documents</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalDocuments}</div>
            <p className="text-xs text-muted-foreground">
              +2 from last week
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending Approvals</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.pendingApprovals}</div>
            <p className="text-xs text-muted-foreground">
              Awaiting review
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Quality Score</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.qualityScore}%</div>
            <p className="text-xs text-muted-foreground">
              +2.1% from last month
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cache Hit Rate</CardTitle>
            <Settings className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.cacheHitRate}%</div>
            <p className="text-xs text-muted-foreground">
              Performance optimized
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-7">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="search">Search</TabsTrigger>
          <TabsTrigger value="agent-approvals">AI Updates</TabsTrigger>
          <TabsTrigger value="quality">Quality</TabsTrigger>
          <TabsTrigger value="approvals">Approvals</TabsTrigger>
          <TabsTrigger value="versions">Versions</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <DocumentationOverview />
        </TabsContent>

        <TabsContent value="search" className="space-y-4">
          <SemanticSearch />
        </TabsContent>

        <TabsContent value="agent-approvals" className="space-y-4">
          <ApprovalQueue />
        </TabsContent>

        <TabsContent value="quality" className="space-y-4">
          <QualityValidation />
        </TabsContent>

        <TabsContent value="approvals" className="space-y-4">
          <ApprovalWorkflow />
        </TabsContent>

        <TabsContent value="versions" className="space-y-4">
          <VersionControl />
        </TabsContent>

        <TabsContent value="performance" className="space-y-4">
          <CacheManagement />
        </TabsContent>
      </Tabs>
    </div>
  );
}