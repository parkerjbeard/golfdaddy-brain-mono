from typing import Dict, Any, Optional, List, Tuple
from supabase import Client
import uuid
from datetime import datetime
from app.integrations.ai_integration import AIIntegration
from app.integrations.clickup_integration import ClickUpIntegration
from app.repositories.task_repository import TaskRepository
from app.models.task import Task
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

class DocGenerationService:
    """Service for generating documentation using AI."""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
        self.task_repository = TaskRepository(supabase)
        self.ai_integration = AIIntegration()
        self.clickup_integration = ClickUpIntegration()
    
    def generate_documentation(self, context: Dict[str, Any], related_task_id: Optional[str] = None) -> Dict[str, Any]:
        """Generates documentation using AI based on provided context.
           Optionally links it to a task and pushes to ClickUp.
        """
        try:
            # 1. Generate documentation using AI
            logger.info(f"Generating documentation with context: {str(context)[:100]}...")
            
            # Extract essential context info
            description = context.get("description", "")
            file_references = context.get("file_references", [])
            doc_type = context.get("doc_type", "general")
            
            # Format the prompt/input for AI
            ai_input = {
                "description": description,
                "files": file_references,
                "doc_type": doc_type
            }
            
            # Generate the doc using AI service
            generated_content = self.ai_integration.generate_doc(ai_input)
            
            if not generated_content:
                logger.error("AI failed to generate documentation.")
                return {"error": "Failed to generate documentation"}

            # Create a title from the content or description
            title = self._extract_title(generated_content) or f"{doc_type.capitalize()} Documentation"
            
            # Generate a unique ID for the document
            doc_id = str(uuid.uuid4())
            
            # Create timestamp
            timestamp = datetime.now().isoformat()
            
            # 2. Store in Supabase docs table
            docs_data = {
                "id": doc_id,
                "title": title,
                "content": generated_content,
                "doc_type": doc_type,
                "created_at": timestamp,
                "related_task_id": related_task_id
            }
            
            # Insert into docs table
            try:
                response = self.supabase.table("docs").insert(docs_data).execute()
                if not response.data:
                    logger.error(f"Failed to save documentation to Supabase: {response.error}")
            except Exception as e:
                logger.error(f"Error saving doc to Supabase: {str(e)}")
            
            logger.info("AI generated documentation successfully.")
            
            # 3. Return the doc data
            return {
                "doc_id": doc_id,
                "title": title,
                "content": generated_content,
                "generated_at": timestamp
            }

        except Exception as e:
            logger.exception(f"Error during documentation generation: {e}")
            return {"error": str(e)}
    
    def save_doc_reference(self, doc_id: str, doc_url: str, 
                          related_task_id: Optional[str] = None) -> bool:
        """
        Save a reference to a generated document.
        
        Args:
            doc_id: The unique identifier for the document
            doc_url: URL where the document is stored (e.g., in ClickUp)
            related_task_id: Optional task ID to associate with the document
            
        Returns:
            Boolean indicating success
        """
        try:
            # Update the doc record with the URL
            self.supabase.table("docs").update({"external_url": doc_url}).eq("id", doc_id).execute()
            
            if related_task_id:
                # Get the task and update it with the doc reference
                task = self.task_repository.get_task_by_id(related_task_id)
                if task:
                    # Update the task with a reference to the doc
                    return self.task_repository.update_task(
                        task_id=related_task_id,
                        update_data={"doc_references": [doc_url]} # This might be appended to existing references in a real impl
                    ) is not None
            
            return True
        except Exception as e:
            logger.exception(f"Error saving doc reference: {e}")
            return False
    
    def handle_iteration(self, doc_id: str, feedback: str) -> Dict[str, Any]:
        """
        Handle iteration on a document based on feedback.
        
        Args:
            doc_id: The unique identifier for the document
            feedback: Feedback on the document that requires changes
            
        Returns:
            Updated document data
        """
        try:
            # Retrieve the original document from Supabase
            response = self.supabase.table("docs").select("*").eq("id", doc_id).single().execute()
            
            if not response.data:
                logger.error(f"Document with ID {doc_id} not found")
                return {"error": "Document not found"}
            
            original_doc = response.data
            original_content = original_doc.get("content", "")
            
            # Send to AI for iteration
            ai_input = {
                "original_content": original_content,
                "feedback": feedback
            }
            
            updated_content = self.ai_integration.update_doc(ai_input)
            
            if not updated_content:
                logger.error("AI failed to update the documentation")
                return {"error": "Failed to update documentation"}
            
            # Update timestamp
            timestamp = datetime.now().isoformat()
            
            # Update in Supabase
            update_data = {
                "content": updated_content,
                "updated_at": timestamp,
                "feedback_history": self._append_feedback_history(original_doc.get("feedback_history", []), feedback)
            }
            
            update_response = self.supabase.table("docs").update(update_data).eq("id", doc_id).execute()
            
            if not update_response.data:
                logger.error(f"Failed to update document in Supabase: {update_response.error}")
                return {"error": "Failed to save updated document"}
            
            # Return updated doc
            return {
                "doc_id": doc_id,
                "title": original_doc.get("title", "Updated Documentation"),
                "content": updated_content,
                "updated_at": timestamp
            }
            
        except Exception as e:
            logger.exception(f"Error handling doc iteration: {e}")
            return {"error": str(e)}
    
    def _extract_title(self, content: str) -> Optional[str]:
        """Extract a title from the generated content, typically from the first markdown heading."""
        try:
            lines = content.strip().split('\n')
            for line in lines:
                # Look for markdown headings
                if line.startswith('# '):
                    return line.replace('# ', '')
            return None
        except Exception:
            return None
    
    def _append_feedback_history(self, existing_history: List[Dict[str, Any]], new_feedback: str) -> List[Dict[str, Any]]:
        """Append new feedback to the document's feedback history."""
        history_item = {
            "timestamp": datetime.now().isoformat(),
            "feedback": new_feedback
        }
        
        if existing_history:
            # Append to existing history
            history_copy = existing_history.copy()
            history_copy.append(history_item)
            return history_copy
        else:
            # Create new history array
            return [history_item]