import React, { useEffect, useMemo, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { FileText, GitBranch, GitCommit, RefreshCw, Search, Diff } from 'lucide-react'

type PRItem = {
  number: number
  title: string
  state: string
  html_url: string
  head: { label?: string; ref?: string; sha?: string }
  base: { label?: string; ref?: string; sha?: string }
  updated_at?: string
}

type TreeItem = { path: string; type: string; size?: number }

export default function DocsRepoViewer() {
  const defaultRepo = (import.meta as any).env?.VITE_DOCS_REPO || ''
  const [ownerRepo, setOwnerRepo] = useState(defaultRepo)
  const [prs, setPrs] = useState<PRItem[]>([])
  const [prNumber, setPrNumber] = useState<number | null>(null)
  const [tree, setTree] = useState<TreeItem[]>([])
  const [filter, setFilter] = useState('')
  const [activeTab, setActiveTab] = useState('render')
  const [selectedPath, setSelectedPath] = useState<string>('')
  const [fileContent, setFileContent] = useState<string>('')
  const [diff, setDiff] = useState<string>('')
  const [loading, setLoading] = useState(false)

  const [owner, repo] = useMemo(() => {
    const parts = ownerRepo.split('/')
    return parts.length === 2 ? parts : ['', '']
  }, [ownerRepo])

  const loadPRs = async (state: 'open' | 'closed' | 'all' = 'open') => {
    if (!owner || !repo) return
    setLoading(true)
    try {
      const resp = await fetch(`/api/v1/repos/${owner}/${repo}/prs?state=${state}`)
      const data = await resp.json()
      setPrs(data.items || [])
      if (!prNumber && data.items?.length) setPrNumber(data.items[0].number)
    } finally {
      setLoading(false)
    }
  }

  const loadTree = async () => {
    if (!owner || !repo || !prNumber) return
    setLoading(true)
    try {
      const resp = await fetch(`/api/v1/docs/${owner}/${repo}/${prNumber}/tree`)
      const data = await resp.json()
      setTree((data.files || []).filter((f: TreeItem) => f.type === 'blob'))
    } finally {
      setLoading(false)
    }
  }

  const loadFile = async (path: string) => {
    if (!owner || !repo || !prNumber) return
    setLoading(true)
    try {
      const resp = await fetch(`/api/v1/docs/${owner}/${repo}/${prNumber}/file?path=${encodeURIComponent(path)}`)
      const data = await resp.json()
      setFileContent(data.content || '')
      setSelectedPath(path)
    } finally {
      setLoading(false)
    }
  }

  const loadDiff = async () => {
    if (!owner || !repo || !prNumber) return
    setLoading(true)
    try {
      const resp = await fetch(`/api/v1/diff/${owner}/${repo}/${prNumber}`)
      const data = await resp.json()
      setDiff(data.diff || '')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (owner && repo) loadPRs('open')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [owner, repo])

  useEffect(() => {
    if (prNumber) {
      loadTree()
      loadDiff()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prNumber])

  const filteredTree = tree.filter((f) => !filter || f.path.toLowerCase().includes(filter.toLowerCase()))

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div className="space-y-1">
          <CardTitle>Docs Repo Viewer</CardTitle>
          <div className="flex gap-2 items-center">
            <Input
              placeholder="owner/repo"
              value={ownerRepo}
              onChange={(e) => setOwnerRepo(e.target.value)}
              className="w-64"
            />
            <Button variant="outline" onClick={() => loadPRs('open')} disabled={!owner || !repo || loading}>
              <RefreshCw className="h-4 w-4 mr-1" /> Refresh PRs
            </Button>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Select value={prNumber ? String(prNumber) : undefined} onValueChange={(v) => setPrNumber(Number(v))}>
            <SelectTrigger className="w-72">
              <SelectValue placeholder="Select Pull Request" />
            </SelectTrigger>
            <SelectContent>
              {prs.map((pr) => (
                <SelectItem key={pr.number} value={String(pr.number)}>
                  #{pr.number} {pr.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-4 border rounded-md">
            <div className="p-3 flex items-center gap-2">
              <Search className="h-4 w-4" />
              <Input placeholder="Filter files..." value={filter} onChange={(e) => setFilter(e.target.value)} />
            </div>
            <ScrollArea className="h-[540px]">
              <div className="px-3 pb-3 space-y-1">
                {filteredTree.map((f) => (
                  <button
                    key={f.path}
                    onClick={() => loadFile(f.path)}
                    className={`w-full text-left px-2 py-1 rounded hover:bg-muted ${selectedPath === f.path ? 'bg-muted' : ''}`}
                  >
                    <div className="flex items-center gap-2 text-sm">
                      <FileText className="h-3.5 w-3.5" />
                      <span className="truncate">{f.path}</span>
                    </div>
                  </button>
                ))}
                {filteredTree.length === 0 && (
                  <div className="text-muted-foreground text-sm px-2 py-2">No files found</div>
                )}
              </div>
            </ScrollArea>
          </div>
          <div className="col-span-8">
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList>
                <TabsTrigger value="render"><FileText className="h-4 w-4 mr-1" /> Rendered</TabsTrigger>
                <TabsTrigger value="source"><GitCommit className="h-4 w-4 mr-1" /> Source</TabsTrigger>
                <TabsTrigger value="diff"><Diff className="h-4 w-4 mr-1" /> Diff</TabsTrigger>
              </TabsList>
              <TabsContent value="render" className="mt-3">
                {/* Lightweight markdown render fallback (no external libs) */}
                <div className="prose prose-neutral dark:prose-invert max-w-none whitespace-pre-wrap">
                  {fileContent || 'Select a file to preview'}
                </div>
              </TabsContent>
              <TabsContent value="source" className="mt-3">
                <pre className="bg-muted p-3 rounded overflow-auto max-h-[540px]"><code>{fileContent}</code></pre>
              </TabsContent>
              <TabsContent value="diff" className="mt-3">
                <pre className="bg-muted p-3 rounded overflow-auto max-h-[540px]"><code>{diff}</code></pre>
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}


