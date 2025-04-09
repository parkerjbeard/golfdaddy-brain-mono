from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.config.database import get_db
from app.services.doc_generation_service import DocGenerationService
from app.integrations.clickup_integration import ClickUpIntegration

router = APIRouter(prefix="/docs", tags=["documentation"])

# Initialize integrations
clickup_integration = ClickUpIntegration()

# Pydantic models for request/response validation
class DocumentationRequest(BaseModel):
    file_references: Optional[List[str]] = Field(None, description="List of file paths or code snippets to document")
    description: str = Field(..., description="Plain text description of what to document")
    doc_type: str = Field("general", description="Type of documentation (e.g., api, component, architecture)")
    format: str = Field("markdown", description="Output format (markdown, html)")
    related_task_id: Optional[str] = Field(None, description="Optional task ID to associate with this doc")
    clickup_list_id: Optional[str] = Field(None, description="ClickUp list ID to save the document to")

class DocumentationResponse(BaseModel):
    doc_id: str
    title: str
    content: str
    clickup_url: Optional[str] = None
    generated_at: str

class DocumentationUpdateRequest(BaseModel):
    doc_id: str
    feedback: str = Field(..., description="Feedback or requested changes for the document")
    
@router.post("/generate", response_model=DocumentationResponse)
def generate_documentation(
    request: DocumentationRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Generate documentation from minimal input using AI.
    
    Takes descriptions and file references and generates structured documentation.
    Optionally saves the documentation to ClickUp.
    """
    # Initialize service
    doc_service = DocGenerationService(db)
    
    # Prepare context for doc generation
    context = {
        "file_references": request.file_references,
        "description": request.description,
        "doc_type": request.doc_type,
        "format": request.format
    }
    
    # Generate documentation
    doc_result = doc_service.generate_documentation(
        context=context,
        related_task_id=request.related_task_id
    )
    
    # Save to ClickUp if requested
    clickup_url = None
    if request.clickup_list_id:
        try:
            clickup_result = clickup_integration.create_doc_in_clickup(
                title=doc_result.get("title", "Generated Documentation"),
                content=doc_result.get("content", ""),
                list_id=request.clickup_list_id,
                tags=["ai-generated", request.doc_type]
            )
            
            clickup_url = clickup_result.get("url")
            
            # Save reference to the doc
            if clickup_url and request.related_task_id:
                doc_service.save_doc_reference(
                    doc_id=doc_result.get("doc_id"),
                    doc_url=clickup_url,
                    related_task_id=request.related_task_id
                )
        except Exception as e:
            # Log the error but continue (we still have the generated doc)
            print(f"Error saving to ClickUp: {str(e)}")
    
    # Prepare response
    return {
        "doc_id": doc_result.get("doc_id"),
        "title": doc_result.get("title", "Generated Documentation"),
        "content": doc_result.get("content", ""),
        "clickup_url": clickup_url,
        "generated_at": doc_result.get("generated_at")
    }

@router.post("/iterate", response_model=DocumentationResponse)
def iterate_documentation(
    request: DocumentationUpdateRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Update a document based on feedback.
    
    Takes the document ID and feedback, then generates an updated version.
    """
    # Initialize service
    doc_service = DocGenerationService(db)
    
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
        "clickup_url": None,  # Would update the existing doc in a real implementation
        "generated_at": updated_doc.get("updated_at")
    }

@router.get("/{doc_id}")
def get_documentation(
    doc_id: str,
    db: Session = Depends(get_db)
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