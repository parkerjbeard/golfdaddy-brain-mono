import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { 
  GitBranch, 
  History, 
  RotateCcw, 
  Eye,
  FileText,
  User,
  Calendar,
  MessageSquare,
  ArrowRight,
  Diff
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
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

interface DocumentVersion {
  id: string;
  document_id: string;
  version_number: number;
  title: string;
  author_id: string;
  created_at: string;
  commit_message?: string;
  content_hash: string;
  word_count?: number;
}

interface DiffPreview {
  summary: {
    lines_added: number;
    lines_removed: number;
    lines_modified: number;
    total_changes: number;
  };
  format: string;
  diff: any[];
  created_at: string;
}

export function VersionControl() {
  const [documents, setDocuments] = useState<string[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<string>('');
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [selectedVersions, setSelectedVersions] = useState<{from: string, to: string}>({from: '', to: ''});
  const [diffPreview, setDiffPreview] = useState<DiffPreview | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadDocuments();
  }, []);

  useEffect(() => {
    if (selectedDocument) {
      loadVersions(selectedDocument);
    }
  }, [selectedDocument]);

  const loadDocuments = async () => {
    try {
      // TODO: Replace with actual API call
      setDocuments([
        'api-documentation',
        'user-guide',
        'installation-guide',
        'developer-reference'
      ]);
      
      // Set default selection
      if (documents.length === 0) {
        setSelectedDocument('api-documentation');
      }
    } catch (error) {
      console.error('Error loading documents:', error);
    }
  };

  const loadVersions = async (documentId: string) => {
    try {
      setLoading(true);
      // TODO: Replace with actual API call
      const mockVersions: DocumentVersion[] = [
        {
          id: 'v1',
          document_id: documentId,
          version_number: 3,
          title: 'API Documentation v3',
          author_id: 'john.doe',
          created_at: '2024-01-15T14:30:00Z',
          commit_message: 'Added authentication endpoints',
          content_hash: 'abc123',
          word_count: 1250
        },
        {
          id: 'v2',
          document_id: documentId,
          version_number: 2,
          title: 'API Documentation v2',
          author_id: 'jane.smith',
          created_at: '2024-01-10T09:15:00Z',
          commit_message: 'Updated error handling section',
          content_hash: 'def456',
          word_count: 1180
        },
        {
          id: 'v3',
          document_id: documentId,
          version_number: 1,
          title: 'API Documentation v1',
          author_id: 'bob.johnson',
          created_at: '2024-01-05T16:45:00Z',
          commit_message: 'Initial documentation',
          content_hash: 'ghi789',
          word_count: 850
        }
      ];
      setVersions(mockVersions);
    } catch (error) {
      console.error('Error loading versions:', error);
    } finally {
      setLoading(false);
    }
  };

  const generateDiff = async () => {
    if (!selectedVersions.from || !selectedVersions.to) return;

    try {
      setLoading(true);
      // TODO: Replace with actual API call
      const mockDiff: DiffPreview = {
        summary: {
          lines_added: 15,
          lines_removed: 8,
          lines_modified: 12,
          total_changes: 6
        },
        format: 'side_by_side',
        diff: [
          {
            old_line_num: 1,
            new_line_num: 1,
            old_content: '# API Documentation',
            new_content: '# API Documentation v2',
            type: 'modification'
          },
          {
            old_line_num: null,
            new_line_num: 2,
            old_content: '',
            new_content: '',
            type: 'unchanged'
          },
          {
            old_line_num: null,
            new_line_num: 3,
            old_content: '',
            new_content: '## Authentication',
            type: 'addition'
          },
          {
            old_line_num: null,
            new_line_num: 4,
            old_content: '',
            new_content: 'All API requests require authentication.',
            type: 'addition'
          }
        ],
        created_at: new Date().toISOString()
      };
      setDiffPreview(mockDiff);
    } catch (error) {
      console.error('Error generating diff:', error);
    } finally {
      setLoading(false);
    }
  };

  const rollbackToVersion = async (versionId: string) => {
    try {
      setLoading(true);
      // TODO: Replace with actual API call
      const response = await fetch(`/api/documentation/documents/${selectedDocument}/rollback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          target_version_id: versionId,
          reason: 'User initiated rollback'
        }),
      });

      if (!response.ok) {
        throw new Error('Rollback failed');
      }

      // Reload versions
      await loadVersions(selectedDocument);
      
      alert('Successfully rolled back to selected version');
    } catch (error) {
      console.error('Error rolling back:', error);
      alert('Rollback failed');
    } finally {
      setLoading(false);
    }
  };

  const getDiffTypeColor = (type: string) => {
    switch (type) {
      case 'addition':
        return 'bg-green-50 border-green-200';
      case 'deletion':
        return 'bg-red-50 border-red-200';
      case 'modification':
        return 'bg-blue-50 border-blue-200';
      default:
        return 'bg-gray-50 border-gray-200';
    }
  };

  const getDiffTypeLabel = (type: string) => {
    switch (type) {
      case 'addition':
        return 'Added';
      case 'deletion':
        return 'Removed';
      case 'modification':
        return 'Modified';
      default:
        return 'Unchanged';
    }
  };

  return (
    <div className="space-y-6">
      {/* Document Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <GitBranch className="h-5 w-5" />
            <span>Version Control</span>
          </CardTitle>
          <CardDescription>
            Track changes, compare versions, and manage rollbacks
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Select Document</label>
              <Select value={selectedDocument} onValueChange={setSelectedDocument}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose a document" />
                </SelectTrigger>
                <SelectContent>
                  {documents.map((doc) => (
                    <SelectItem key={doc} value={doc}>
                      {doc.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Version History */}
      {selectedDocument && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <History className="h-5 w-5" />
              <span>Version History</span>
            </CardTitle>
            <CardDescription>
              All versions of {selectedDocument.replace('-', ' ')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center h-32">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
              </div>
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Version</TableHead>
                      <TableHead>Title</TableHead>
                      <TableHead>Author</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Message</TableHead>
                      <TableHead>Changes</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {versions.map((version, index) => (
                      <TableRow key={version.id}>
                        <TableCell>
                          <div className="flex items-center space-x-2">
                            <Badge variant={index === 0 ? 'default' : 'outline'}>
                              v{version.version_number}
                            </Badge>
                            {index === 0 && (
                              <Badge variant="secondary" className="text-xs">
                                Latest
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center space-x-2">
                            <FileText className="h-4 w-4 text-muted-foreground" />
                            <span className="font-medium">{version.title}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center space-x-2">
                            <User className="h-4 w-4 text-muted-foreground" />
                            <span>{version.author_id}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center space-x-1 text-sm text-muted-foreground">
                            <Calendar className="h-3 w-3" />
                            <span>{new Date(version.created_at).toLocaleDateString()}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          {version.commit_message ? (
                            <div className="flex items-center space-x-2">
                              <MessageSquare className="h-4 w-4 text-muted-foreground" />
                              <span className="text-sm">{version.commit_message}</span>
                            </div>
                          ) : (
                            <span className="text-muted-foreground text-sm">No message</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {version.word_count && (
                            <span className="text-sm">{version.word_count} words</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center space-x-2">
                            <Button variant="outline" size="sm">
                              <Eye className="h-4 w-4 mr-1" />
                              View
                            </Button>
                            {index > 0 && (
                              <Dialog>
                                <DialogTrigger asChild>
                                  <Button variant="outline" size="sm">
                                    <RotateCcw className="h-4 w-4 mr-1" />
                                    Rollback
                                  </Button>
                                </DialogTrigger>
                                <DialogContent>
                                  <DialogHeader>
                                    <DialogTitle>Confirm Rollback</DialogTitle>
                                    <DialogDescription>
                                      Are you sure you want to rollback to version {version.version_number}? 
                                      This will create a new version with the content from this version.
                                    </DialogDescription>
                                  </DialogHeader>
                                  <div className="flex justify-end space-x-2">
                                    <Button variant="outline">Cancel</Button>
                                    <Button 
                                      onClick={() => rollbackToVersion(version.id)}
                                      disabled={loading}
                                    >
                                      Confirm Rollback
                                    </Button>
                                  </div>
                                </DialogContent>
                              </Dialog>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Version Comparison */}
      {versions.length >= 2 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Diff className="h-5 w-5" />
              <span>Compare Versions</span>
            </CardTitle>
            <CardDescription>
              Compare changes between different versions
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                <div className="space-y-2">
                  <label className="text-sm font-medium">From Version</label>
                  <Select 
                    value={selectedVersions.from} 
                    onValueChange={(value) => setSelectedVersions(prev => ({...prev, from: value}))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select version" />
                    </SelectTrigger>
                    <SelectContent>
                      {versions.map((version) => (
                        <SelectItem key={version.id} value={version.id}>
                          v{version.version_number} - {version.title}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex justify-center">
                  <ArrowRight className="h-6 w-6 text-muted-foreground" />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">To Version</label>
                  <Select 
                    value={selectedVersions.to} 
                    onValueChange={(value) => setSelectedVersions(prev => ({...prev, to: value}))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select version" />
                    </SelectTrigger>
                    <SelectContent>
                      {versions.map((version) => (
                        <SelectItem key={version.id} value={version.id}>
                          v{version.version_number} - {version.title}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <Button 
                onClick={generateDiff}
                disabled={!selectedVersions.from || !selectedVersions.to || loading}
                className="w-full"
              >
                {loading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Generating Diff...
                  </>
                ) : (
                  <>
                    <Diff className="mr-2 h-4 w-4" />
                    Compare Versions
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Diff Results */}
      {diffPreview && (
        <Card>
          <CardHeader>
            <CardTitle>Comparison Results</CardTitle>
            <CardDescription>
              Changes between selected versions
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Summary */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-3 bg-green-50 rounded-lg border border-green-200">
                  <div className="text-2xl font-bold text-green-600">
                    +{diffPreview.summary.lines_added}
                  </div>
                  <div className="text-sm text-green-600">Lines Added</div>
                </div>
                <div className="text-center p-3 bg-red-50 rounded-lg border border-red-200">
                  <div className="text-2xl font-bold text-red-600">
                    -{diffPreview.summary.lines_removed}
                  </div>
                  <div className="text-sm text-red-600">Lines Removed</div>
                </div>
                <div className="text-center p-3 bg-blue-50 rounded-lg border border-blue-200">
                  <div className="text-2xl font-bold text-blue-600">
                    {diffPreview.summary.lines_modified}
                  </div>
                  <div className="text-sm text-blue-600">Lines Modified</div>
                </div>
                <div className="text-center p-3 bg-gray-50 rounded-lg border border-gray-200">
                  <div className="text-2xl font-bold text-gray-600">
                    {diffPreview.summary.total_changes}
                  </div>
                  <div className="text-sm text-gray-600">Total Changes</div>
                </div>
              </div>

              {/* Diff Content */}
              <div className="space-y-2">
                <h4 className="font-medium">Changes</h4>
                <div className="border rounded-lg max-h-96 overflow-y-auto">
                  {diffPreview.diff.map((line, index) => (
                    <div
                      key={index}
                      className={`p-2 border-b text-sm ${getDiffTypeColor(line.type)}`}
                    >
                      <div className="flex items-center space-x-2 mb-1">
                        <Badge variant="outline" className="text-xs">
                          {getDiffTypeLabel(line.type)}
                        </Badge>
                        {line.old_line_num && (
                          <span className="text-xs text-muted-foreground">
                            Line {line.old_line_num}
                          </span>
                        )}
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {line.old_content && (
                          <div className="bg-red-50 p-2 rounded text-xs">
                            <span className="text-red-600 font-mono">- {line.old_content}</span>
                          </div>
                        )}
                        {line.new_content && (
                          <div className="bg-green-50 p-2 rounded text-xs">
                            <span className="text-green-600 font-mono">+ {line.new_content}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}