from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import json

from app.config.database import get_db
from app.integrations.slack_integration import SlackIntegration
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.services.raci_service import RaciService
from app.services.notification_service import NotificationService
from app.models.task import TaskStatus

router = APIRouter(prefix="/slack", tags=["slack"])

# Initialize integrations
slack_integration = SlackIntegration()

@router.post("/event")
async def slack_event(request: Request, db: Session = Depends(get_db),
                     x_slack_signature: str = Header(None),
                     x_slack_request_timestamp: str = Header(None)):
    """
    Handle Slack events and slash commands.
    
    This endpoint processes:
    - Slash commands for task creation/management
    - Interactive components (buttons, menus)
    - Event subscriptions
    """
    # Get raw request body for signature verification
    body = await request.body()
    body_str = body.decode("utf-8")
    
    # Verify Slack signature (if not using Make.com)
    if x_slack_signature and x_slack_request_timestamp:
        if not slack_integration.signature_verification(
            x_slack_signature, x_slack_request_timestamp, body_str
        ):
            raise HTTPException(status_code=401, detail="Invalid Slack signature")
    
    try:
        # Parse request body as JSON or form data
        if request.headers.get("content-type") == "application/json":
            payload = await request.json()
        else:
            # Handle form data (common for slash commands)
            form_data = await request.form()
            payload = dict(form_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request format: {str(e)}")
    
    # Parse Slack payload
    parsed_payload = slack_integration.parse_slack_payload(payload)
    
    # Initialize repositories and services
    task_repository = TaskRepository(db)
    user_repository = UserRepository(db)
    raci_service = RaciService(db)
    notification_service = NotificationService(db)
    
    # Handle URL verification challenge (for Events API)
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}
    
    # Handle different types of events
    event_type = parsed_payload.get("type")
    
    if event_type == "command":
        # Handle slash command
        command = parsed_payload.get("command")
        text = parsed_payload.get("text", "")
        user_id = parsed_payload.get("user_id")
        
        # Find user by Slack ID
        user = user_repository.get_user_by_slack_id(user_id)
        
        if not user:
            return JSONResponse(
                content={"text": "You don't have an account in the system. Please contact an admin."},
                status_code=200
            )
        
        # Handle /task command for task creation
        if command == "/task":
            # Basic parsing - in real app would have more sophisticated parsing
            parts = text.split("|")
            
            if len(parts) < 1:
                return JSONResponse(
                    content={"text": "Please provide a task description: `/task Description | @responsible | @accountable`"},
                    status_code=200
                )
            
            description = parts[0].strip()
            
            # Default responsible and accountable to the command issuer
            responsible_id = user.id
            accountable_id = user.id
            
            # Parse mentions for RACI roles
            if len(parts) > 1 and parts[1].strip():
                responsible_slack_id = parts[1].strip().replace("@", "")
                responsible_user = user_repository.get_user_by_slack_id(responsible_slack_id)
                if responsible_user:
                    responsible_id = responsible_user.id
            
            if len(parts) > 2 and parts[2].strip():
                accountable_slack_id = parts[2].strip().replace("@", "")
                accountable_user = user_repository.get_user_by_slack_id(accountable_slack_id)
                if accountable_user:
                    accountable_id = accountable_user.id
            
            # Create task with RACI roles
            try:
                task, warnings = raci_service.assign_raci(
                    description=description,
                    assignee_id=responsible_id,
                    responsible_id=responsible_id,
                    accountable_id=accountable_id
                )
                
                # Send notification to assignee
                notification_service.task_created_notification(task.id)
                
                # Build response message
                warning_text = "\n".join(warnings) if warnings else ""
                
                return JSONResponse(
                    content={
                        "text": f"Task created: {description}" + (f"\n{warning_text}" if warning_text else "")
                    },
                    status_code=200
                )
            except Exception as e:
                return JSONResponse(
                    content={"text": f"Error creating task: {str(e)}"},
                    status_code=200
                )
        
        # Handle /block command for marking tasks as blocked
        elif command == "/block":
            parts = text.split("|")
            
            if len(parts) < 2:
                return JSONResponse(
                    content={"text": "Please provide a task ID and reason: `/block task_id | blocking reason`"},
                    status_code=200
                )
            
            task_id = parts[0].strip()
            blocking_reason = parts[1].strip()
            
            # Escalate the blocked task
            success, message = raci_service.escalate_blocked_task(task_id, blocking_reason)
            
            return JSONResponse(
                content={"text": message},
                status_code=200
            )
    
    elif event_type == "event":
        # Handle Events API events (e.g., message events)
        event_subtype = parsed_payload.get("event_type")
        
        if event_subtype == "message":
            # Example: Process messages for a Slack bot
            # This would likely be handled by Make.com in the outlined system
            pass
    
    elif event_type == "interactive":
        # Handle interactive components (e.g., button clicks)
        action_type = parsed_payload.get("action_type")
        actions = parsed_payload.get("actions", [])
        
        if action_type == "block_actions" and actions:
            action_id = actions[0].get("action_id", "")
            
            if action_id.startswith("task_complete_"):
                # Handle task completion button
                task_id = action_id.replace("task_complete_", "")
                task_repository.update_task_status(task_id, TaskStatus.COMPLETED)
                
                return JSONResponse(
                    content={"text": "Task marked as completed!"},
                    status_code=200
                )
    
    # Default response for unhandled events
    return JSONResponse(content={"status": "processed"}, status_code=200)