import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env file in the workspace root
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
dotenv_path = os.path.join(workspace_root, '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- Configuration ---
# Get webhook URL from environment variable
WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_EOD_REMINDER")

# Replace with a REAL Slack User ID to receive the EOD summary
TEST_USER_SLACK_ID = os.getenv("TEST_SLACK_USER_ID", "U0XXXXXXXXX")

# Test payload structure
TEST_PAYLOAD = {
    "user_slack_id": TEST_USER_SLACK_ID,
    "user_name": "Test User EOD",
    "tasks_summary": [
        {
            "id": "eod-task-1",
            "description": "Finalize presentation slides for tomorrow morning.",
            "status": "in_progress",
            "due_date": "2024-07-26T09:00:00Z"
        },
        {
            "id": "eod-task-2",
            "description": "Review pull request #42.",
            "status": "pending",
            "due_date": None
        },
        {
            "id": "eod-task-3",
            "description": "Submit timesheet for the week.",
            "status": "assigned",
            "due_date": "2024-07-26T17:00:00Z"
        }
    ]
}

# Example payload for a user with NO active tasks
TEST_PAYLOAD_NO_TASKS = {
    "user_slack_id": TEST_USER_SLACK_ID,
    "user_name": "Test User EOD Empty",
    "tasks_summary": []
}
# ---

def send_test_request(payload_to_send=TEST_PAYLOAD):
    """Sends the test JSON payload to the configured Make.com webhook URL."""
    if not WEBHOOK_URL:
        print("Error: MAKE_WEBHOOK_EOD_REMINDER environment variable not set.")
        print(f"Please set it in your {dotenv_path} file or environment.")
        return

    if TEST_USER_SLACK_ID == "U0XXXXXXXXX":
        print("Warning: TEST_SLACK_USER_ID not set. Using placeholder.")
        print("The Slack message might not be delivered to a specific user.")

    headers = {"Content-Type": "application/json"}

    try:
        print(f"Sending test payload to: {WEBHOOK_URL}")
        response = requests.post(WEBHOOK_URL, headers=headers, data=json.dumps(payload_to_send))
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
    print("--- Testing Make.com EOD Reminder Webhook --- ")
    send_test_request(TEST_PAYLOAD)

    # Optional: Test the case with no tasks
    # print("\n--- Testing Make.com EOD Reminder Webhook (No Tasks) --- ")
    # send_test_request(TEST_PAYLOAD_NO_TASKS) 