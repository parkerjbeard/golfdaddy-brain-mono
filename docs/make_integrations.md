# Make.com Integration Documentation

This document details potential Make.com scenarios for the project, primarily focusing on the notification system and potentially bridging other services like GitHub to the backend. Each scenario receives data (via webhooks from the backend or directly from services like GitHub) and performs actions like calling backend APIs or sending Slack messages.

## Prerequisites

- A Make.com account with access to create new scenarios
- Connections configured in Make.com for relevant services (Slack, GitHub) or permissions to create them
- Access to update backend environment variables/settings and potentially deploy new API endpoints

## Overview

Make.com can serve multiple roles:

1.  **Notification Relay (Primary Use):** The backend's `NotificationService` identifies events (like task creation) and sends specific data (JSON payloads) to unique Make.com webhook URLs. Each URL triggers a separate Make.com scenario responsible for formatting and sending a message to Slack.
2.  **Event Forwarding (e.g., GitHub):** Make.com can listen for events from external services (like GitHub commits) and forward structured data to specific backend API endpoints for processing (e.g., commit analysis).

## Required Make.com Scenarios (Notifications)

These scenarios are triggered by webhooks called from the backend `NotificationService`. You need to create **four** distinct scenarios in Make.com for notifications:

1.  Task Created Notification
2.  Task Blocked Notification
3.  End-of-Day (EOD) Reminder
4.  Personal Mastery Reminder

---

## Potential Additional Make.com Scenarios

Based on the project outline (`docs/outline.md`), here are other areas where Make.com *could* be used.

### 5. Make.com Scenario: GitHub Commit Forwarding

**Purpose:** To capture new commits from a specified GitHub repository and forward relevant information to the backend for AI analysis (`commit_analysis_service.py`).

**Triggering Event (External):** A push event to a specific branch in a configured GitHub repository.

**Target Backend API Endpoint:** You will need to create a dedicated endpoint in your backend (e.g., within `app/api/github_events.py` or similar) to receive this data. Let's assume `POST /api/v1/integrations/github/commit` for this example. This endpoint should be secured appropriately (e.g., using an API key known to Make.com).

**Backend API Endpoint Setting (Backend):** Store the URL for this new endpoint in `settings.py` (e.g., `settings.backend_github_commit_endpoint`). Also store any necessary API key in settings (e.g., `settings.make_integration_api_key`).

**Expected Payload (Sent *to* Backend API):** The Make.com scenario should construct and send a JSON payload like this to your backend endpoint:

```json
{
  "commit_hash": "string (SHA)",
  "commit_message": "string",
  "commit_url": "string (URL to commit)",
  "commit_timestamp": "string (ISO 8601 format)",
  "author_github_username": "string",
  "author_email": "string",
  "repository_name": "string",
  "repository_url": "string",
  "branch": "string",
  "diff_url": "string (URL to diff, e.g., commit_url.patch or .diff)"
  // Optionally, if Make.com fetches the diff:
  // "commit_diff": "string (The actual diff content)"
}
```
*(Note: Your backend's `commit_analysis_service.py` will need to map `author_github_username` or `author_email` to an internal `User` record).*

**Make.com Scenario Setup Steps (Detailed):**

1.  **Log in to Make.com & Create New Scenario:** Follow Steps 1-3 from Scenario 1 (Task Created Notification).
2.  **Search for Trigger Module:** Click the central "+", search for "GitHub".
3.  **Select GitHub Module:** Click the "GitHub" module icon.
4.  **Choose GitHub Trigger:** Select the "Watch Commits" (or "Watch Push Events" - choose the one that provides the most useful initial data) trigger.
5.  **Configure GitHub Connection:**
    *   Click "Add" next to "Connection" if you haven't connected your GitHub account. Follow the prompts to authorize Make.com to access your repositories. You might need to grant access to specific repositories.
    *   Select the specific **Repository** you want to monitor.
    *   Select the **Branch** (e.g., `main`, `develop`) to watch for commits/pushes.
    *   Configure **Limit** (how many commits to process per run). Start with a small number like 5 or 10.
    *   Click "OK". Make.com might ask to run the trigger once to determine the data structure based on recent commits.
6.  **(Optional) Add GitHub Module: Get a Commit:** If the trigger event payload doesn't include enough detail (e.g., the commit timestamp or full author details), you might need to add another GitHub module *after* the trigger.
    *   Click "+ Add another module".
    *   Select "GitHub" -> "Get a Commit".
    *   Use the `Commit SHA` data field mapped from the *trigger* module (`1. sha` or similar) as input.
    *   Click "OK".
7.  **Add HTTP Module (Call Backend API):**
    *   Click "+ Add another module" after the GitHub trigger (or the optional "Get a Commit" module).
    *   Search for "HTTP" and select it.
    *   Choose the "Make a request" action.
    *   **URL:** Enter the URL of your backend endpoint (e.g., `{{settings.backend_github_commit_endpoint}}` - you'll likely paste the actual URL here or retrieve it from a Make.com variable if you set one up).
    *   **Method:** `POST`.
    *   **Headers:**
        *   Add item: Name = `Content-Type`, Value = `application/json`.
        *   Add item: Name = `X-API-Key` (or your chosen header from `settings.api_key_header`), Value = `YOUR_MAKE_INTEGRATION_API_KEY` (paste the actual key value stored in your backend settings).
    *   **Body type:** `Raw`.
    *   **Content type:** `JSON (application/json)`.
    *   **Request content:** Construct the JSON payload defined in **Expected Payload (Sent *to* Backend API)** above. Map the relevant data fields from the GitHub trigger module (and the optional "Get a Commit" module). Example mappings (numbers depend on your specific module order):
        ```json
        {
          "commit_hash": "{{1.sha}}", // From Trigger
          "commit_message": "{{1.commit.message}}", // From Trigger
          "commit_url": "{{1.html_url}}", // From Trigger
          "commit_timestamp": "{{formatDate(2.commit.author.date; "YYYY-MM-DDTHH:mm:ssZ")}}", // From 'Get a Commit' module (Module 2)
          "author_github_username": "{{1.author.login}}", // From Trigger
          "author_email": "{{2.commit.author.email}}", // From 'Get a Commit' module (Module 2)
          "repository_name": "{{1.repository.name}}", // From Trigger (adjust path as needed)
          "repository_url": "{{1.repository.html_url}}", // From Trigger (adjust path as needed)
          "branch": "main", // Or map dynamically if trigger provides it
          "diff_url": "{{1.html_url}}.diff" // Construct diff URL
        }
        ```
        *(Carefully check the available fields from your GitHub modules in Make.com and adjust the mappings)*.
    *   **Parse response:** Enable this if you want Make.com to process the backend's response.
    *   Click "OK".
8.  **Save Scenario:** Give it a name like `Forward GitHub Commits to Backend`.
9.  **Activate Scenario:** Toggle scheduling to "ON". It will now periodically check GitHub for new commits and forward them. Adjust the schedule interval as needed (e.g., every 15 minutes).

---

### ClickUp Integration Note

The current project outline (`docs/outline.md` sections 11, 18, 20) suggests that after the AI generates documentation (`doc_generation_service.py`), the backend *directly* calls the ClickUp API via `clickup_integration.py` to create or update the document in ClickUp.

While a Make.com scenario *could* be designed to receive generated documentation from a backend webhook and then call the ClickUp API, this is **not** the flow implied by the current outline. If you wish to use Make.com for this, the backend services (`doc_generation_service.py`, `clickup_integration.py`) and potentially the API layer (`docs_generation.py`) would need to be adjusted to trigger a Make.com webhook instead of making a direct ClickUp API call.

---

## 1. Make.com Scenario: Task Created Notification

**Purpose:** To send a direct message in Slack to a user when they are assigned a new task.

**Triggering Event (Backend):** The `notify_task_created` method in `app/services/notification_service.py`.

**Webhook URL Setting (Backend):** The URL stored in `settings.make_webhook_task_created` (or the corresponding environment variable).

**Webhook URL:** `https://hook.us2.make.com/gte26y9nx8yqiqvwtogjcf4gwyhzki9j`

**Expected Payload (from Backend):** A JSON object with the following structure:

```json
{
  "task_id": "string (UUID)",
  "task_description": "string",
  "assignee_slack_id": "string (Slack User ID, e.g., U0XXXXXXXXX)",
  "assignee_name": "string",
  "responsible_slack_id": "string (Slack User ID) | null",
  "accountable_slack_id": "string (Slack User ID) | null",
  "status": "string (e.g., 'assigned')",
  "due_date": "string (ISO 8601 format, e.g., '2023-10-27T10:00:00Z') | null",
  "creator_slack_id": "string (Slack User ID) | null",
  "creator_name": "string | null"
}
```

**Make.com Scenario Setup Steps (Detailed):**

1.  **Log in to Make.com:** Access your Make.com account.
2.  **Navigate to Scenarios:** Find the "Scenarios" section in the left-hand navigation menu and click on it.
3.  **Create New Scenario:** Click the "+ Create a new scenario" button, usually located in the top-right corner.
4.  **Search for Trigger Module:** You'll see a large "+" button in the center of the screen. Click it. A search box will appear. Type "Webhooks" into the search box.
5.  **Select Webhooks Module:** Click on the "Webhooks" module icon from the search results.
6.  **Choose Webhook Trigger:** A list of triggers and actions will appear for the Webhooks module. Select the "Custom webhook" trigger.
7.  **Configure Webhook:** A configuration panel ("Create a webhook") will pop up.
    *   Click the "Add" button next to the "Webhook" field.
    *   A new dialog "Add a hook" appears.
    *   **Webhook name:** Enter a descriptive name, like `GolfDaddy Task Created Hook`. This name is just for your reference within Make.com.
    *   **IP restrictions:** Leave blank unless you have specific security requirements.
    *   Click the "Save" button.
8.  **Copy Webhook URL:** Make.com will now display the unique **Webhook URL** for this trigger. This is crucial.
    *   Click the "Copy address to clipboard" button to copy the URL.
9.  **Update Backend Configuration:**
    *   **Immediately paste this URL** into your backend's configuration file where the `make_webhook_task_created` setting is defined. This might be in a `.env` file, a `settings.py`, or an environment variable in your deployment environment. Ensure this setting corresponds exactly to the copied URL. **The integration will not work without this step.**
10. **Determine Data Structure (Important!):**
    *   Leave the Make.com scenario editor open. The webhook configuration window should still be open, showing "Stop" and "OK" buttons. It now says "Successfully determined." or it might be waiting for data.
    *   **Crucially, Make.com needs to receive sample data at least once to understand the structure of the JSON payload it will receive.**
    *   Go to your backend application or use a tool like `curl` (see "Testing Webhook URLs" section below) to send a *test* payload to the URL you just copied and configured. Use the **Expected Payload** structure shown above as a template for your test data. Replace placeholder values (like `"U0XXXXXXXXX"`) with valid test data if possible.
    *   Once Make.com successfully receives the test data, the configuration window should show "Successfully determined." This confirms it understands the incoming data format (`task_id`, `task_description`, etc.).
    *   Click "OK" in the Make.com webhook configuration window.

11. **Add Slack Module:**
    *   Hover over the right side of the Webhooks module you just configured. A small semi-circle with a "+" sign will appear. Click this "+ Add another module" button.
    *   A search box appears. Type "Slack".
    *   Click the "Slack" module icon.
12. **Choose Slack Action:** Select the "Create a Message" action from the list.
13. **Configure Slack Connection:** A configuration panel for the Slack message appears.
    *   **Connection:** Click the "Add" button if you haven't connected your Slack workspace yet.
        *   A "Create a connection" window pops up.
        *   **Connection name:** Enter `GolfDaddy Bot Connection`.
        *   **Connection type:** Ensure **Bot** is selected.
        *   Click "Save".
        *   You will be redirected to Slack for authorization. Follow the prompts to allow the "Make Integration" bot (or whatever name Make displays) to access your workspace. You might need Slack admin approval depending on your workspace settings. Ensure the bot is granted the necessary permissions (at least `chat:write` for public/private channels and `im:write` for direct messages).
        *   Once authorized, you'll be redirected back to Make.com. The connection `GolfDaddy Bot Connection` should now be selected.
    *   If you already have the connection set up, simply select it from the dropdown list.
14. **Map Payload Data to Slack Message:** Now, configure the details of the Slack message using the data received by the webhook.
    *   **Enter a channel ID or email address:** Choose "Enter Manually" from the dropdown.
    *   **Channel ID/User ID:** This determines *who* receives the message.
        *   Click into the input field. A panel with available data fields will appear on the right.
        *   Find the "Webhooks - Custom webhook" section (it might be labeled with the name you gave the webhook, e.g., `1. GolfDaddy Task Created Hook`).
        *   Click on the `assignee_slack_id` field (it will appear as `1. assignee_slack_id`). This maps the Slack ID received from your backend to the recipient field, ensuring the message goes directly to the assigned user.
    *   **Text:** This is the *required* fallback text.
        *   Click into the "Text" input field.
        *   From the data panel on the right, click on `1. task_description`. The field should now contain `{{1.task_description}}`.
    *   **Show advanced settings:** Toggle this switch to ON. More options will appear.
    *   **Blocks:** This is where you define the visually rich message using Slack's Block Kit JSON format.
        *   Go to the **Slack Block Kit Builder** (https://app.slack.com/block-kit-builder/) in a separate browser tab.
        *   Design your desired message layout using the visual builder.
        *   In the builder, use placeholders like `{{task_description}}`, `{{status}}`, `{{due_date}}`, `{{creator_name}}` where you want dynamic data to appear.
        *   Once you are happy with the design, copy the entire JSON payload from the right-hand pane of the Block Kit Builder.
        *   Go back to the Make.com scenario editor.
        *   Paste the copied JSON into the "Blocks" field.
        *   **Crucially, you now need to replace the placeholders in the pasted JSON with the actual Make.com data mappings.**
            *   Delete the placeholder `{{task_description}}` in the JSON.
            *   Click *inside* the JSON string where the placeholder was. The Make.com data panel should appear.
            *   Click `1. task_description` from the panel. The correct mapping `{{1.task_description}}` will be inserted into the JSON.
            *   Repeat this process for all placeholders (`{{status}}` becomes `{{1.status}}`, `{{due_date}}` becomes `{{1.due_date}}`, `{{creator_name}}` becomes `{{1.creator_name}}`).
            *   **For the due date:** You'll likely want to format it. Use Make.com's built-in functions. Replace `{{1.due_date}}` with something like `{{if(1.due_date; formatDate(1.due_date; "YYYY-MM-DD"); "Not Set")}}`. This checks if `due_date` exists, formats it if it does, and outputs "Not Set" otherwise. You can access date functions by clicking the calendar/clock icon in the mapping panel or the functions tab (fx).
            *   **For optional fields like creator name:** Use a fallback. Replace `{{1.creator_name}}` with `{{1.creator_name | "System"}}`. The `| "System"` part provides a default value if `creator_name` is missing from the payload.
        *   Refer to the **Example Block Kit JSON** provided earlier in this document to see the final structure with mappings. Double-check your JSON structure and mappings carefully.

15. **Finalize Slack Module:** Click the "OK" button at the bottom of the Slack module configuration panel.
16. **Save Scenario:**
    *   Click the "Save" icon (looks like a floppy disk) located in the bottom control bar.
    *   You might be prompted to name the scenario if you haven't already. Use a descriptive name like `Notify User on New Task Assignment`.
17. **Activate Scenario:**
    *   In the bottom control bar, find the toggle switch labeled "SCHEDULING" (it might initially say "OFF").
    *   Click this toggle to switch it to "ON". The scenario is now active and will run automatically whenever the webhook URL receives data matching the expected structure.

---

## 2. Make.com Scenario: Task Blocked Notification

**Purpose:** To notify the Accountable person when a task is marked as blocked.

**Triggering Event (Backend):** `notify_task_blocked` in `app/services/notification_service.py`.

**Webhook URL Setting (Backend):** `settings.make_webhook_task_blocked`.

**Expected Payload (from Backend):**

```json
{
  "task_id": "string (UUID)",
  "task_description": "string",
  "assignee_slack_id": "string (Slack User ID) | null",
  "assignee_name": "string | null",
  "accountable_slack_id": "string (Slack User ID)", // Should always exist for blocked tasks
  "accountable_name": "string",
  "blocker_slack_id": "string (Slack User ID) | null", // User who marked as blocked
  "blocker_name": "string | null",
  "block_reason": "string" // Reason for blocking
}
```

**Make.com Scenario Setup Steps:**

1.  **Create New Scenario:** Follow Steps 1-3 from Scenario 1 above.
2.  **Add Webhook Trigger:**
    *   Follow Steps 4-9 from Scenario 1, BUT:
        *   **Give the webhook a different name** in Step 7 (e.g., `GolfDaddy Task Blocked Hook`). This generates a *new, unique URL*.
        *   **Copy this NEW URL** in Step 8.
        *   **Update the correct backend setting** (`settings.make_webhook_task_blocked`) with this *new* URL in Step 9.
    *   **Determine Data Structure:** Follow Step 10 from Scenario 1, sending a test payload matching the **Task Blocked** expected structure to the *new* webhook URL.
3.  **Add Slack Module ("Create a Message"):** Follow Steps 11-13 from Scenario 1. You can reuse the same "GolfDaddy Bot Connection".
4.  **Map Payload Data to Slack Message:** Follow Step 14 from Scenario 1, BUT with these specific changes:
    *   **Channel ID/User ID:** Map `1.accountable_slack_id` (instead of `assignee_slack_id`).
    *   **Text:** Use fallback text relevant to blocking, e.g., `Task Blocked: {{1.task_description}} by {{1.blocker_name | "System"}}`.
    *   **Blocks:** Use the Block Kit Builder to design a message suitable for a blocked task notification. Use the **Example Block Kit JSON** for this scenario as a guide, mapping fields like `1.task_description`, `1.block_reason`, `1.assignee_name`, `1.accountable_name`, `1.blocker_name`, and `1.task_id` from *this* webhook's data.
5.  **Save and Activate:** Follow Steps 15-17 from Scenario 1, giving this scenario a distinct name (e.g., `Notify Accountable on Blocked Task`).

---

## 3. Make.com Scenario: End-of-Day (EOD) Reminder

**Purpose:** Send a user a summary of their active tasks.

**Triggering Event (Backend):** `trigger_eod_reminder` in `notification_service.py` (needs scheduling).

**Webhook URL Setting (Backend):** `settings.make_webhook_eod_reminder`.

**Expected Payload (from Backend):**

```json
{
  "user_slack_id": "string (Slack User ID)",
  "user_name": "string",
  "tasks_summary": [ // Array of task objects
    {
      "id": "string (UUID)",
      "description": "string",
      "status": "string",
      "due_date": "string (ISO 8601 format) | null"
    }
    // ... more task objects
  ]
}
```

**Make.com Scenario Setup Steps:**

1.  **Create New Scenario & Webhook Trigger:** Follow Steps 1-10 from Scenario 1, creating a *new* webhook named like `GolfDaddy EOD Reminder Hook`, copying its *new* unique URL, updating the correct backend setting (`settings.make_webhook_eod_reminder`), and determining the data structure using the **EOD Reminder** payload format.
2.  **Add Iterator Module (Handling the Task List):**
    *   Click the "+ Add another module" button attached to the Webhook module.
    *   Search for "Flow Control" and select it.
    *   Choose the "Iterator" action.
    *   **Array:** Click into the field. From the data panel on the right (under your webhook's data, e.g., `1. GolfDaddy EOD Reminder Hook`), click on the `tasks_summary` array field (`1. tasks_summary`). This tells the Iterator to process each item inside the `tasks_summary` list one by one.
    *   Click "OK".
3.  **Add Text Aggregator Module (Combining Task Info):**
    *   Click the "+ Add another module" button attached to the *Iterator* module.
    *   Search for "Tools" and select it (or search directly for "Text aggregator").
    *   Choose the "Text aggregator" action.
    *   A configuration panel appears:
        *   **Source Module:** Select the Iterator module you just added (e.g., `3. Flow Control - Iterator`).
        *   **Row separator:** Choose "New row" from the dropdown.
        *   **Stop processing after an empty aggregation:** Keep as "No".
        *   **Text:** Define how each *individual* task item should be formatted as a line of text. Click into the field. Now, map data fields *from the Iterator* (which represents one task at a time, e.g., `3. id`, `3. description`, `3. status`, `3. due_date`). Example format:
            `• *{{3.description}}* (Status: \`{{3.status}}\`{{if(3.due_date; ", Due: " + formatDate(3.due_date; "YYYY-MM-DD"); "")}})`
            *(Remember to use formatting functions like `formatDate` and `if` as needed. The `3.` prefix refers to the Iterator module number, which might vary depending on your scenario structure).*
    *   Click "OK".
4.  **Add Slack Module ("Create a Message"):**
    *   Click the "+ Add another module" button attached to the *Text Aggregator* module.
    *   Follow Steps 11-13 from Scenario 1 to add the Slack "Create a Message" action and configure the connection.
5.  **Map Payload Data to Slack Message:** Follow Step 14 from Scenario 1, BUT with these specific changes:
    *   **Channel ID/User ID:** Map `1.user_slack_id` (from the *original Webhook trigger*, module 1).
    *   **Text:** Use fallback text like `Your EOD Task Summary`.
    *   **Blocks:** Use the Block Kit Builder. In your Block Kit JSON, where you want the list of tasks to appear, map the output of the *Text Aggregator*. This will look like `{{4.text}}` (assuming the Text Aggregator is module 4). Use a fallback for the case where there are no tasks: `{{4.text | "You have no active tasks today!"}}`. Also map the user's name: `{{1.user_name}}` (from the Webhook trigger). Refer to the **Example Block Kit JSON** for this scenario.
6.  **Save and Activate:** Follow Steps 15-17 from Scenario 1, naming it appropriately (e.g., `Send EOD Task Reminder`).

---

## 4. Make.com Scenario: Personal Mastery Reminder

**Purpose:** Remind managers about pending personal mastery tasks.

**Triggering Event (Backend):** `trigger_personal_mastery_reminder` in `notification_service.py` (needs scheduling).

**Webhook URL Setting (Backend):** `settings.make_webhook_mastery_reminder`.

**Expected Payload (from Backend):**

```json
{
  "manager_slack_id": "string (Slack User ID)",
  "manager_name": "string",
  "mastery_tasks": [ // Array of pending task objects
    {
      "id": "string (UUID)",
      "description": "string",
      "status": "string (e.g., 'pending')",
      "created_at": "string (ISO 8601 format)",
      "completed_at": null
      // potentially other fields if added in PersonalMasteryService
    }
    // ... more task objects
  ]
}
```

**Make.com Scenario Setup Steps:**

1.  **Create New Scenario & Webhook Trigger:** Follow Steps 1-10 from Scenario 1, creating a *new* webhook named like `GolfDaddy Mastery Reminder Hook`, copying its *new* unique URL, updating the correct backend setting (`settings.make_webhook_mastery_reminder`), and determining the data structure using the **Personal Mastery Reminder** payload format.
2.  **Add Iterator Module:** Follow Step 2 from Scenario 3, but map the `1.mastery_tasks` array to the Iterator's "Array" field.
3.  **Add Text Aggregator Module:** Follow Step 3 from Scenario 3, but define the "Text" field to format each mastery task, mapping fields *from the Iterator* (e.g., `3. description`, `3. created_at`). Example format:
    `• {{3.description}} (Added: {{formatDate(3.created_at; "YYYY-MM-DD")}})`
4.  **Add Slack Module ("Create a Message"):** Follow Step 4 from Scenario 3 (attach it after the Text Aggregator).
5.  **Map Payload Data to Slack Message:** Follow Step 5 from Scenario 3, BUT with these specific changes:
    *   **Channel ID/User ID:** Map `1.manager_slack_id` (from the Webhook trigger).
    *   **Text:** Use fallback text like `Your Personal Mastery Reminder`.
    *   **Blocks:** Use the Block Kit Builder. Map the manager's name `{{1.manager_name}}` (from the Webhook). Map the aggregated list of tasks using the Text Aggregator output, e.g., `{{4.text | "You have no pending mastery tasks!"}}`. Refer to the **Example Block Kit JSON** for this scenario.
6.  **Save and Activate:** Follow Steps 15-17 from Scenario 1, naming it appropriately (e.g., `Send Personal Mastery Reminder`).

---

## General Tips for Make.com Setup

- **Naming:** Use clear names for your webhooks and scenarios in Make.com.
- **Error Handling:** Consider adding error handling branches in your Make.com scenarios (e.g., if the Slack API call fails).
- **Testing:** Test each scenario thoroughly. You can use Make.com's "Run once" feature and send test data to the webhook URL using tools like `curl` or Postman before fully activating.
- **Block Kit:** Invest time in designing clear and helpful messages using the Block Kit Builder. Good formatting improves user experience significantly.
- **Rate Limits:** Be mindful of Slack's API rate limits if you anticipate sending a very high volume of notifications. Make.com usually handles basic retries.

## Running Test Scripts

We've created a set of Python scripts to help you test each Make.com webhook integration triggered *by the backend*. These scripts are located in the `scripts/make_tests/` directory. Testing the GitHub forwarding scenario requires triggering a commit in the monitored repository.

### Setup Instructions

1. **Install Dependencies:**
   ```bash
   cd scripts/make_tests
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables:**
   Create or update your `.env` file in the root of your `golfdaddy-brain` workspace with the following variables:
   ```dotenv
   # Make.com Webhook URLs (Triggered by Backend)
   MAKE_WEBHOOK_TASK_CREATED="YOUR_TASK_CREATED_WEBHOOK_URL"
   MAKE_WEBHOOK_TASK_BLOCKED="YOUR_TASK_BLOCKED_WEBHOOK_URL"
   MAKE_WEBHOOK_EOD_REMINDER="YOUR_EOD_REMINDER_WEBHOOK_URL"
   MAKE_WEBHOOK_MASTERY_REMINDER="YOUR_MASTERY_REMINDER_WEBHOOK_URL"

   # Backend Endpoint URL & API Key (For Make.com -> Backend Calls, e.g., GitHub)
   BACKEND_GITHUB_COMMIT_ENDPOINT="YOUR_BACKEND_API_ENDPOINT_FOR_GITHUB_COMMITS"
   MAKE_INTEGRATION_API_KEY="YOUR_SECRET_API_KEY_FOR_MAKE_TO_CALL_BACKEND"

   # Slack User IDs for testing Notifications
   TEST_SLACK_USER_ID="U0XXXXXXXXX"  # Replace with a real Slack User ID
   TEST_BLOCKER_SLACK_ID="U0ZZZZZZZZZ"  # Optional: Replace if needed
   ```

### Available Test Scripts (Backend -> Make.com)

1. **Task Created Notification**
   ```bash
   python test_task_created.py
   ```
   - Tests the webhook for new task notifications
   - Sends a test task to the assignee's Slack DM

2. **Task Blocked Notification**
   ```bash
   python test_task_blocked.py
   ```
   - Tests the webhook for blocked task notifications
   - Sends a notification to the accountable person

3. **End-of-Day (EOD) Reminder**
   ```bash
   python test_eod_reminder.py
   ```
   - Tests the EOD summary webhook
   - Sends a summary of active tasks to the user
   - Includes an option to test with no tasks (uncomment in script)

4. **Personal Mastery Reminder**
   ```bash
   python test_personal_mastery.py
   ```
   - Tests the personal mastery reminder webhook
   - Sends a reminder about pending mastery tasks to the manager
   - Includes an option to test with no tasks (uncomment in script)

### Script Output

Each script will:
1. Print the webhook URL being used
2. Display the JSON payload being sent
3. Show the response status and body
4. Provide success/failure messages

### Troubleshooting

If you encounter issues:
1. Verify all environment variables are set correctly
2. Check that the webhook URLs are valid and active
3. Ensure the Slack User IDs are correct
4. Look for error messages in the script output
5. Check the Make.com scenario execution history for details

Remember to test each scenario in Make.com before running the scripts to ensure the webhook is properly configured and the Slack connection is working.

## Testing Webhook URLs (Backend -> Make.com)

Here are example `curl` commands to test each webhook where the backend initiates the call (replace `YOUR_WEBHOOK_URL` with the actual URLs from Make.com):

**1. Test Task Created:**
```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "task_id": "test-123",
  "task_description": "Test task creation",
  "assignee_slack_id": "U0XXXXXXXXX",
  "assignee_name": "Test User",
  "status": "assigned",
  "due_date": "2024-03-20T10:00:00Z",
  "creator_name": "Test Creator"
}' "YOUR_WEBHOOK_URL"
```

**2. Test Task Blocked:**
```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "task_id": "test-123",
  "task_description": "Test blocked task",
  "assignee_name": "Test Assignee",
  "accountable_slack_id": "U0XXXXXXXXX",
  "accountable_name": "Test Accountable",
  "block_reason": "Testing blocked notification"
}' "YOUR_WEBHOOK_URL"
```

**3. Test EOD Reminder:**
```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "user_slack_id": "U0XXXXXXXXX",
  "user_name": "Test User",
  "tasks_summary": [
    {
      "id": "test-123",
      "description": "Test task 1",
      "status": "in_progress",
      "due_date": "2024-03-20T10:00:00Z"
    },
    {
      "id": "test-456",
      "description": "Test task 2",
      "status": "pending",
      "due_date": null
    }
  ]
}' "YOUR_WEBHOOK_URL"
```

**4. Test Personal Mastery Reminder:**
```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "manager_slack_id": "U0XXXXXXXXX",
  "manager_name": "Test Manager",
  "mastery_tasks": [
    {
      "id": "test-123",
      "description": "Test mastery task 1",
      "status": "pending",
      "created_at": "2024-03-01T10:00:00Z",
      "completed_at": null
    }
  ]
}' "YOUR_WEBHOOK_URL"
```

Replace `U0XXXXXXXXX` with actual Slack user IDs when testing notifications. You can get these IDs from your Slack workspace's user profile information or through the Slack API.

### Testing GitHub Forwarding (GitHub -> Make.com -> Backend)

1.  **Ensure the Make.com scenario is active.**
2.  **Ensure your backend API endpoint (`BACKEND_GITHUB_COMMIT_ENDPOINT`) is running and accessible.**
3.  **Push a commit** to the specific branch of the repository monitored by the Make.com scenario.
4.  **Check the Make.com scenario execution history** to see if it triggered and successfully called your backend API.
5.  **Check your backend logs** to verify it received the payload correctly from Make.com.
6.  **Check your backend database** (`commits` table) to see if the commit information was processed and stored.

Replace `U0XXXXXXXXX` with actual Slack user IDs when testing notifications. You can get these IDs from your Slack workspace's user profile information or through the Slack API. 