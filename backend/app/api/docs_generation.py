from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field

from app.config.supabase_client import get_supabase_client
from app.services.doc_generation_service import DocGenerationService
from supabase import Client

router = APIRouter(prefix="/docs", tags=["documentation"])

# Pydantic models for request/response validation
class DocumentationRequest(BaseModel):
    file_references: Optional[List[str]] = Field(None, description="List of file paths or code snippets to document")
    description: str = Field(..., description="Plain text description of what to document")
    doc_type: str = Field("general", description="Type of documentation (e.g., api, component, architecture)")
    format: str = Field("markdown", description="Output format (markdown, html)")
    related_task_id: Optional[str] = Field(None, description="Optional task ID to associate with this doc")
    git_repo_name: Optional[str] = Field(None, description="Git repository name (owner/repo) to save the document to")
    git_path: Optional[str] = Field(None, description="Path within the Git repository where the document should be saved")

class DocumentationResponse(BaseModel):
    doc_id: str
    title: str
    content: str
    generated_at: str
    git_url: Optional[str] = None

class DocumentationUpdateRequest(BaseModel):
    doc_id: str = Field(..., description="The ID of the document to update")
    feedback: str = Field(..., description="Feedback or instructions for updating the document")

@router.post("", response_model=DocumentationResponse)
def generate_documentation(
    request: DocumentationRequest = Body(...),
    supabase: Client = Depends(get_supabase_client)
):
    """
    Generate documentation using AI.
    
    Takes a description of what to document, generates content using AI.
    Optionally saves the documentation to a Git repository.
    """
    # Initialize service
    doc_service = DocGenerationService(supabase)
    
    # Generate documentation
    generated_doc = doc_service.generate_documentation(
        context={
            "description": request.description,
            "file_references": request.file_references,
            "doc_type": request.doc_type,
            "format": request.format
        },
        related_task_id=request.related_task_id
    )
    
    # Check for errors
    if "error" in generated_doc:
        raise HTTPException(status_code=500, detail=generated_doc["error"])
    
    # Save to Git repository if requested
    git_url = None
    if request.git_repo_name and request.git_path:
        try:
            # Save to Git
            from app.services.documentation_update_service import DocumentationUpdateService
            docs_service = DocumentationUpdateService()
            
            git_result = docs_service.save_to_git_repository(
                repo_name=request.git_repo_name,
                file_path=request.git_path,
                content=generated_doc["content"],
                title=generated_doc["title"],
                commit_message=f"Add documentation: {generated_doc['title']}"
            )
            
            git_url = git_result.get("url")
            
            # Save reference to the Git URL
            if git_url:
                doc_service.save_doc_reference(
                    doc_id=generated_doc["doc_id"],
                    doc_url=git_url,
                    related_task_id=request.related_task_id
                )
                
        except Exception as e:
            # Log the error but continue - we still have the generated doc
            print(f"Error saving to Git repository: {str(e)}")
    
    # Return response
    return {
        "doc_id": generated_doc["doc_id"],
        "title": generated_doc["title"],
        "content": generated_doc["content"],
        "generated_at": generated_doc["generated_at"],
        "git_url": git_url
    }

@router.post("/iterate", response_model=DocumentationResponse)
def iterate_documentation(
    request: DocumentationUpdateRequest = Body(...),
    supabase: Client = Depends(get_supabase_client)
):
    """
    Update a document based on feedback.
    
    Takes the document ID and feedback, then generates an updated version.
    """
    # Initialize service
    doc_service = DocGenerationService(supabase)
    
    # Handle iteration
    updated_doc = doc_service.handle_iteration(
        doc_id=request.doc_id,
        feedback=request.feedback
    )
    
    # Prepare response
    return {
        "doc_id": updated_doc.get("doc_id"),
        "title": updated_doc.get("title", "Updated Documentation"),
        "content": updated_doc.get("content", ""),
        "git_url": None,  # Would update the existing doc in a real implementation
        "generated_at": updated_doc.get("updated_at")
    }

@router.get("/{doc_id}")
def get_documentation(
    doc_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """
    Retrieve a generated document by ID.
    
    This would typically fetch the document from storage.
    In the current implementation, this is a placeholder.
    """
    # This would typically fetch from a database
    # For now, return a placeholder
    return {
        "doc_id": doc_id,
        "title": "Requested Documentation",
        "content": "This is a placeholder. In a real implementation, this would fetch the document from storage.",
        "generated_at": "2023-01-01T00:00:00Z"
    }