from fastapi import APIRouter, HTTPException, Depends
from app.integrations.slack import SlackMessage, SlackIntegration
from typing import Dict, Any

router = APIRouter(prefix="/slack", tags=["slack"])

@router.post("/webhook")
async def handle_slack_webhook(message: SlackMessage) -> Dict[str, Any]:
    """
    Handle incoming webhooks from make.com for Slack messages
    """
    try:
        # Process the incoming message
        processed_data = await SlackIntegration.process_message(message)
        
        # Here you can add additional logic like:
        # - Storing the message in a database
        # - Triggering other services
        # - Sending responses back through make.com
        
        return {
            "status": "success",
            "message": "Message processed successfully",
            "data": processed_data
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing Slack message: {str(e)}"
        ) 