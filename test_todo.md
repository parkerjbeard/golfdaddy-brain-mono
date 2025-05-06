# Backend Test Plan (TODO)

This document outlines the necessary tests for the backend application.

## 1. Models (`backend/app/models/`)

- **`daily_report.py`**:
    - `AiAnalysis`:
        - Test creation with valid data.
        - Test creation with missing optional fields (e.g., `estimated_hours`, `estimated_difficulty`).
        - Test `clarification_requests` initialization and updates.
    - `ClarificationRequest`:
        - Test creation with valid data.
        - Test default values (e.g., `status`, `created_at`, `updated_at`).
        - Test `ClarificationStatus` enum usage.
    - `DailyReportBase`:
        - Test creation with valid data.
        - Test optional fields.
    - `DailyReportCreate`:
        - Test creation with valid data.
        - Test inheritance from `DailyReportBase`.
    - `DailyReportUpdate`:
        - Test creation with all fields optional.
        - Test that at least one field can be provided for an update.
    - `DailyReport` (DB Model):
        - Test creation with valid data, including nested `AiAnalysis`.
        - Test default values (e.g., `created_at`, `updated_at`, `status`, `linked_commit_ids`).
        - Test relationship with `user_id`.
- **General Model Tests**:
    - For all Pydantic models:
        - Test validation errors with invalid data types.
        - Test validation for required fields.
        - Test JSON serialization and deserialization (`.model_dump_json()` and `model_validate_json()`).

## 2. Repositories (`backend/app/repositories/`)

- **`daily_report_repository.py`**:
    - `DailyReportRepository`:
        - `create_daily_report`:
            - Test successful creation and return of `DailyReport` object.
            - Mock database call and verify input.
        - `get_daily_report_by_id`:
            - Test retrieving an existing report.
            - Test retrieving a non-existent report (should return `None`).
            - Mock database call.
        - `get_daily_reports_by_user_id`:
            - Test retrieving reports for a user.
            - Test for a user with no reports (should return empty list).
            - Mock database call.
        - `get_daily_reports_by_user_and_date`:
            - Test retrieving a report for a specific user and date.
            - Test for a user/date with no report (should return `None`).
            - Mock database call, especially date handling.
        - `update_daily_report`:
            - Test successful update of various fields (e.g., `raw_text_input`, `ai_analysis`, `overall_assessment_notes`).
            - Test updating a non-existent report (should handle gracefully, e.g., return `None` or raise specific error if designed so).
            - Mock database call and verify update payload.
        - `delete_daily_report` (if it exists or is planned):
            - Test successful deletion.
            - Test deleting a non-existent report.
            - Mock database call.
- **General Repository Tests**:
    - Ensure all repository methods correctly interact with the (mocked) database.
    - Test for correct data transformation between application layer and database layer if any.

## 3. Services (`backend/app/services/`)

- **`daily_report_service.py`**:
    - `DailyReportService`:
        - `submit_daily_report`:
            - Test submitting a new report (no existing report for user/date).
                - Verify `DailyReportRepository.create_daily_report` is called.
                - Verify AI processing placeholder logic (dummy `AiAnalysis` creation).
                - Verify `DailyReportRepository.update_daily_report` is called with AI data.
                - Mock `AiIntegrationService.analyze_eod_report` if it were active.
            - Test submitting a report when one already exists for the user/date (update existing).
                - Verify `DailyReportRepository.get_daily_reports_by_user_and_date` is called.
                - Verify `DailyReportRepository.update_daily_report` is called for the existing report.
            - Test error handling during AI processing (ensure report is still returned).
            - Test with `current_user_id`.
        - `get_report_by_id`:
            - Test retrieving an existing report.
            - Test retrieving a non-existent report.
            - Verify call to `DailyReportRepository.get_daily_report_by_id`.
        - `get_reports_for_user`:
            - Test retrieving reports for a user.
            - Verify call to `DailyReportRepository.get_daily_reports_by_user_id`.
        - `get_user_report_for_date`:
            - Test retrieving a report for a user and date.
            - Verify call to `DailyReportRepository.get_daily_reports_by_user_and_date`.
        - `update_report_assessment`:
            - Test successfully updating assessment notes and final hours.
            - Verify call to `DailyReportRepository.update_daily_report` with correct data.
        - `link_commits_to_report`:
            - Test linking new commit IDs to a report.
            - Test linking commit IDs when some already exist (ensure no duplicates, append new).
            - Test linking to a non-existent report (should return `None`).
            - Verify calls to `DailyReportRepository.get_daily_report_by_id` and `update_daily_report`.
        - **Clarification Request Flow (TODO section in service)**:
            - Test AI requesting clarification.
            - Test user responding to clarification.
            - Test `ClarificationRequest` status updates.
- **`ai_integration_service.py` (Placeholder - test if/when implemented)**:
    - Mock external AI API calls.
    - Test `analyze_eod_report` method:
        - Input: `raw_text_input`.
        - Output: `AiAnalysis` object.
        - Test error handling from external API.
- **`user_service.py` (Placeholder - test if/when implemented)**:
    - Test user validation logic.
- **General Service Tests**:
    - Mock all external dependencies (repositories, other services, external APIs).
    - Focus on testing business logic within each service method.
    - Test error handling and edge cases.

## 4. API Endpoints (`backend/app/api/`)

- Need to inspect files in `backend/app/api/` to define specific tests.
- **`daily_report_endpoints.py`**:
    - Test `POST /reports/` (submit_daily_report):
        - Valid payload, successful creation.
        - Invalid payload (validation errors).
        - Service layer exceptions.
        - Authentication (e.g., `current_user`).
    - Test `GET /reports/{report_id}` (get_daily_report):
        - Existing report.
        - Non-existent report (404).
        - Invalid UUID format for `report_id`.
    - Test `GET /reports/user/{user_id}` (get_reports_for_user):
        - User with reports.
        - User with no reports.
        - Invalid UUID format for `user_id`.
    - Test `GET /reports/user/{user_id}/date/{report_date}` (get_user_report_for_date):
        - Report exists for user/date.
        - No report for user/date.
        - Invalid date format.
    - Test `PUT /reports/{report_id}/assessment` (update_report_assessment):
        - Valid payload.
        - Non-existent report.
        - Invalid payload (e.g., non-float hours).
    - Test `PUT /reports/{report_id}/commits` (link_commits_to_report):
        - Valid payload.
        - Non-existent report.
- **`task_endpoints.py`**:
    - (Inspect `task_endpoints.py` for specific routes and define tests similar to `daily_report_endpoints.py`)
    - Example tests:
        - Create task.
        - Get task by ID.
        - Get tasks by user/project.
        - Update task.
        - Delete task.
- **`auth_endpoints.py`**:
    - (Inspect `auth_endpoints.py` for specific routes like /login, /register, /refresh_token)
    - Test successful login with valid credentials.
    - Test login with invalid credentials.
    - Test token refresh.
    - Test user registration (if applicable).
- **`github_events.py`**:
    - Test handling of GitHub webhook events (e.g., push, pull_request).
    - Verify parsing of webhook payloads.
    - Verify calls to appropriate services (e.g., to link commits).
    - Test security/signature verification of webhooks if implemented.
- **`slack_events.py` / `slack.py`**:
    - Test handling of Slack events or commands.
    - Verify parsing of Slack payloads.
    - Verify interaction with Slack API (mocked).
    - Test any challenge/verification requests from Slack.
- **General API Test Structure (for each endpoint)**:
    - Test successful requests (200 OK, 201 Created, etc.).
        - Verify response schema and data.
        - Verify calls to underlying service methods with correct parameters.
    - Test invalid input data (422 Unprocessable Entity).
        - Verify Pydantic validation errors in response.
    - Test unauthorized/forbidden access (401 Unauthorized, 403 Forbidden) if auth is implemented.
    - Test non-existent resources (404 Not Found).
    - Test different HTTP methods (GET, POST, PUT, DELETE).
    - Mock service layer to isolate API logic.

## 5. Integrations (`backend/app/integrations/`)

- (Assuming make.com handles actual Slack/GitHub interaction, backend might have client/connector classes)
- Mock calls to make.com or any direct SDK usage for Slack/GitHub.
- Test any data transformation or preparation logic before sending data to external services.
- Test handling of responses/errors from these integrations.

## 6. Authentication/Authorization (`backend/app/auth/`)

- Need to inspect files in `backend/app/auth/` if it exists and contains logic.
- Test token generation and validation (if applicable).
- Test dependency injections for current user.
- Test permission checks.

## 7. Configuration (`backend/app/config/`)

- Test loading of configurations.
- Test default values and overrides via environment variables.

## 8. Main Application (`backend/app/main.py`)

- Test application startup.
- Test middleware registration and functionality (if any custom middleware in `backend/app/middleware/`).
- Test basic health check endpoint if available.

## Test Setup and Conventions

- Use `pytest` as the test runner.
- Use `pytest-asyncio` for async tests.
- Employ mocking extensively (e.g., `unittest.mock.AsyncMock` for async methods).
- Organize tests in a `backend/tests/` directory, mirroring the `app` structure (e.g., `backend/tests/services/test_daily_report_service.py`).
- Use clear and descriptive test function names.
- Aim for high test coverage.
- Fixtures for common setup (e.g., test client for API tests, mock repositories). 