# Documentation Migration Guide: ClickUp to GolfDaddy Brain

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Migration Strategy](#migration-strategy)
4. [Phase 1: Content Extraction from ClickUp](#phase-1-content-extraction-from-clickup)
5. [Phase 2: LLM Processing](#phase-2-llm-processing)
6. [Phase 3: Repository Setup](#phase-3-repository-setup)
7. [Phase 4: Content Import & Organization](#phase-4-content-import--organization)
8. [Phase 5: Doc Agent Configuration](#phase-5-doc-agent-configuration)
9. [Phase 6: Validation & Go-Live](#phase-6-validation--go-live)
10. [Post-Migration](#post-migration)
11. [Required Scripts](#required-scripts)

## Overview

This guide walks through migrating your existing documentation from ClickUp to the GolfDaddy Brain repository system, where it will be managed by the doc agent for automated updates, approval workflows, and semantic search.

### Migration Flow
```
ClickUp Screenshots → LLM Processing → Markdown Files → 
Repository Organization → Doc Agent Integration → 
Embeddings & Search → Live Documentation System
```

### Expected Outcomes
- All documentation converted to version-controlled markdown
- Automated documentation updates via doc agent
- Semantic search capabilities
- Approval workflows through Slack
- Integration with code commits for automatic doc generation

## Prerequisites

### Access Requirements
- ClickUp workspace access with documentation
- GitHub repository with write permissions
- OpenAI API access (GPT-4 Vision for screenshot processing)
- Supabase database access
- Slack workspace (for approval workflows)

### Environment Variables
Create a `.env` file with:
```
OPENAI_API_KEY=
GITHUB_TOKEN=
GITHUB_APP_ID=
GITHUB_APP_PRIVATE_KEY=
GITHUB_APP_INSTALLATION_ID=
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
DATABASE_URL=
SLACK_BOT_TOKEN=
SLACK_DEFAULT_CHANNEL=
DOCS_REPOSITORY=owner/repo
FRONTEND_URL=
```

### Directory Structure to Create
```
docs/
├── api/                    # API documentation
├── guides/                 # User guides and tutorials
├── architecture/           # System architecture docs
├── processes/             # Business processes
├── reference/             # Reference materials
├── migration/             # Migration working directory
│   ├── screenshots/       # ClickUp screenshots
│   ├── extracted/         # LLM-extracted content
│   └── processed/         # Final markdown files
└── .meta/                 # Metadata and configuration
    ├── index.json         # Document index
    └── config.json        # Doc agent configuration
```

## Migration Strategy

### Approach: LLM-Based Screenshot Processing

We'll use screenshots of ClickUp documentation processed through GPT-4 Vision to:
1. Preserve visual context and formatting
2. Extract structured content
3. Generate proper markdown with frontmatter
4. Maintain relationships between documents

### Why This Approach
- **Handles complex layouts** - ClickUp's rich formatting is preserved
- **No API limitations** - Works with any ClickUp configuration
- **Visual verification** - Can review screenshots before/after
- **Flexible extraction** - LLM can understand context and structure

## Phase 1: Content Extraction from ClickUp

### Step 1.1: Document Inventory
1. Navigate to your ClickUp workspace
2. Create a spreadsheet listing all documentation:
   - Document title
   - URL
   - Category/folder
   - Priority (high/medium/low)
   - Dependencies (related docs)
   - Last updated date

### Step 1.2: Screenshot Capture Process

#### Manual Capture (Recommended for accuracy)
1. Open each document in ClickUp
2. Use full-page screenshot tools:
   - **Mac**: Cmd+Shift+5, select "Capture Entire Page"
   - **Windows**: Edge/Chrome DevTools → Cmd+Shift+P → "Capture full size screenshot"
   - **Cross-platform**: Browser extensions like GoFullPage

3. Naming convention: `[category]-[document-name]-[page-number].png`
   - Example: `api-authentication-guide-01.png`

4. Save to `docs/migration/screenshots/` with subdirectories:
   ```
   screenshots/
   ├── api/
   ├── guides/
   ├── architecture/
   └── processes/
   ```

#### Tips for Quality Screenshots
- Use consistent window width (1920px recommended)
- Ensure all expandable sections are open
- Capture code blocks completely
- Include comments and annotations
- Take multiple shots if document is very long

### Step 1.3: Metadata Collection
For each document, create a metadata file:
```json
{
  "source_url": "https://app.clickup.com/...",
  "title": "API Authentication Guide",
  "category": "api",
  "tags": ["authentication", "security", "api"],
  "related_docs": ["api-rate-limiting", "api-errors"],
  "last_updated": "2024-01-15",
  "author": "original_author_id",
  "priority": "high"
}
```

Save as `[document-name].meta.json` alongside screenshots.

## Phase 2: LLM Processing

### Step 2.1: Content Extraction Strategy

#### Prepare LLM Prompts
Create targeted prompts for different document types:

**For API Documentation:**
```
Analyze this API documentation screenshot and extract:
1. Endpoint name and HTTP method
2. Request/response schemas
3. Authentication requirements
4. Rate limiting information
5. Error codes and meanings
6. Code examples with language specified
7. Important notes or warnings

Format as structured markdown with proper code blocks.
```

**For Guides/Tutorials:**
```
Extract this tutorial content maintaining:
1. Step-by-step instructions in numbered lists
2. Prerequisites section
3. Code snippets with syntax highlighting
4. Tips and warnings in blockquotes
5. Related documentation links
6. Troubleshooting section if present
```

**For Architecture Documentation:**
```
Extract architectural documentation preserving:
1. System components and their relationships
2. Data flow descriptions
3. Technology stack details
4. Scaling considerations
5. Security boundaries
6. Diagram descriptions (describe visual diagrams in detail)
```

### Step 2.2: Processing Workflow

1. **Group screenshots** by document (multi-page docs)
2. **Process sequentially** to maintain context
3. **Extract structured content** using GPT-4 Vision
4. **Generate markdown** with proper frontmatter
5. **Save to** `docs/migration/extracted/`

### Step 2.3: Content Structure Template

Each processed document should follow this structure:

```markdown
---
title: Document Title
category: category-name
tags: [tag1, tag2, tag3]
version: 1.0.0
last_updated: 2024-01-20
migrated_from: clickup
original_url: https://app.clickup.com/...
related_docs: [doc1, doc2]
---

# Document Title

## Overview
Brief description of the document's purpose

## Prerequisites (if applicable)
- Requirement 1
- Requirement 2

## Main Content
[Extracted and formatted content]

## Code Examples (if applicable)
```language
// Code here
```

## Related Documentation
- [Link to related doc 1]
- [Link to related doc 2]

## Changelog
- 2024-01-20: Migrated from ClickUp
```

### Step 2.4: Quality Checks

After LLM extraction, verify:
- [ ] All sections from original are present
- [ ] Code blocks are properly formatted
- [ ] Links are identified (even if broken initially)
- [ ] Tables are converted to markdown tables
- [ ] Lists maintain proper hierarchy
- [ ] Special callouts/warnings are preserved

## Phase 3: Repository Setup

### Step 3.1: Initialize Repository Structure

1. Create the directory structure (as shown in Prerequisites)
2. Initialize git repository if not exists
3. Create README files for each section:

**docs/README.md:**
```markdown
# Documentation

Comprehensive documentation for the GolfDaddy Brain system.

## Structure
- `/api` - API references and endpoints
- `/guides` - User guides and tutorials
- `/architecture` - System design and architecture
- `/processes` - Business processes and workflows
- `/reference` - Technical references and specifications

## Contributing
All documentation updates go through the doc agent approval workflow.

## Search
Documentation is indexed for semantic search via embeddings.
```

### Step 3.2: Configure Doc Agent Integration

Create `docs/.meta/config.json`:
```json
{
  "auto_update": true,
  "approval_required": true,
  "quality_threshold": 80,
  "embedding_model": "text-embedding-3-large",
  "categories": {
    "api": {
      "auto_generate": true,
      "template": "api-template.md"
    },
    "guides": {
      "review_required": true
    },
    "architecture": {
      "update_frequency": "quarterly"
    }
  }
}
```

### Step 3.3: Set Up Git Hooks

Configure pre-commit hooks for documentation:
1. Validate markdown syntax
2. Check frontmatter completeness
3. Verify internal links
4. Ensure naming conventions

## Phase 4: Content Import & Organization

### Step 4.1: Content Review and Cleaning

1. **Review extracted content** in `docs/migration/extracted/`
2. **Fix any extraction issues:**
   - Incomplete code blocks
   - Broken formatting
   - Missing sections
   - Incorrect categorization

3. **Standardize formatting:**
   - Consistent heading levels
   - Uniform code block languages
   - Standardized link formats
   - Consistent list styles

### Step 4.2: Organize into Repository

1. **Move files** from `extracted/` to proper directories:
   - API docs → `docs/api/`
   - Guides → `docs/guides/`
   - Architecture → `docs/architecture/`
   - Processes → `docs/processes/`
   - References → `docs/reference/`

2. **Rename files** following conventions:
   - Use kebab-case: `authentication-guide.md`
   - Include version if applicable: `api-v2-reference.md`
   - Be descriptive but concise

3. **Update internal links:**
   - Convert ClickUp links to relative markdown links
   - Fix cross-references between documents
   - Add links to related documentation

### Step 4.3: Create Document Index

Generate `docs/.meta/index.json`:
```json
{
  "documents": [
    {
      "path": "api/authentication.md",
      "title": "Authentication Guide",
      "category": "api",
      "tags": ["auth", "security"],
      "checksum": "abc123...",
      "last_modified": "2024-01-20"
    }
  ],
  "categories": {
    "api": 15,
    "guides": 23,
    "architecture": 8,
    "processes": 12,
    "reference": 19
  },
  "total_documents": 77,
  "last_indexed": "2024-01-20T10:00:00Z"
}
```

## Phase 5: Doc Agent Configuration

### Step 5.1: Database Setup

1. **Create necessary tables** in Supabase:
   - `document_metadata` - Document information
   - `document_embeddings` - Search embeddings
   - `doc_approvals` - Approval workflow
   - `document_versions` - Version history

2. **Configure indexes** for:
   - Full-text search
   - Vector similarity search
   - Category filtering
   - Tag searching

### Step 5.2: Enable Automated Updates

1. **Configure commit monitoring:**
   - Set up GitHub webhooks
   - Configure which commits trigger doc updates
   - Set rules for auto-generation

2. **Set approval workflows:**
   - Define approval requirements by category
   - Configure Slack notifications
   - Set auto-approval thresholds

3. **Configure quality checks:**
   - Minimum documentation score
   - Required sections by document type
   - Style guide compliance

### Step 5.3: Generate Embeddings

1. **Process all documents** to generate embeddings
2. **Store in database** for semantic search
3. **Test search functionality** with sample queries
4. **Optimize chunk size** for best results

### Step 5.4: Slack Integration

1. **Set up Slack app** with required permissions
2. **Configure channels** for notifications:
   - Approval requests
   - Update notifications
   - Quality alerts

3. **Test approval workflow:**
   - Create test documentation update
   - Verify Slack notification
   - Test approval/rejection flow

## Phase 6: Validation & Go-Live

### Step 6.1: Content Validation

Verify for each document:
- [ ] Content completeness compared to original
- [ ] All code examples are valid
- [ ] Internal links work correctly
- [ ] Frontmatter is complete and accurate
- [ ] Document renders correctly in markdown viewer

### Step 6.2: System Testing

1. **Search Testing:**
   - Test common search queries
   - Verify relevance of results
   - Check search performance

2. **Update Workflow:**
   - Create test commit
   - Verify doc agent triggers
   - Test approval process
   - Confirm PR creation

3. **Integration Testing:**
   - Test GitHub webhook
   - Verify Slack notifications
   - Check database updates
   - Validate embedding generation

### Step 6.3: Performance Validation

Check:
- Document load times
- Search response times
- Embedding generation speed
- Approval workflow latency

### Step 6.4: Go-Live Checklist

- [ ] All documents migrated and validated
- [ ] Embeddings generated for all documents
- [ ] Search functionality verified
- [ ] Approval workflows tested
- [ ] Team trained on new system
- [ ] Backup of all documentation created
- [ ] Monitoring configured
- [ ] Rollback plan prepared

### Step 6.5: Cutover Process

1. **Announce migration** to team
2. **Freeze ClickUp documentation** (read-only)
3. **Deploy doc agent** to production
4. **Enable webhooks** and automation
5. **Monitor** for first 24-48 hours
6. **Gather feedback** and address issues

## Post-Migration

### Immediate Tasks (Day 1-7)
1. Monitor approval queue for backlog
2. Address any broken links reported
3. Fix search relevance issues
4. Update team bookmarks/references
5. Document any manual fixes needed

### Short-term Tasks (Week 1-4)
1. Review search analytics
2. Identify most accessed documents
3. Prioritize updates for high-traffic docs
4. Establish update cadence
5. Train team on contribution process

### Long-term Maintenance
1. Regular quality audits
2. Periodic embedding regeneration
3. Archive outdated documentation
4. Expand automation rules
5. Optimize based on usage patterns

### Success Metrics
Track:
- Documentation coverage (% of code documented)
- Search success rate
- Average approval time
- Documentation freshness (days since update)
- User satisfaction scores

## Required Scripts

### Essential Scripts to Develop

1. **screenshot_processor.py**
   - Takes screenshot directory as input
   - Sends images to GPT-4 Vision API
   - Extracts structured content
   - Generates markdown with frontmatter
   - Handles multi-page documents

2. **content_validator.py**
   - Validates markdown syntax
   - Checks frontmatter completeness
   - Verifies internal links
   - Reports missing sections
   - Compares against original screenshots

3. **document_importer.py**
   - Reads processed markdown files
   - Creates database records
   - Generates initial embeddings
   - Builds document index
   - Sets up monitoring rules

4. **link_fixer.py**
   - Scans all documents for links
   - Identifies broken ClickUp links
   - Suggests replacements
   - Updates cross-references
   - Validates all internal links

5. **embedding_generator.py**
   - Processes documents in batches
   - Splits content into optimal chunks
   - Generates embeddings via OpenAI
   - Stores in vector database
   - Handles rate limiting

6. **migration_monitor.py**
   - Tracks migration progress
   - Compares source vs migrated content
   - Identifies missing documents
   - Generates progress reports
   - Alerts on issues

7. **search_tester.py**
   - Runs predefined test queries
   - Measures search relevance
   - Tests different embedding strategies
   - Optimizes search parameters
   - Generates performance report

8. **approval_workflow_test.py**
   - Creates test documentation updates
   - Triggers approval workflow
   - Verifies Slack integration
   - Tests auto-approval rules
   - Validates PR creation

9. **bulk_metadata_updater.py**
   - Updates frontmatter in bulk
   - Adds missing metadata fields
   - Standardizes tags and categories
   - Updates version numbers
   - Maintains consistency

10. **documentation_reporter.py**
    - Generates migration summary
    - Creates coverage reports
    - Identifies documentation gaps
    - Tracks quality metrics
    - Produces executive summary

### Utility Scripts

11. **clickup_url_extractor.py**
    - Parses ClickUp workspace
    - Extracts all documentation URLs
    - Creates initial inventory
    - Generates screenshot list

12. **markdown_formatter.py**
    - Standardizes markdown formatting
    - Fixes common formatting issues
    - Ensures consistent style
    - Prettifies code blocks

13. **category_organizer.py**
    - Analyzes document content
    - Suggests categorization
    - Moves files to correct directories
    - Updates index

14. **rollback_script.py**
    - Reverts migration if needed
    - Restores previous state
    - Maintains backup copies
    - Logs all changes

15. **health_checker.py**
    - Monitors documentation system
    - Checks for stale content
    - Identifies broken workflows
    - Alerts on issues

## Module Structure Update (2025-08-17)

The `doc_agent` module has been consolidated within the backend for better organization and production readiness:

### Changes Made
- **Consolidated Location**: Module now exclusively at `backend/app/doc_agent/`
- **Removed Duplicate**: Eliminated duplicate module from project root
- **Updated Scripts**: Modified all scripts to use backend path with proper Python path configuration
- **Preserved Features**: Maintained all existing functionality including V1 and V2 clients

### Import Path Changes
```python
# Old (from project root)
from doc_agent.client import AutoDocClient

# New (within backend code)
from app.doc_agent.client import AutoDocClient

# New (from scripts outside backend)
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../backend'))
from app.doc_agent.client import AutoDocClient
```

### Affected Files
- `backend/app/api/v1/api.py` - Updated import path
- `scripts/auto_docs.py` - Added path configuration
- `scripts/pre_commit_auto_docs.py` - Added path configuration
- `scripts/setup_doc_agent.sh` - Updated embedded Python code

### Benefits
- **Single Source of Truth**: No more duplicate code to maintain
- **Better Organization**: Module is now properly part of the backend application
- **Production Ready**: Clear import paths and dependencies
- **Easier Testing**: All tests run from backend context with proper paths