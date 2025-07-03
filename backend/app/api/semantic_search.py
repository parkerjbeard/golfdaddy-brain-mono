"""
API endpoints for semantic search and documentation insights.
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.database import get_db
from app.auth.dependencies import get_current_user
from app.services.semantic_search_service import SemanticSearchService
from app.services.embedding_service import EmbeddingService
from app.services.context_analyzer import ContextAnalyzer
from app.schemas.search import (
    SearchRequest,
    SearchResponse,
    DocumentationGapsResponse,
    DocumentGraphResponse,
    ImprovementSuggestionsResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/search", tags=["Semantic Search"])


@router.post("/documents", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Search documentation using semantic similarity.
    
    This endpoint uses AI embeddings to find relevant documentation
    based on natural language queries.
    """
    search_service = SemanticSearchService()
    
    try:
        results = await search_service.search_documentation(
            db,
            query=request.query,
            repository=request.repository,
            doc_type=request.doc_type,
            limit=request.limit or 10,
            include_context=request.include_context
        )
        
        return SearchResponse(**results)
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


@router.get("/documents/{document_id}/related")
async def get_related_documents(
    document_id: str,
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Find documents related to a specific document."""
    search_service = SemanticSearchService()
    
    try:
        related = await search_service.find_related_documentation(
            db, document_id, limit
        )
        
        return {
            "document_id": document_id,
            "related_documents": related,
            "count": len(related)
        }
        
    except Exception as e:
        logger.error(f"Error finding related documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to find related documents")


@router.get("/gaps/{repository}", response_model=DocumentationGapsResponse)
async def analyze_documentation_gaps(
    repository: str,
    threshold: float = Query(0.7, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze gaps in documentation coverage for a repository.
    
    This identifies files and modules that lack proper documentation.
    """
    search_service = SemanticSearchService()
    
    try:
        gaps = await search_service.analyze_documentation_gaps(
            db, repository, threshold
        )
        
        return DocumentationGapsResponse(**gaps)
        
    except Exception as e:
        logger.error(f"Error analyzing gaps: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze documentation gaps")


@router.get("/graph/{repository}", response_model=DocumentGraphResponse)
async def get_documentation_graph(
    repository: str,
    max_nodes: int = Query(50, ge=10, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get a graph representation of documentation relationships.
    
    This can be used to visualize how documents are connected.
    """
    search_service = SemanticSearchService()
    
    try:
        graph = await search_service.get_documentation_graph(
            db, repository, max_nodes
        )
        
        return DocumentGraphResponse(**graph)
        
    except Exception as e:
        logger.error(f"Error building graph: {e}")
        raise HTTPException(status_code=500, detail="Failed to build documentation graph")


@router.get("/suggestions/{document_id}", response_model=ImprovementSuggestionsResponse)
async def get_improvement_suggestions(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get AI-powered improvement suggestions for a document."""
    search_service = SemanticSearchService()
    
    try:
        suggestions = await search_service.suggest_documentation_improvements(
            db, document_id
        )
        
        return ImprovementSuggestionsResponse(**suggestions)
        
    except Exception as e:
        logger.error(f"Error generating suggestions: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate suggestions")


@router.post("/analyze-repository/{repository}")
async def analyze_repository_context(
    repository: str,
    repo_path: str = Query(..., description="Local path to repository"),
    max_files: int = Query(100, ge=10, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze a repository to build context for better documentation.
    
    This is typically run once when setting up a new repository.
    """
    embedding_service = EmbeddingService()
    context_analyzer = ContextAnalyzer(embedding_service)
    
    try:
        analysis = await context_analyzer.analyze_repository(
            db, repository, repo_path, max_files
        )
        
        return {
            "repository": repository,
            "status": "analyzed",
            "files_analyzed": analysis['analyzed_files'],
            "languages": analysis['languages'],
            "patterns": analysis['patterns'],
            "structure": analysis['structure'],
            "metrics": analysis['metrics']
        }
        
    except Exception as e:
        logger.error(f"Error analyzing repository: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze repository")


@router.post("/embed-document")
async def embed_document(
    title: str,
    content: str,
    doc_type: str,
    repository: str,
    file_path: Optional[str] = None,
    document_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Create embeddings for a document to enable semantic search.
    
    This is typically called when new documentation is created.
    """
    embedding_service = EmbeddingService()
    
    try:
        doc_embedding = await embedding_service.embed_document(
            db,
            title=title,
            content=content,
            doc_type=doc_type,
            repository=repository,
            file_path=file_path,
            document_id=document_id,
            metadata=metadata
        )
        
        if doc_embedding:
            return {
                "id": str(doc_embedding.id),
                "status": "embedded",
                "title": doc_embedding.title,
                "repository": doc_embedding.repository
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to create embedding")
            
    except Exception as e:
        logger.error(f"Error embedding document: {e}")
        raise HTTPException(status_code=500, detail="Failed to embed document")


@router.get("/coverage/{repository}")
async def get_documentation_coverage(
    repository: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get overall documentation coverage statistics for a repository."""
    search_service = SemanticSearchService()
    
    try:
        gaps = await search_service.analyze_documentation_gaps(db, repository)
        
        # Calculate additional metrics
        total_files = gaps['coverage_summary']['total_files']
        documented_files = gaps['coverage_summary']['documented_files']
        
        coverage = {
            "repository": repository,
            "total_files": total_files,
            "documented_files": documented_files,
            "undocumented_files": len(gaps['undocumented_files']),
            "poorly_documented_files": len(gaps['poorly_documented_files']),
            "coverage_percentage": gaps['coverage_summary']['coverage_percentage'],
            "quality_score": 0.0,  # Calculate based on various factors
            "recommendations": []
        }
        
        # Calculate quality score
        if documented_files > 0:
            quality_factors = [
                gaps['coverage_summary']['coverage_percentage'] / 100,
                1 - (len(gaps['poorly_documented_files']) / documented_files),
            ]
            coverage['quality_score'] = sum(quality_factors) / len(quality_factors) * 100
        
        # Add recommendations
        if coverage['coverage_percentage'] < 50:
            coverage['recommendations'].append({
                "type": "low_coverage",
                "message": "Documentation coverage is below 50%. Consider documenting high-complexity files first.",
                "priority": "high"
            })
        
        if len(gaps['poorly_documented_files']) > 5:
            coverage['recommendations'].append({
                "type": "improve_quality",
                "message": f"{len(gaps['poorly_documented_files'])} files have poor documentation. Review and enhance them.",
                "priority": "medium"
            })
        
        return coverage
        
    except Exception as e:
        logger.error(f"Error calculating coverage: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate coverage")