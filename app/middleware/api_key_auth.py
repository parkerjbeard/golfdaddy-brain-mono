from typing import Dict, Optional, Callable, List
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

class ApiKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware for API key authentication.
    Verifies that requests contain a valid API key in the header.
    """
    
    def __init__(
        self, 
        app,
        api_keys: Dict[str, Dict[str, str]],
        api_key_header: str = "X-API-Key",
        exclude_paths: Optional[List[str]] = None
    ):
        """
        Initialize API key middleware.
        
        Args:
            app: FastAPI application
            api_keys: Dict of {api_key: {"owner": owner_name, "role": role_name}}
            api_key_header: Name of the header containing the API key
            exclude_paths: List of URL paths to exclude from API key check
        """
        super().__init__(app)
        self.api_keys = api_keys
        self.api_key_header = api_key_header
        self.exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json", "/health"]
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip authentication for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
            
        # Get API key from header
        api_key = request.headers.get(self.api_key_header)
        
        # Check if API key is provided and valid
        if not api_key:
            logger.warning(f"No API key provided for {request.url.path}")
            return Response(
                content="API key required",
                status_code=401,
                headers={"WWW-Authenticate": "ApiKey"}
            )
            
        # Validate API key
        if api_key not in self.api_keys:
            logger.warning(f"Invalid API key provided for {request.url.path}")
            return Response(
                content="Invalid API key",
                status_code=403
            )
            
        # Add API key info to request state for use in routes
        request.state.api_key_info = self.api_keys[api_key]
        request.state.api_key = api_key
        
        # Continue processing the request
        return await call_next(request) 