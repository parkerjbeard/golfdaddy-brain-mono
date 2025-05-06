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
# Get webhook URL from environment variable
WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_MASTERY_REMINDER")

# Replace with a REAL Slack User ID for testing
TEST_MANAGER_SLACK_ID = os.getenv("TEST_SLACK_USER_ID", "U0XXXXXXXXX")

# Test payloads that match our notification service implementation
MILESTONE_TRACKING_PAYLOAD = {
    "manager_id": "test-manager-uuid-12345",
    "manager_slack_id": TEST_MANAGER_SLACK_ID,
    "manager_name": "Test Manager",
    "milestone_id": "milestone-123",
    "milestone_description": "Launch the new user onboarding flow",
    "milestone_month": "August 2024",
    "milestone_status": "in_progress",
    "milestone_notes": "On track for delivery by end of month",
    "last_checkin_date": "2024-08-15T14:30:00Z",
    "timestamp": time.time()
}

MANAGER_FEEDBACK_PAYLOAD = {
    "manager_id": "test-manager-uuid-12345",
    "manager_slack_id": TEST_MANAGER_SLACK_ID,
    "manager_name": "Test Manager",
    "feedback_id": "feedback-123",
    "improvement_area": "Team delegation",
    "feedback_details": "Could improve distribution of tasks among team members to avoid bottlenecks",
    "provided_by": "Daniel",
    "action_items": [
        "Create a task assignment matrix",
        "Schedule 1:1s with team leads to discuss workload balance"
    ],
    "send_reminder": True,
    "timestamp": time.time()
}

TASK_ACHIEVEMENT_PAYLOAD = {
    "manager_id": "test-manager-uuid-12345",
    "manager_slack_id": TEST_MANAGER_SLACK_ID,
    "manager_name": "Test Manager",
    "achievement_id": "achievement-123",
    "achievement_title": "Fixed login page bug",
    "customer_value": "Customers no longer experience frustration when trying to log in on mobile devices",
    "achievement_type": "bug",
    "completed_by": "Jane Developer",
    "completion_date": "2024-08-16T10:15:00Z",
    "timestamp": time.time()
}
# ---

def send_test_request(payload_to_send, test_type="milestone"):
    """Sends the test JSON payload to the configured Make.com webhook URL."""
    if not WEBHOOK_URL:
        print("Error: MAKE_WEBHOOK_MASTERY_REMINDER environment variable not set.")
        print(f"Please set it in your {dotenv_path} file or environment.")
        return

    if TEST_MANAGER_SLACK_ID == "U0XXXXXXXXX":
        print("Warning: TEST_SLACK_USER_ID not set. Using placeholder.")
        print("The Slack message might not be delivered to a specific manager.")

    headers = {"Content-Type": "application/json"}

    try:
        print(f"Sending {test_type} test payload to: {WEBHOOK_URL}")
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
    test_type = input("What would you like to test?\n1. Milestone tracking\n2. Manager feedback\n3. Task achievement\nEnter number (default: 1): ") or "1"
    
    if test_type == "1":
        print("\n--- Testing Make.com Milestone Tracking Webhook --- ")
        send_test_request(MILESTONE_TRACKING_PAYLOAD, "milestone")
    elif test_type == "2":
        print("\n--- Testing Make.com Manager Feedback Webhook --- ")
        send_test_request(MANAGER_FEEDBACK_PAYLOAD, "manager feedback")
    elif test_type == "3":
        print("\n--- Testing Make.com Task Achievement Webhook --- ")
        send_test_request(TASK_ACHIEVEMENT_PAYLOAD, "task achievement")
    else:
        print("\nInvalid selection. Using default (milestone tracking).")
        send_test_request(MILESTONE_TRACKING_PAYLOAD, "milestone") 