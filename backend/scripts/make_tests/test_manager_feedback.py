import os
import requests
import json
import time
import uuid
from dotenv import load_dotenv

# Load environment variables from .env file in the workspace root
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
dotenv_path = os.path.join(workspace_root, '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- Configuration ---
# Get webhook URL from environment variable
WEBHOOK_URL_MANAGER_MASTERY = os.getenv("MAKE_WEBHOOK_MANAGER_MASTERY")

# Replace with a REAL Slack User ID for testing
TEST_MANAGER_SLACK_ID = os.getenv("TEST_SLACK_USER_ID", "U0XXXXXXXXX")
TEST_EMPLOYEE_SLACK_ID = os.getenv("TEST_EMPLOYEE_SLACK_ID", "U0XXXXXXXXX")
TEST_DIRECTOR_SLACK_ID = os.getenv("TEST_DIRECTOR_SLACK_ID", "U0XXXXXXXXX")
TEST_PEER_SLACK_ID = os.getenv("TEST_PEER_SLACK_ID", "U0XXXXXXXXX")

# RACI Types
RACI_TYPES = {
    "responsible": "The person who does the work to complete the task",
    "accountable": "The person ultimately answerable for the completion of the task",
    "consulted": "People whose opinions are sought before execution",
    "informed": "People who are kept up-to-date on progress"
}

# Development Areas
DEVELOPMENT_AREAS = [
    "strategic_thinking",
    "team_leadership",
    "communication",
    "decision_making",
    "conflict_resolution",
    "delegation",
    "coaching",
    "feedback_delivery",
    "business_acumen",
    "change_management"
]

# --- Task Templates ---

# RACI Development Task Template
def create_management_development_task(task_type, development_area, task_title, task_description):
    """Creates a management development task with full RACI implementation"""
    
    # Generate a unique task ID
    task_id = f"mgmt-dev-{uuid.uuid4().hex[:8]}"
    
    # Base payload with all RACI roles
    payload = {
        # Task identification
        "task_id": task_id,
        "task_type": task_type,
        "title": task_title,
        "description": task_description,
        "development_area": development_area,
        
        # Timestamps
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "due_date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 7*24*60*60)),  # 1 week from now
        "timestamp": time.time(),
        
        # RACI Structure - IDs will be populated based on task type
        "responsible_id": "",
        "responsible_slack_id": "",
        "responsible_name": "",
        
        "accountable_id": "",
        "accountable_slack_id": "",
        "accountable_name": "",
        
        "consulted_ids": [],
        "consulted_slack_ids": [],
        "consulted_names": [],
        
        "informed_ids": [],
        "informed_slack_ids": [],
        "informed_names": [],
        
        # Status tracking
        "status": "created",
        "progress": 0,
        "completion_criteria": [],
        "feedback_received": False
    }
    
    return payload

# --- Specific Task Types ---

def create_milestone_task(development_area):
    """Creates a milestone task where manager is responsible, director is accountable"""
    title = f"Complete {development_area.replace('_', ' ').title()} Assessment"
    description = f"Conduct a self-assessment of your {development_area.replace('_', ' ')} skills and identify 3 areas for improvement."
    
    payload = create_management_development_task("milestone", development_area, title, description)
    
    # RACI Assignment:
    # Manager is responsible for completing the milestone
    payload["responsible_id"] = "test-manager-uuid-12345"
    payload["responsible_slack_id"] = TEST_MANAGER_SLACK_ID
    payload["responsible_name"] = "Test Manager"
    
    # Director is accountable for ensuring it happens
    payload["accountable_id"] = "test-director-uuid-67890"
    payload["accountable_slack_id"] = TEST_DIRECTOR_SLACK_ID
    payload["accountable_name"] = "Test Director"
    
    # HR or L&D might be consulted
    payload["consulted_ids"] = ["test-hr-uuid-12345"]
    payload["consulted_slack_ids"] = [TEST_PEER_SLACK_ID]
    payload["consulted_names"] = ["HR Partner"]
    
    # Team members might be informed
    payload["informed_ids"] = ["test-employee-uuid-54321"]
    payload["informed_slack_ids"] = [TEST_EMPLOYEE_SLACK_ID]
    payload["informed_names"] = ["Direct Report"]
    
    # Specific milestone data
    payload["completion_criteria"] = [
        "Complete self-assessment document",
        "Identify 3 specific improvement areas",
        "Schedule review meeting with director"
    ]
    
    return payload

def create_development_task(development_area):
    """Creates a development task where manager is both responsible and accountable"""
    title = f"Implement {development_area.replace('_', ' ').title()} Practice"
    description = f"Apply a new {development_area.replace('_', ' ')} technique with your team and document the results."
    
    payload = create_management_development_task("development", development_area, title, description)
    
    # RACI Assignment:
    # Manager is responsible for the development activity
    payload["responsible_id"] = "test-manager-uuid-12345"
    payload["responsible_slack_id"] = TEST_MANAGER_SLACK_ID
    payload["responsible_name"] = "Test Manager"
    
    # Manager is also accountable (self-development)
    payload["accountable_id"] = "test-manager-uuid-12345"
    payload["accountable_slack_id"] = TEST_MANAGER_SLACK_ID
    payload["accountable_name"] = "Test Manager"
    
    # Director and peer managers might be consulted
    payload["consulted_ids"] = ["test-director-uuid-67890", "test-peer-uuid-24680"]
    payload["consulted_slack_ids"] = [TEST_DIRECTOR_SLACK_ID, TEST_PEER_SLACK_ID]
    payload["consulted_names"] = ["Test Director", "Peer Manager"]
    
    # Team members are informed
    payload["informed_ids"] = ["test-employee-uuid-54321"]
    payload["informed_slack_ids"] = [TEST_EMPLOYEE_SLACK_ID]
    payload["informed_names"] = ["Direct Report"]
    
    # Specific development data
    payload["completion_criteria"] = [
        "Research and select appropriate technique",
        "Implement with team for at least 2 weeks",
        "Document outcomes and learnings"
    ]
    
    return payload

def create_feedback_task(development_area):
    """Creates a feedback task where director is responsible, manager is consulted/informed"""
    title = f"Provide Feedback on {development_area.replace('_', ' ').title()}"
    description = f"Observe and provide structured feedback on the manager's {development_area.replace('_', ' ')} skills."
    
    payload = create_management_development_task("feedback", development_area, title, description)
    
    # RACI Assignment:
    # Director is responsible for giving feedback
    payload["responsible_id"] = "test-director-uuid-67890"
    payload["responsible_slack_id"] = TEST_DIRECTOR_SLACK_ID
    payload["responsible_name"] = "Test Director"
    
    # Director is also accountable for this task
    payload["accountable_id"] = "test-director-uuid-67890"
    payload["accountable_slack_id"] = TEST_DIRECTOR_SLACK_ID
    payload["accountable_name"] = "Test Director"
    
    # Manager is consulted during the feedback process
    payload["consulted_ids"] = ["test-manager-uuid-12345"]
    payload["consulted_slack_ids"] = [TEST_MANAGER_SLACK_ID]
    payload["consulted_names"] = ["Test Manager"]
    
    # HR might be informed
    payload["informed_ids"] = ["test-hr-uuid-12345"]
    payload["informed_slack_ids"] = [TEST_PEER_SLACK_ID]
    payload["informed_names"] = ["HR Partner"]
    
    # Specific feedback data
    payload["completion_criteria"] = [
        "Observe manager in relevant situation",
        "Document specific examples",
        "Deliver feedback in 1:1 session",
        "Create action plan based on feedback"
    ]
    
    return payload

def send_test_request(payload):
    """Sends the test JSON payload to the configured Make.com webhook URL."""
    webhook_url = WEBHOOK_URL_MANAGER_MASTERY
    env_var_name = "MAKE_WEBHOOK_MANAGER_MASTERY"

    if not webhook_url:
        print(f"Error: {env_var_name} environment variable not set.")
        print(f"Please set it in your {dotenv_path} file or environment.")
        return False

    # Verify required Slack IDs are set
    if TEST_MANAGER_SLACK_ID == "U0XXXXXXXXX":
        print("Warning: TEST_SLACK_USER_ID not set. Using placeholder.")
    
    if TEST_EMPLOYEE_SLACK_ID == "U0XXXXXXXXX":
        print("Warning: TEST_EMPLOYEE_SLACK_ID not set. Using placeholder.")
    
    if TEST_DIRECTOR_SLACK_ID == "U0XXXXXXXXX":
        print("Warning: TEST_DIRECTOR_SLACK_ID not set. Using placeholder.")

    headers = {"Content-Type": "application/json"}

    try:
        task_type = payload.get("task_type", "unknown")
        print(f"Sending {task_type} task for {payload['development_area']} to webhook: {webhook_url}")
        print("\nRACI Roles:")
        print(f"Responsible: {payload['responsible_name']} ({payload['responsible_slack_id']})")
        print(f"Accountable: {payload['accountable_name']} ({payload['accountable_slack_id']})")
        print(f"Consulted: {', '.join(payload['consulted_names'])}")
        print(f"Informed: {', '.join(payload['informed_names'])}")
        
        response = requests.post(webhook_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        print("\n--- Request Sent ---")
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")

        if response.status_code == 200 and response.text.lower() == "accepted":
            print("\nSuccess: Make.com accepted the webhook data.")
            print("Check your Make.com scenario history and Slack for the message.")
            return True
        else:
            print("\nWarning: Received non-standard success response from Make.com.")
            return False

    except requests.exceptions.RequestException as e:
        print(f"\nError sending request: {e}")
        return False
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        return False

def create_development_plan(manager_name, development_areas):
    """Creates a complete development plan with milestone, development, and feedback tasks"""
    print(f"\nCreating development plan for {manager_name} with {len(development_areas)} focus areas...")
    
    successful_sends = 0
    
    for area in development_areas:
        print(f"\n=== Development Area: {area.replace('_', ' ').title()} ===")
        
        # Create milestone task (assessment/goal setting)
        milestone_payload = create_milestone_task(area)
        print("\n>> Sending Milestone Task...")
        if send_test_request(milestone_payload):
            successful_sends += 1
        
        # Create development task (practice/implementation)
        development_payload = create_development_task(area)
        print("\n>> Sending Development Task...")
        if send_test_request(development_payload):
            successful_sends += 1
        
        # Create feedback task (evaluation/coaching)
        feedback_payload = create_feedback_task(area)
        print("\n>> Sending Feedback Task...")
        if send_test_request(feedback_payload):
            successful_sends += 1
    
    print(f"\nDevelopment plan creation complete. Successfully sent {successful_sends} tasks.")

if __name__ == "__main__":
    print("\n=== Manager Development RACI System ===")
    print("This tool creates a structured management development program with RACI accountability")
    
    # Option 1: Create a single task
    # Option 2: Create a complete development plan
    mode = input("\nSelect mode:\n1. Send individual development task\n2. Create complete development plan\nEnter choice (default: 1): ") or "1"
    
    if mode == "1":
        # Individual task creation
        print("\n--- Available Development Areas ---")
        for i, area in enumerate(DEVELOPMENT_AREAS, 1):
            print(f"{i}. {area.replace('_', ' ').title()}")
        
        area_choice = input(f"\nSelect development area (1-{len(DEVELOPMENT_AREAS)}, default: 1): ") or "1"
        try:
            area_index = int(area_choice) - 1
            if 0 <= area_index < len(DEVELOPMENT_AREAS):
                selected_area = DEVELOPMENT_AREAS[area_index]
            else:
                selected_area = DEVELOPMENT_AREAS[0]
        except ValueError:
            selected_area = DEVELOPMENT_AREAS[0]
        
        print(f"\nSelected area: {selected_area.replace('_', ' ').title()}")
        
        task_type = input("\nSelect task type:\n1. Milestone Task\n2. Development Task\n3. Feedback Task\nEnter choice (default: 1): ") or "1"
        
        if task_type == "1":
            print("\n--- Creating Milestone Task ---")
            payload = create_milestone_task(selected_area)
            send_test_request(payload)
        elif task_type == "2":
            print("\n--- Creating Development Task ---")
            payload = create_development_task(selected_area)
            send_test_request(payload)
        elif task_type == "3":
            print("\n--- Creating Feedback Task ---")
            payload = create_feedback_task(selected_area)
            send_test_request(payload)
        else:
            print("\nInvalid selection. Using default (Milestone Task).")
            payload = create_milestone_task(selected_area)
            send_test_request(payload)
    
    elif mode == "2":
        # Complete development plan creation
        print("\n--- Creating Complete Development Plan ---")
        print("\nHow many development areas should be included?")
        num_areas = input("Enter number (1-3, default: 1): ") or "1"
        
        try:
            num = min(max(int(num_areas), 1), 3)  # Between 1 and 3
        except ValueError:
            num = 1
        
        # Allow selection of specific areas
        print("\n--- Available Development Areas ---")
        for i, area in enumerate(DEVELOPMENT_AREAS, 1):
            print(f"{i}. {area.replace('_', ' ').title()}")
        
        selected_areas = []
        for i in range(num):
            prompt = f"\nSelect development area #{i+1} (1-{len(DEVELOPMENT_AREAS)}): "
            area_choice = input(prompt)
            try:
                area_index = int(area_choice) - 1
                if 0 <= area_index < len(DEVELOPMENT_AREAS):
                    selected_areas.append(DEVELOPMENT_AREAS[area_index])
                else:
                    # Pick a default not already selected
                    for area in DEVELOPMENT_AREAS:
                        if area not in selected_areas:
                            selected_areas.append(area)
                            break
            except ValueError:
                # Pick a default not already selected
                for area in DEVELOPMENT_AREAS:
                    if area not in selected_areas:
                        selected_areas.append(area)
                        break
        
        create_development_plan("Test Manager", selected_areas)
    
    else:
        print("\nInvalid mode selection. Exiting.") 