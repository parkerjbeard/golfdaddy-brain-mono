# Architecture Overview

This document describes the high-level structure of the **GolfDaddy Brain** backend and shows how data flows through the system for common operations.

## Components

- **API Gateway (FastAPI)** – Entry point for all requests. Handles authentication, rate limiting and routing.
- **Services** – Business logic implemented in Python services such as `CommitAnalysisService`, `DailyReportService` and `DocumentationUpdateService`.
- **Repositories** – Thin persistence layer that interacts with the Supabase Postgres database.
- **Database (Supabase/Postgres)** – Stores users, tasks, commits, daily reports and generated docs.
- **AI Service (OpenAI)** – Provides commit analysis, EOD summarisation and documentation generation.
- **Integrations**
  - **GitHub** – Source for commit diffs and destination for documentation PRs.
  - **Make.com** – Webhooks used to send commit events and notifications.
  - **Doc Agent** – Lightweight client that analyses commits and proposes doc updates.

## High‑Level Diagram

```text
                +----------------+
                |   Frontend     |
                +----------------+
                        |
                        v
                +----------------+      triggers webhooks      +---------------+
GitHub -------->|  Make.com      |---------------------------->| API Gateway   |
                +----------------+                             | (FastAPI)     |
                                                               +---------------+
                                                                        |
                                                                        v
                                                     +--------------------------+
                                                     |        Services          |
                                                     |  CommitAnalysisService   |
                                                     |  DailyReportService      |
                                                     |  DocGenerationService    |
                                                     +--------------------------+
                                                                        |
                                                                        v
                                                     +--------------------------+
                                                     |       Repositories       |
                                                     +--------------------------+
                                                                        |
                                                                        v
                                                     +--------------------------+
                                                     |    Supabase Database     |
                                                     +--------------------------+
                                                                        |
                                                                        v
                                                     +--------------------------+
                                                     |       AI Service         |
                                                     +--------------------------+
```

The Doc Agent operates outside the main API. It pulls commit diffs, uses the AI service, and pushes documentation PRs to GitHub for review.

## Data Flows

### 1. Commit Processing

1. **GitHub** notifies **Make.com** of a new commit.
2. **Make.com** sends a webhook to `/api/v1/integrations/github/commit` on the **API Gateway**.
3. The request is authenticated and forwarded to **CommitAnalysisService**.
4. The service fetches the diff from GitHub, invokes the **AI Service** for analysis and persists results via the **CommitRepository**.
5. If documentation updates are enabled, **DocumentationUpdateService** (or the external **Doc Agent**) creates PRs in the docs repository.
6. The service can trigger **Make.com** webhooks for notifications.

### 2. End‑of‑Day (EOD) Report Generation

1. A user submits text via `/reports/daily`.
2. **DailyReportService** stores the raw report and calls the **AI Service** to summarise tasks, estimate hours and request clarifications.
3. The processed report is saved back to the database and can reference related commits.
4. Notifications or reminders may be sent via **Make.com**.

### 3. Documentation Updates

1. Requests to `/docs` or analysis triggered from commit processing call **DocGenerationService** or **DocumentationUpdateService**.
2. The service feeds context and code snippets to the **AI Service**.
3. Generated documentation is stored in Supabase and optionally pushed to GitHub (either directly or via the **Doc Agent**).
4. A link to the generated document or PR is returned to the user.

---
