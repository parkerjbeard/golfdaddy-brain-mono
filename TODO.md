# Backend TODO List

This list outlines the remaining backend integration and implementation tasks required to complete the project based on the specifications in `docs/outline.md` and `docs/make_integrations.md`.

## 1. GitHub Integration & Commit Analysis

-   **Create GitHub Event API Endpoint:**
    -   Define and implement a new API endpoint (e.g., `POST /api/v1/integrations/github/commit` within a new `app/api/github_events.py` router) to receive commit data.
    -   This endpoint should handle payloads either directly from GitHub webhooks or forwarded from the Make.com "GitHub Commit Forwarding" scenario.
    -   Ensure appropriate security (e.g., API key validation if receiving from Make.com, signature verification if direct from GitHub).
-   **Include GitHub Router:** Add the new GitHub events router to `app/main.py`.
-   **Implement `CommitAnalysisService`:**
    -   Develop the core logic to process incoming commit data received by the API endpoint.
    -   Map GitHub author information (username/email) to internal `User` records (using `UserRepository`).
    -   Implement the call to `AiIntegration` to get points/time estimates for the commit (requires `AiIntegration` to be implemented).
    -   Save the commit details and AI analysis results using `CommitRepository`.
-   **Implement `AiIntegration` (Commit Analysis part):** Ensure the `analyze_commit_diff` (or similar) method is implemented to interact with the chosen AI service.
-   **Implement `CommitRepository`:** Ensure all necessary methods (`save_commit`, `bulk_insert_commits`, etc.) are implemented.
-   **Implement `GithubIntegration` (Optional):** If fetching diffs directly from the backend (instead of relying on Make.com or the payload), implement the necessary methods here.

### Detailed GitHub Integration Tasks

1. **GitHub Webhook Configuration:**
   - Set up webhook in GitHub repository settings
   - Configure webhook to send commit events
   - Document webhook payload structure
   - Set up webhook secret for signature verification

2. **Security Implementation:**
   - Implement GitHub webhook signature verification using `X-Hub-Signature-256`
   - Add validation for required webhook headers
   - Set up proper error responses for invalid signatures
   - Configure rate limiting for webhook endpoints

3. **Payload Processing:**
   - Add validation for different GitHub event types
   - Implement proper error handling for malformed payloads
   - Add logging for webhook receipt and processing
   - Handle retry logic for failed webhook deliveries

4. **GitHub API Integration:**
   - Complete the `get_commit_diff` method in `GitHubIntegration`
   - Add proper error handling for API rate limits
   - Implement caching for API responses if needed
   - Add retry logic for failed API calls

5. **Testing & Monitoring:**
   - Add unit tests for webhook signature verification
   - Add integration tests with sample GitHub payloads
   - Set up monitoring for webhook failures
   - Add logging for GitHub API rate limit usage

6. **Documentation:**
   - Document webhook setup process
   - Add configuration instructions for GitHub tokens
   - Document expected payload formats
   - Add troubleshooting guide for common issues

7. **Error Handling:**
   - Define error response formats
   - Implement proper status code responses
   - Add error logging and monitoring
   - Create recovery procedures for failed webhooks

## 2. ClickUp Integration

-   **Implement `DocGenerationService` Logic:**
    -   Ensure the service correctly calls `AiIntegration` to generate documentation.
    -   Implement the subsequent call to `ClickUpIntegration.create_doc_in_clickup` (or similar) to push the generated document content to ClickUp.
-   **Implement `ClickUpIntegration`:** Develop the methods needed to interact with the ClickUp API (authentication, creating/updating documents).
-   **Implement `AiIntegration` (Doc Generation part):** Ensure the `generate_doc` (or similar) method is implemented.

## 3. Personal Mastery

-   **Implement `PersonalMasteryService`:**
    -   Define the structure for storing mastery tasks (e.g., in the `User.personal_mastery` JSON field or a dedicated table/model).
    -   Implement methods for assigning, tracking, and retrieving these tasks.
-   **Implement `NotificationService.trigger_personal_mastery_reminder`:**
    -   Add the function that fetches pending mastery tasks (using `PersonalMasteryService` and `UserRepository`) and prepares the payload for the Make.com webhook (`settings.make_webhook_mastery_reminder`).
-   **Schedule Personal Mastery Reminder:**
    -   Add a new scheduled job in `app/main.py`'s `start_scheduler` function to call `NotificationService.trigger_personal_mastery_reminder` at the desired frequency (e.g., weekly).

## 4. KPI Service

-   **Implement `KpiService`:**
    -   Develop the logic to calculate defined KPIs (velocity, burndown, efficiency) using data from `TaskRepository` and `CommitRepository`.
-   **Determine Trigger Mechanism:** Decide how KPIs are generated (e.g., on a schedule, via an API endpoint).
-   **Integrate Trigger:**
    -   *If Scheduled:* Add a new scheduled job in `app/main.py`'s `start_scheduler`.
    -   *If API:* Create a new router (e.g., `app/api/kpi_endpoints.py`) with endpoints like `GET /kpi` or `POST /kpi/calculate`, include it in `app/main.py`, and implement the endpoint logic to call `KpiService`.

## 5. RACI Service Integration

-   **Implement `RaciService`:** Develop the methods for RACI validation and escalation logic.
-   **Integrate into `TaskEndpoints`:** Modify the task creation and update endpoints in `app/api/task_endpoints.py` to call `RaciService` methods for validation before saving/updating tasks via `TaskRepository`. Handle potential validation errors.
-   **Integrate Escalation:** Ensure the blocked task flow triggers `RaciService.escalate_blocked_task`, which in turn should correctly interact with `NotificationService` to send alerts.

## 6. General Service/Repository Implementation

-   **Complete `NotificationService`:** Ensure all notification methods (`task_created`, `task_blocked`, `eod_reminder`, `personal_mastery_reminder`) are fully implemented to prepare and send payloads to the correct Make.com webhooks defined in `settings`.
-   **Complete `UserRepository`, `TaskRepository`:** Ensure all required data access methods outlined or implied by the services are fully implemented.
-   **Review Settings:** Ensure all necessary API keys, webhook URLs, and external service configurations are present in `app/config/settings.py` and corresponding environment variables (`.env`).

## 7. Testing

-   Develop unit tests for all new/updated services and repositories.
-   Develop integration tests for the key flows:
    -   GitHub commit -> Backend analysis -> DB storage.
    -   Doc generation request -> AI -> ClickUp.
    -   Task creation/update -> RACI validation.
    -   Scheduled reminders (EOD, Personal Mastery). 