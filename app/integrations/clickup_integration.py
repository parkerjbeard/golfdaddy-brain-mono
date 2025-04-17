from typing import Dict, Any, Optional, List
import requests
import json
import os
from datetime import datetime

from app.config.settings import settings

class ClickUpIntegration:
    """Integration with ClickUp API for documentation management (using Tasks)."""
    
    def __init__(self):
        """Initialize the ClickUp integration with token from settings."""
        self.token = settings.clickup_token
        self.base_url = "https://api.clickup.com/api/v2"
        if not self.token:
            # Consider logging a warning or raising an error if the token is essential at init
            print("Warning: ClickUp token is not configured in settings.")
            
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Helper method to make requests to the ClickUp API."""
        if not self.token:
            raise ValueError("ClickUp API token is missing.")
            
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": self.token,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            return response.json()
        except requests.exceptions.RequestException as e:
            # Log the error details (consider using a proper logger)
            print(f"ClickUp API request failed: {e}")
            if e.response is not None:
                print(f"Response status: {e.response.status_code}")
                try:
                    print(f"Response body: {e.response.json()}")
                except json.JSONDecodeError:
                    print(f"Response body: {e.response.text}")
            # Re-raise or return a structured error
            raise  # Or return an error dictionary: {"error": True, "message": str(e)}

    def create_doc_in_clickup(self, title: str, content: str, list_id: str,
                             tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Create a new task in ClickUp to represent a document.
        
        Args:
            title: Document title (Task name)
            content: Document content (Task description in Markdown)
            list_id: ClickUp list ID to add the task to
            tags: Optional tags to apply to the task
            
        Returns:
            Dictionary with the ClickUp API response for the created task.
        """
        endpoint = f"/list/{list_id}/task"
        payload = {
            "name": title,
            "markdown_description": content,
            "tags": tags or []
        }
        
        # Note: folder_id is typically managed by assigning the list_id to a list within that folder.
        # Creating tasks doesn't usually take a folder_id directly.
        
        print(f"Creating ClickUp task in list {list_id}: {title}")
        return self._make_request("POST", endpoint, json=payload)

    def update_doc(self, task_id: str, title: Optional[str] = None,
                  content: Optional[str] = None,
                  tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Update an existing task (document) in ClickUp.
        
        Args:
            task_id: Task ID representing the document to update
            title: Optional new title (Task name)
            content: Optional new content (Task description in Markdown)
            tags: Optional list of tags to set (replaces existing tags if provided)
            
        Returns:
            Dictionary with the ClickUp API response for the updated task.
        """
        endpoint = f"/task/{task_id}"
        payload = {}
        if title is not None:
            payload["name"] = title
        if content is not None:
            payload["markdown_description"] = content
        # Note: Updating tags might require specific handling depending on whether 
        # you want to add, remove, or replace tags. This implementation replaces them.
        if tags is not None:
            payload["tags"] = tags
            
        if not payload:
            print(f"No updates provided for ClickUp task {task_id}.")
            # Or query the existing task and return it
            return self.get_task(task_id) # Requires a get_task method

        print(f"Updating ClickUp task {task_id}: {payload.keys()}")
        return self._make_request("PUT", endpoint, json=payload)
        
    def get_task(self, task_id: str) -> Dict[str, Any]:
        """
        Retrieve details of a specific task from ClickUp.

        Args:
            task_id: The ID of the task to retrieve.

        Returns:
            Dictionary with the ClickUp API response for the task.
        """
        endpoint = f"/task/{task_id}"
        print(f"Fetching ClickUp task {task_id}")
        return self._make_request("GET", endpoint)

    def handle_auth(self) -> bool:
        """
        Verify authentication with ClickUp by fetching user info.
        
        Returns:
            Boolean indicating if authentication is valid.
        """
        if not self.token:
            return False
            
        try:
            # Make a simple request to verify the token
            self._make_request("GET", "/user")
            print("ClickUp authentication successful.")
            return True
        except Exception as e:
            print(f"ClickUp authentication failed: {e}")
            return False

# Example Usage (Optional - for testing purposes)
# if __name__ == "__main__":
#     # Ensure you have a .env file with CLICKUP_TOKEN defined
#     # or set it as an environment variable
#     from dotenv import load_dotenv
#     load_dotenv()
#     # Assuming settings are loaded correctly, perhaps via an init function or directly
#     # For example:
#     # from app.config.settings import load_settings
#     # load_settings()

#     if not settings.clickup_token:
#         print("Skipping ClickUp example: CLICKUP_TOKEN not set in environment or .env file.")
#     else:
#         clickup = ClickUpIntegration()
#         
#         if clickup.handle_auth():
#             print("Auth check passed.")
#             
#             # !!! IMPORTANT: Replace with a valid List ID from your ClickUp workspace !!!
#             test_list_id = "YOUR_LIST_ID" 
#             
#             if test_list_id == "YOUR_LIST_ID":
#                 print("Please replace 'YOUR_LIST_ID' with an actual ClickUp List ID to run create/update examples.")
#             else:
#                 try:
#                     # --- Create Example ---
#                     print("\n--- Attempting to Create Task ---")
#                     created_task = clickup.create_doc_in_clickup(
#                         title="Test Doc from Integration",
#                         content="## Hello World!\n\nThis is a test document created via API.",
#                         list_id=test_list_id,
#                         tags=["api-test", "generated"]
#                     )
#                     print("\n--- Created Task ---")
#                     print(json.dumps(created_task, indent=2))
#                     task_id_to_update = created_task.get("id")
# 
#                     if task_id_to_update:
#                         # --- Update Example ---
#                         print(f"\n--- Attempting to Update Task {task_id_to_update} ---")
#                         updated_task = clickup.update_doc(
#                             task_id=task_id_to_update,
#                             title="Test Doc - UPDATED",
#                             content="## Updated Content\n\nThe content has been modified.",
#                             tags=["api-test", "updated"]
#                         )
#                         print("\n--- Updated Task ---")
#                         print(json.dumps(updated_task, indent=2))
#                         
#                         # --- Get Example ---
#                         print(f"\n--- Attempting to Get Task {task_id_to_update} ---")
#                         fetched_task = clickup.get_task(task_id=task_id_to_update)
#                         print("\n--- Fetched Task ---")
#                         print(json.dumps(fetched_task, indent=2))
#                         
#                 except Exception as e:
#                     print(f"\nAn error occurred during ClickUp example execution: {e}")
#         else:
#             print("Auth check failed. Cannot proceed with examples.")