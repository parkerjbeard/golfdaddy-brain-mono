import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env file in the workspace root
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
dotenv_path = os.path.join(workspace_root, '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- Configuration ---
# Get webhook URL from environment variable
WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_TASK_CREATED")

# Replace with a REAL Slack User ID for testing DMs
TEST_ASSIGNEE_SLACK_ID = os.getenv("TEST_SLACK_USER_ID", "U0XXXXXXXXX")

# Test payload structure
TEST_PAYLOAD = {
    "task_id": "test-uuid-12345",
    "task_description": "Test Task: Please review the Q3 budget proposal.",
    "assignee_slack_id": TEST_ASSIGNEE_SLACK_ID,
    "assignee_name": "Test Assignee",
    "responsible_slack_id": None,
    "accountable_slack_id": None,
    "status": "assigned",
    "due_date": "2024-08-15T17:00:00Z",
    "creator_slack_id": "U0YYYYYYYYY", # Optional: Can be a real or test ID
    "creator_name": "Test Creator"
}
# ---

def send_test_request():
    """Sends the test JSON payload to the configured Make.com webhook URL."""
    if not WEBHOOK_URL:
        print("Error: MAKE_WEBHOOK_TASK_CREATED environment variable not set.")
        print(f"Please set it in your {dotenv_path} file or environment.")
        return

    if TEST_ASSIGNEE_SLACK_ID == "U0XXXXXXXXX":
        print("Warning: TEST_SLACK_USER_ID not set. Using placeholder.")
        print("The Slack message might not be delivered to a specific user.")

    headers = {"Content-Type": "application/json"}

    try:
        print(f"Sending test payload to: {WEBHOOK_URL}")
        response = requests.post(WEBHOOK_URL, headers=headers, data=json.dumps(TEST_PAYLOAD))
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        print("\n--- Request Sent ---")
        print(f"Payload: {json.dumps(TEST_PAYLOAD, indent=2)}")
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
    print("--- Testing Make.com Task Created Webhook --- ")
    send_test_request() 