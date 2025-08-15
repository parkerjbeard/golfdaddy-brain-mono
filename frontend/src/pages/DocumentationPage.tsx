import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Plus } from 'lucide-react';

// Import documentation management components
import { QualityValidation } from '@/components/documentation/QualityValidation';
import { ApprovalWorkflow } from '@/components/documentation/ApprovalWorkflow';
import { ApprovalQueue } from '@/components/documentation/ApprovalQueue';
import { VersionControl } from '@/components/documentation/VersionControl';
import { CacheManagement } from '@/components/documentation/CacheManagement';
import { DocumentationOverview } from '@/components/documentation/DocumentationOverview';
import { SemanticSearch } from '@/components/documentation/SemanticSearch';
import DocsRepoViewer from '@/components/documentation/DocsRepoViewer';
import api from '@/services/api/endpoints';

export default function DocumentationPage() {
  const [activeTab, setActiveTab] = useState('viewer');

  useEffect(() => {}, []);

  return (
    <div className="flex-1 space-y-6 p-8 pt-6">
      {/* Minimal Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold tracking-tight">Documentation</h2>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          New Document
        </Button>
      </div>

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="viewer">Docs Viewer</TabsTrigger>
          <TabsTrigger value="search">Search</TabsTrigger>
          <TabsTrigger value="agent-approvals">AI Updates</TabsTrigger>
          <TabsTrigger value="approvals">Approvals</TabsTrigger>
        </TabsList>

        <TabsContent value="viewer" className="space-y-4">
          <DocsRepoViewer />
        </TabsContent>

        <TabsContent value="search" className="space-y-4">
          <SemanticSearch />
        </TabsContent>

        <TabsContent value="agent-approvals" className="space-y-4">
          <ApprovalQueue />
        </TabsContent>

        <TabsContent value="approvals" className="space-y-4">
          <ApprovalWorkflow />
        </TabsContent>
      </Tabs>
    </div>
  );
}