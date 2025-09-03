import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import uvicorn
from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.github_events import router as github_router
from app.api.health import router as health_router
from app.api.v1.api import api_v1_router
from app.api.webhooks import router as webhooks_router
from app.config.settings import settings
from app.config.supabase_client import get_supabase_client
from app.core.error_handlers import add_exception_handlers
from app.core.log_sanitizer import configure_secure_logging
from app.middleware.api_key_auth import ApiKeyMiddleware
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.request_metrics import RequestMetricsMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
root_logger = logging.getLogger()
if not root_logger.handlers:
    for handler in logging.getLogger("uvicorn.error").handlers:
        root_logger.addHandler(handler)
    root_logger.setLevel(logging.getLogger("uvicorn.error").level)

# Configure secure logging with sensitive data filtering
configure_secure_logging()

logger = logging.getLogger(__name__)

# Create app instance
app = FastAPI(
    title="GolfDaddy Brain API",
    description="Backend API for GolfDaddy Brain, the AI assistant for software engineering",
    version="1.0.0",
)

# Middleware
app.add_middleware(RequestMetricsMiddleware)
if settings.ENABLE_RATE_LIMITING:
    app.add_middleware(
        RateLimiterMiddleware,
        rate_limit_per_minute=settings.DEFAULT_RATE_LIMIT,
        exclude_paths=settings.RATE_LIMIT_EXCLUDE_PATHS.split(","),
    )

# Register minimal routers
app.include_router(health_router)
app.include_router(webhooks_router)
app.include_router(github_router)
app.include_router(api_v1_router, prefix="/api/v1")

# Register custom exception handlers
add_exception_handlers(app)

# Health check endpoint
@app.get("/health", tags=["status"])
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    }


# Debug endpoint to check frontend files
@app.get("/debug/frontend", tags=["debug"])
async def debug_frontend():
    frontend_dist_path = "/app/frontend/dist"
    debug_info = {
        "frontend_dist_exists": os.path.exists(frontend_dist_path),
        "frontend_dist_path": frontend_dist_path,
        "files": [],
    }

    if os.path.exists(frontend_dist_path):
        try:
            debug_info["files"] = os.listdir(frontend_dist_path)
        except Exception as e:
            debug_info["error"] = str(e)

    return debug_info


# Initialize services on startup
@app.on_event("startup")
def startup_services():
    try:
        # Initialize the Supabase client
        _ = get_supabase_client()
        logger.info("Supabase client initialized")

    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise


# Mount static files (frontend) - MUST be after all other routes
frontend_dist_path = "/app/frontend/dist"
if os.path.exists(frontend_dist_path):
    # Mount static assets
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")

    # Serve index.html for SPA routing (catch-all route)
    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_spa(full_path: str):
        # Don't serve SPA for API routes or known backend paths
        if full_path.startswith(("api/", "docs", "redoc", "openapi.json", "health", "auth/", "dev/")):
            return JSONResponse({"detail": "Not found"}, status_code=404)

        # Serve static files directly
        static_file = os.path.join(frontend_dist_path, full_path)
        if os.path.isfile(static_file):
            return FileResponse(static_file)

        # For everything else, serve the SPA index.html
        index_file = os.path.join(frontend_dist_path, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return JSONResponse({"detail": "Frontend not found"}, status_code=404)


# Main entry point
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
