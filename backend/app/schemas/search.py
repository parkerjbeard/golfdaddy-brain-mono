"""
Pydantic schemas for semantic search API.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Request model for document search."""

    query: str = Field(..., description="Search query in natural language")
    repository: Optional[str] = Field(None, description="Filter by repository")
    doc_type: Optional[str] = Field(None, description="Filter by document type")
    limit: Optional[int] = Field(10, ge=1, le=50, description="Maximum results to return")
    include_context: bool = Field(True, description="Include related code context")


class SearchResult(BaseModel):
    """Individual search result."""

    id: str
    title: str
    content: str
    type: Optional[str]
    repository: Optional[str]
    file_path: Optional[str]
    similarity: float = Field(..., ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    related_code: Optional[List[Dict[str, Any]]] = None


class SearchResponse(BaseModel):
    """Response model for document search."""

    query: str
    repository: Optional[str]
    results: List[SearchResult]
    total_results: int
    total_documents: int
    search_time: str


class DocumentationGap(BaseModel):
    """Model for documentation gap information."""

    file_path: str
    module: Optional[str]
    classes: Optional[int] = 0
    functions: Optional[int] = 0
    complexity: Optional[float] = 0.0


class PoorlyDocumentedFile(BaseModel):
    """Model for poorly documented file."""

    file_path: str
    best_match: str
    match_score: float
    improvement_needed: bool = True


class DocumentationSuggestion(BaseModel):
    """Model for documentation suggestion."""

    file_path: str
    priority: str = Field(..., pattern="^(high|medium|low)$")
    suggested_sections: List[str]


class CoverageSummary(BaseModel):
    """Model for coverage summary."""

    total_files: int
    documented_files: int
    coverage_percentage: float = Field(..., ge=0.0, le=100.0)


class DocumentationGapsResponse(BaseModel):
    """Response model for documentation gaps analysis."""

    undocumented_files: List[DocumentationGap]
    poorly_documented_files: List[PoorlyDocumentedFile]
    suggested_documentation: List[DocumentationSuggestion]
    coverage_summary: CoverageSummary


class GraphNode(BaseModel):
    """Model for graph node."""

    id: str
    label: str
    type: str
    size: int


class GraphEdge(BaseModel):
    """Model for graph edge."""

    source: str
    target: str
    weight: float
    type: str


class GraphStatistics(BaseModel):
    """Model for graph statistics."""

    total_nodes: int
    total_edges: int
    average_connections: float


class DocumentGraphResponse(BaseModel):
    """Response model for documentation graph."""

    nodes: List[GraphNode]
    edges: List[GraphEdge]
    statistics: GraphStatistics


class QualityMetrics(BaseModel):
    """Model for document quality metrics."""

    length: int
    has_examples: bool
    has_links: bool
    last_updated: Optional[str]


class ImprovementItem(BaseModel):
    """Model for improvement suggestion item."""

    type: str
    priority: str = Field(..., pattern="^(high|medium|low)$")
    description: str


class RelatedUpdate(BaseModel):
    """Model for related update suggestion."""

    commit: str
    date: str
    file: str
    suggestion: str


class ImprovementSuggestionsResponse(BaseModel):
    """Response model for improvement suggestions."""

    document_id: str
    title: str
    current_quality: QualityMetrics
    improvements: List[ImprovementItem]
    related_updates: List[RelatedUpdate]


class CoverageRecommendation(BaseModel):
    """Model for coverage recommendation."""

    type: str
    message: str
    priority: str = Field(..., pattern="^(high|medium|low)$")


class CoverageResponse(BaseModel):
    """Response model for documentation coverage."""

    repository: str
    total_files: int
    documented_files: int
    undocumented_files: int
    poorly_documented_files: int
    coverage_percentage: float = Field(..., ge=0.0, le=100.0)
    quality_score: float = Field(..., ge=0.0, le=100.0)
    recommendations: List[CoverageRecommendation]
