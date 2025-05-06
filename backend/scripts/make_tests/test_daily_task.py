import os
import requests
import json
import time
from dotenv import load_dotenv

# Load environment variables from .env file in the workspace root
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
dotenv_path = os.path.join(workspace_root, '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- Configuration ---
# Get webhook URLs from environment variables
WEBHOOK_URL_TASK_CREATED = os.getenv("MAKE_WEBHOOK_TASK_CREATED")
WEBHOOK_URL_TASK_BLOCKED = os.getenv("MAKE_WEBHOOK_TASK_BLOCKED")

# Replace with a REAL Slack User ID for testing
TEST_MANAGER_SLACK_ID = os.getenv("TEST_SLACK_USER_ID", "U0XXXXXXXXX")

# Test payload for task created 
TASK_CREATED_PAYLOAD = {
    "manager_id": "test-manager-uuid-12345",
    "manager_slack_id": TEST_MANAGER_SLACK_ID,
    "manager_name": "Test Manager",
    "task_id": "daily-task-123",
    "task_description": "Review Q3 marketing budget proposal",
    "task_status": "created",
    "creation_date": "2024-08-16T09:00:00Z",
    "due_date": "2024-08-16T17:00:00Z",
    "is_eod_reminder": True,
    "timestamp": time.time()
}

# Test payload for a blocked task
TASK_BLOCKED_PAYLOAD = {
    "manager_id": "test-manager-uuid-12345",
    "manager_slack_id": TEST_MANAGER_SLACK_ID,
    "manager_name": "Test Manager",
    "task_id": "daily-task-456",
    "task_description": "Send team update email",
    "task_status": "blocked",
    "creation_date": "2024-08-16T09:00:00Z",
    "due_date": "2024-08-16T17:00:00Z",
    "is_eod_reminder": True,
    "timestamp": time.time()
}
# ---

def send_test_request(payload_to_send, task_status):
    """Sends the test JSON payload to the configured Make.com webhook URL."""
    # Determine which webhook URL to use based on task status
    if task_status == "created":
        webhook_url = WEBHOOK_URL_TASK_CREATED
        env_var_name = "MAKE_WEBHOOK_TASK_CREATED"
    elif task_status == "blocked":
        webhook_url = WEBHOOK_URL_TASK_BLOCKED
        env_var_name = "MAKE_WEBHOOK_TASK_BLOCKED"
    else:
        print(f"Error: Unknown task status '{task_status}'")
        return

    if not webhook_url:
        print(f"Error: {env_var_name} environment variable not set.")
        print(f"Please set it in your {dotenv_path} file or environment.")
        return

    if TEST_MANAGER_SLACK_ID == "U0XXXXXXXXX":
        print("Warning: TEST_SLACK_USER_ID not set. Using placeholder.")
        print("The Slack message might not be delivered to a specific manager.")

    headers = {"Content-Type": "application/json"}

    try:
        print(f"Sending {task_status} daily task payload to: {webhook_url}")
        response = requests.post(webhook_url, headers=headers, data=json.dumps(payload_to_send))
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        print("\n--- Request Sent ---")
        print(f"Payload: {json.dumps(payload_to_send, indent=2)}")
        print("\n--- Response --- ")
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")

        if response.status_code == 200 and response.text.lower() == "accepted":
            print("\nSuccess: Make.com accepted the webhook data.")
            print("Check your Make.com scenario history and Slack for the message.")
        else:
            print("\nWarning: Received non-standard success response from Make.com.")

    except requests.exceptions.RequestException as e:
        print(f"\nError sending request: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    test_type = input("What would you like to test?\n1. Task created\n2. Task blocked\nEnter number (default: 1): ") or "1"
    
    if test_type == "1":
        print("\n--- Testing Make.com Daily Task (Created) --- ")
        send_test_request(TASK_CREATED_PAYLOAD, "created")
    elif test_type == "2":
        print("\n--- Testing Make.com Daily Task (Blocked) --- ")
        send_test_request(TASK_BLOCKED_PAYLOAD, "blocked")
    else:
        print("\nInvalid selection. Using default (task created).")
        send_test_request(TASK_CREATED_PAYLOAD, "created") 