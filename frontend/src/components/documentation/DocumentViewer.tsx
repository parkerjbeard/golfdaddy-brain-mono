import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  FileText, 
  Edit, 
  History,
  Download,
  Share2,
  Printer,
  ChevronLeft,
  ChevronRight,
  GitBranch,
  Clock,
  User,
  CheckCircle,
  AlertCircle,
  Code,
  List,
  Eye,
  Copy,
  ExternalLink,
  Bookmark,
  MessageSquare
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useToast } from '@/components/ui/use-toast';

interface Document {
  id: string;
  title: string;
  content: string;
  type: string;
  status: 'draft' | 'pending' | 'approved' | 'rejected';
  qualityScore: number;
  author: string;
  authorAvatar?: string;
  createdAt: string;
  lastModified: string;
  version: number;
  tags: string[];
  toc?: TocItem[];
  metadata?: {
    readTime?: string;
    wordCount?: number;
    lastReviewer?: string;
    repository?: string;
    commitHash?: string;
  };
}

interface TocItem {
  id: string;
  title: string;
  level: number;
}

interface DocumentViewerProps {
  documentId?: string;
  onBack?: () => void;
  onEdit?: (documentId: string) => void;
}

export function DocumentViewer({ documentId, onBack, onEdit }: DocumentViewerProps) {
  const [document, setDocument] = useState<Document | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('content');
  const [showToc, setShowToc] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    if (documentId) {
      loadDocument(documentId);
    }
  }, [documentId]);

  const loadDocument = async (id: string) => {
    try {
      setLoading(true);
      // TODO: Fetch from API
      const mockDocument: Document = {
        id: '1',
        title: 'GolfDaddy Brain API Documentation',
        content: `# GolfDaddy Brain API Documentation

## Overview

The GolfDaddy Brain API provides a comprehensive set of endpoints for managing documentation, commits, and AI-powered features.

## Authentication

All API requests require authentication using JWT tokens obtained from Supabase.

\`\`\`bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \\
  https://api.golfdaddy.ai/v1/docs
\`\`\`

## Endpoints

### Documentation Management

#### GET /api/v1/docs
Retrieve all documentation entries.

**Response:**
\`\`\`json
{
  "documents": [
    {
      "id": "123",
      "title": "API Guide",
      "content": "...",
      "status": "approved"
    }
  ]
}
\`\`\`

#### POST /api/v1/docs
Create a new documentation entry.

**Request Body:**
\`\`\`json
{
  "title": "New Guide",
  "content": "# New Guide\\n\\nContent here...",
  "type": "guide"
}
\`\`\`

### Commit Analysis

The commit analysis endpoints use AI to analyze code changes and provide insights.

#### POST /api/v1/commits/analyze
Analyze a specific commit for complexity and impact.

**Request Body:**
\`\`\`json
{
  "commitHash": "abc123",
  "repository": "golfdaddy/brain"
}
\`\`\`

## Rate Limiting

API requests are rate limited to:
- 1000 requests per hour for authenticated users
- 100 requests per hour for unauthenticated users

## Error Handling

The API uses standard HTTP status codes:

| Status Code | Description |
|------------|-------------|
| 200 | Success |
| 400 | Bad Request |
| 401 | Unauthorized |
| 404 | Not Found |
| 429 | Too Many Requests |
| 500 | Internal Server Error |

## SDK Support

Official SDKs are available for:
- JavaScript/TypeScript
- Python
- Go

## Webhooks

Configure webhooks to receive real-time updates about documentation changes.

### Webhook Events

- \`doc.created\` - New document created
- \`doc.updated\` - Document updated
- \`doc.approved\` - Document approved
- \`doc.rejected\` - Document rejected

## Best Practices

1. **Cache responses** when possible to reduce API calls
2. **Use pagination** for large result sets
3. **Handle rate limits** gracefully with exponential backoff
4. **Validate inputs** before sending requests

## Support

For API support, please contact:
- Email: api@golfdaddy.ai
- Discord: discord.gg/golfdaddy
- GitHub Issues: github.com/golfdaddy/brain/issues`,
        type: 'api',
        status: 'approved',
        qualityScore: 92,
        author: 'John Doe',
        createdAt: '2024-01-10T08:00:00Z',
        lastModified: '2024-01-15T10:30:00Z',
        version: 3,
        tags: ['api', 'documentation', 'guide'],
        metadata: {
          readTime: '8 min read',
          wordCount: 450,
          lastReviewer: 'Jane Smith',
          repository: 'golfdaddy/brain',
          commitHash: 'abc123def'
        }
      };
      
      // Generate TOC from content
      const tocItems = generateToc(mockDocument.content);
      mockDocument.toc = tocItems;
      
      setDocument(mockDocument);
    } catch (error) {
      console.error('Error loading document:', error);
      toast({
        title: 'Error',
        description: 'Failed to load document',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  const generateToc = (content: string): TocItem[] => {
    const headingRegex = /^(#{1,6})\s+(.+)$/gm;
    const toc: TocItem[] = [];
    let match;
    
    while ((match = headingRegex.exec(content)) !== null) {
      const level = match[1].length;
      const title = match[2];
      const id = title.toLowerCase().replace(/[^\w]+/g, '-');
      
      toc.push({ id, title, level });
    }
    
    return toc;
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast({
        title: 'Copied!',
        description: 'Content copied to clipboard',
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to copy to clipboard',
        variant: 'destructive'
      });
    }
  };

  const handleExport = (format: 'markdown' | 'pdf' | 'html') => {
    // TODO: Implement export functionality
    toast({
      title: 'Exporting...',
      description: `Exporting document as ${format.toUpperCase()}`,
    });
  };

  const scrollToSection = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!document) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-center">
            <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">Document not found</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-14 items-center px-4">
          <div className="flex items-center flex-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={onBack}
              className="mr-2"
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Back
            </Button>
            <Separator orientation="vertical" className="mx-2 h-6" />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem>
                  <BreadcrumbLink href="#">Documentation</BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  <BreadcrumbLink href="#">{document.type}</BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  <BreadcrumbPage>{document.title}</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
          
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowToc(!showToc)}
            >
              <List className="h-4 w-4" />
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm">
                  <Download className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => handleExport('markdown')}>
                  Export as Markdown
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleExport('pdf')}>
                  Export as PDF
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleExport('html')}>
                  Export as HTML
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button variant="ghost" size="sm">
              <Share2 className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="sm">
              <Printer className="h-4 w-4" />
            </Button>
            {onEdit && (
              <Button
                size="sm"
                onClick={() => onEdit(document.id)}
              >
                <Edit className="h-4 w-4 mr-1" />
                Edit
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex">
        {/* Table of Contents */}
        {showToc && document.toc && document.toc.length > 0 && (
          <aside className="w-64 border-r bg-muted/10">
            <ScrollArea className="h-full">
              <div className="p-4">
                <h3 className="font-semibold mb-4">Table of Contents</h3>
                <nav className="space-y-1">
                  {document.toc.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => scrollToSection(item.id)}
                      className={`block w-full text-left py-1 px-2 rounded-md text-sm hover:bg-muted transition-colors`}
                      style={{ paddingLeft: `${(item.level - 1) * 12 + 8}px` }}
                    >
                      {item.title}
                    </button>
                  ))}
                </nav>
              </div>
            </ScrollArea>
          </aside>
        )}

        {/* Document Content */}
        <div className="flex-1 overflow-auto">
          <div className="container max-w-4xl mx-auto py-8 px-6">
            {/* Document Header */}
            <div className="mb-8">
              <div className="flex items-center gap-2 mb-4">
                <Badge variant={document.status === 'approved' ? 'default' : 'secondary'}>
                  {document.status}
                </Badge>
                <Badge variant="outline">v{document.version}</Badge>
                {document.tags.map((tag) => (
                  <Badge key={tag} variant="outline">
                    {tag}
                  </Badge>
                ))}
              </div>
              
              <h1 className="text-4xl font-bold mb-4">{document.title}</h1>
              
              <div className="flex items-center gap-6 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  <User className="h-4 w-4" />
                  <span>{document.author}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  <span>{document.metadata?.readTime}</span>
                </div>
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  <span>{document.metadata?.wordCount} words</span>
                </div>
                {document.metadata?.repository && (
                  <div className="flex items-center gap-2">
                    <GitBranch className="h-4 w-4" />
                    <span>{document.metadata.repository}</span>
                  </div>
                )}
              </div>
            </div>

            <Separator className="mb-8" />

            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="mb-6">
                <TabsTrigger value="content">
                  <Eye className="h-4 w-4 mr-2" />
                  Content
                </TabsTrigger>
                <TabsTrigger value="source">
                  <Code className="h-4 w-4 mr-2" />
                  Source
                </TabsTrigger>
                <TabsTrigger value="history">
                  <History className="h-4 w-4 mr-2" />
                  History
                </TabsTrigger>
                <TabsTrigger value="comments">
                  <MessageSquare className="h-4 w-4 mr-2" />
                  Comments
                </TabsTrigger>
              </TabsList>

              <TabsContent value="content" className="prose prose-neutral dark:prose-invert max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h1: ({ children, ...props }) => (
                      <h1 id={String(children).toLowerCase().replace(/[^\w]+/g, '-')} {...props}>
                        {children}
                      </h1>
                    ),
                    h2: ({ children, ...props }) => (
                      <h2 id={String(children).toLowerCase().replace(/[^\w]+/g, '-')} {...props}>
                        {children}
                      </h2>
                    ),
                    h3: ({ children, ...props }) => (
                      <h3 id={String(children).toLowerCase().replace(/[^\w]+/g, '-')} {...props}>
                        {children}
                      </h3>
                    ),
                    code({ node, inline, className, children, ...props }) {
                      const match = /language-(\w+)/.exec(className || '');
                      return !inline && match ? (
                        <div className="relative">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="absolute right-2 top-2"
                            onClick={() => copyToClipboard(String(children).replace(/\n$/, ''))}
                          >
                            <Copy className="h-4 w-4" />
                          </Button>
                          <SyntaxHighlighter
                            style={oneDark}
                            language={match[1]}
                            PreTag="div"
                            {...props}
                          >
                            {String(children).replace(/\n$/, '')}
                          </SyntaxHighlighter>
                        </div>
                      ) : (
                        <code className={className} {...props}>
                          {children}
                        </code>
                      );
                    },
                  }}
                >
                  {document.content}
                </ReactMarkdown>
              </TabsContent>

              <TabsContent value="source">
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle>Markdown Source</CardTitle>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => copyToClipboard(document.content)}
                      >
                        <Copy className="h-4 w-4 mr-2" />
                        Copy
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <pre className="bg-muted p-4 rounded-lg overflow-auto">
                      <code>{document.content}</code>
                    </pre>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="history">
                <Card>
                  <CardHeader>
                    <CardTitle>Version History</CardTitle>
                    <CardDescription>
                      Track changes and updates to this document
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      <div className="flex items-start gap-4">
                        <div className="flex-shrink-0 w-2 h-2 mt-1.5 rounded-full bg-primary" />
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium">Version {document.version}</span>
                            <Badge variant="outline" className="text-xs">Current</Badge>
                          </div>
                          <p className="text-sm text-muted-foreground mb-1">
                            Updated by {document.metadata?.lastReviewer || document.author}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {new Date(document.lastModified).toLocaleString()}
                          </p>
                        </div>
                      </div>
                      {/* Add more version history items here */}
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="comments">
                <Card>
                  <CardHeader>
                    <CardTitle>Comments & Reviews</CardTitle>
                    <CardDescription>
                      Discussion and feedback about this document
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="text-center py-8 text-muted-foreground">
                      No comments yet. Be the first to leave feedback!
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </div>
    </div>
  );
}