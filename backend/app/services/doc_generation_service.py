from typing import Dict, Any, Optional, List, Tuple
from supabase import Client
import uuid
from datetime import datetime
from app.integrations.ai_integration import AIIntegration
from app.repositories.task_repository import TaskRepository
from app.models.task import Task
from uuid import UUID
import logging
from app.core.exceptions import (
    AIIntegrationError,
    DatabaseError,
    ResourceNotFoundError,
    AppExceptionBase # General fallback
)

logger = logging.getLogger(__name__)

class DocGenerationService:
    """Service for generating documentation using AI."""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
        self.task_repository = TaskRepository(supabase)
        self.ai_integration = AIIntegration()
    
    def get_documentation_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a document by its ID from Supabase."""
        try:
            response = self.supabase.table("docs").select("*").eq("id", doc_id).single().execute()
            if response.data:
                return response.data
            else:
                # Log if needed, but caller (API layer) will raise ResourceNotFoundError
                logger.info(f"Document with ID {doc_id} not found in Supabase.")
                return None
        except Exception as e:
            logger.error(f"Error fetching document {doc_id} from Supabase: {str(e)}", exc_info=True)
            # Let caller handle this potential DB issue, or raise DatabaseError here
            raise DatabaseError(f"Failed to fetch document {doc_id}: {str(e)}")

    def generate_documentation(self, context: Dict[str, Any], related_task_id: Optional[str] = None) -> Dict[str, Any]:
        """Generates documentation using AI based on provided context.
           Optionally links it to a task.
        """
        try:
            logger.info(f"Generating documentation with context: {str(context)[:100]}...")
            description = context.get("description", "")
            file_references = context.get("file_references", [])
            doc_type = context.get("doc_type", "general")
            ai_input = {
                "description": description,
                "files": file_references,
                "doc_type": doc_type
            }
            
            generated_content = self.ai_integration.generate_doc(ai_input)
            if not generated_content:
                logger.error("AI failed to generate documentation content.")
                raise AIIntegrationError("AI failed to generate documentation content.")

            title = self._extract_title(generated_content) or f"{doc_type.capitalize()} Documentation"
            doc_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            
            docs_data = {
                "id": doc_id,
                "title": title,
                "content": generated_content,
                "doc_type": doc_type,
                "created_at": timestamp,
                "related_task_id": related_task_id
            }
            
            try:
                response = self.supabase.table("docs").insert(docs_data).execute()
                # Assuming PostgREST client: response.data should contain the inserted record(s)
                # For other clients, success check might differ. PySupabase execute() returns APIResponse.
                # If response.error exists or data is empty list for insert, it failed.
                if hasattr(response, 'error') and response.error:
                    logger.error(f"Failed to save documentation to Supabase: {response.error}")
                    raise DatabaseError(f"Failed to save documentation: {response.error.message}")
                if not response.data: # Check if data is empty (another sign of failure for insert)
                    logger.error("Failed to save documentation to Supabase: No data returned after insert.")
                    raise DatabaseError("Failed to save documentation: No data returned after insert.")
            except Exception as db_exc:
                logger.error(f"Error saving doc to Supabase: {str(db_exc)}", exc_info=True)
                raise DatabaseError(f"Database error while saving documentation: {str(db_exc)}")
            
            logger.info(f"AI generated and saved documentation {doc_id} successfully.")
            return {
                "doc_id": doc_id,
                "title": title,
                "content": generated_content,
                "generated_at": timestamp
            }

        except AIIntegrationError: # Re-raise specific AI errors
            raise
        except DatabaseError: # Re-raise specific DB errors
            raise
        except Exception as e:
            logger.error(f"Error during documentation generation: {e}", exc_info=True)
            raise AppExceptionBase(f"An unexpected error occurred during documentation generation: {str(e)}")
    
    def save_doc_reference(self, doc_id: str, doc_url: str, 
                          related_task_id: Optional[str] = None) -> bool:
        """
        Save a reference to a generated document.
        """
        try:
            update_resp = self.supabase.table("docs").update({"external_url": doc_url}).eq("id", doc_id).execute()
            if hasattr(update_resp, 'error') and update_resp.error:
                 logger.error(f"Failed to update doc {doc_id} with external_url in Supabase: {update_resp.error}")
                 raise DatabaseError(f"Failed to save doc reference URL for {doc_id}: {update_resp.error.message}")
            # Some Supabase client versions might not return data on update, so check error primarily
            
            if related_task_id:
                task = self.task_repository.get_task_by_id(UUID(related_task_id)) # Ensure UUID
                if not task:
                    logger.warning(f"Task {related_task_id} not found when trying to link doc {doc_id}.")
                    # Decide: raise ResourceNotFoundError or just log and return success for doc part?
                    # For now, let's consider doc part successful and log task issue.
                elif self.task_repository.update_task(
                        task_id=UUID(related_task_id),
                        update_data={"doc_references": [doc_url]} # This might be appended
                    ) is None:
                    logger.error(f"Failed to update task {related_task_id} with doc reference {doc_url}.")
                    # This is a partial failure. Doc URL saved, task link failed.
                    raise DatabaseError(f"Saved doc URL, but failed to link to task {related_task_id}.")
            return True
        except DatabaseError: # Re-raise if already a DatabaseError
            raise
        except Exception as e:
            logger.error(f"Error saving doc reference for {doc_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error saving doc reference for {doc_id}: {str(e)}")
    
    def handle_iteration(self, doc_id: str, feedback: str) -> Dict[str, Any]:
        """
        Handle iteration on a document based on feedback.
        """
        try:
            original_doc = self.get_documentation_by_id(doc_id)
            if not original_doc:
                # get_documentation_by_id logs, API layer raises ResourceNotFoundError if it gets None
                # However, if this service calls it and gets None, it should raise here.
                raise ResourceNotFoundError(resource_name="Document", resource_id=doc_id)
            
            original_content = original_doc.get("content", "")
            ai_input = {"original_content": original_content, "feedback": feedback}
            updated_content = self.ai_integration.update_doc(ai_input)
            
            if not updated_content:
                logger.error(f"AI failed to update documentation for doc {doc_id}.")
                raise AIIntegrationError("AI failed to update documentation content based on feedback.")
            
            timestamp = datetime.now().isoformat()
            update_data = {
                "content": updated_content,
                "updated_at": timestamp,
                "feedback_history": self._append_feedback_history(original_doc.get("feedback_history", []), feedback)
            }
            
            update_response = self.supabase.table("docs").update(update_data).eq("id", doc_id).execute()
            if hasattr(update_response, 'error') and update_response.error:
                logger.error(f"Failed to update document {doc_id} in Supabase after iteration: {update_response.error}")
                raise DatabaseError(f"Failed to save updated document {doc_id}: {update_response.error.message}")
            # Check if data is empty for update response might not be reliable, error is better.
            if not update_response.data: # For some clients, data might be empty on successful update if returning='minimal'
                logger.warning(f"Supabase update for doc {doc_id} returned no data. Assuming success if no error object.")

            return {
                "doc_id": doc_id,
                "title": original_doc.get("title", "Updated Documentation"),
                "content": updated_content,
                "updated_at": timestamp
            }
        except (ResourceNotFoundError, AIIntegrationError, DatabaseError): # Re-raise known
            raise
        except Exception as e:
            logger.error(f"Error handling doc iteration for {doc_id}: {e}", exc_info=True)
            raise AppExceptionBase(f"Unexpected error during document iteration for {doc_id}: {str(e)}")
    
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