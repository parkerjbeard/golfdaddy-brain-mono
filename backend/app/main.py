from fastapi import FastAPI, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import uvicorn
import logging
import os
from datetime import datetime, timedelta
import schedule
import time
import threading

from app.config.settings import settings
from app.config.supabase_client import get_supabase_client
from app.api.docs_generation import router as docs_router
from app.api.task_endpoints import router as tasks_router
from app.api.auth_endpoints import router as auth_router
from app.api.github_events import router as github_router
from app.api.daily_report_endpoints import router as daily_reports_router
from app.repositories.user_repository import UserRepository
from app.services.notification_service import NotificationService
from app.middleware.api_key_auth import ApiKeyMiddleware
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.request_metrics import RequestMetricsMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create app instance
app = FastAPI(
    title="GolfDaddy Brain API",
    description="Backend API for GolfDaddy Brain, the AI assistant for software engineering",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.add_middleware(RequestMetricsMiddleware)
if settings.ENABLE_RATE_LIMITING:
    app.add_middleware(
        RateLimiterMiddleware,
        rate_limit_per_minute=settings.DEFAULT_RATE_LIMIT,
        exclude_paths=settings.RATE_LIMIT_EXCLUDE_PATHS.split(","),
    )
if settings.ENABLE_API_AUTH:
    app.add_middleware(
        ApiKeyMiddleware,
        api_key_header=settings.API_KEY_HEADER,
        api_keys=settings.API_KEYS,
        exclude_paths=settings.AUTH_EXCLUDE_PATHS.split(","),
    )

# Register routers
app.include_router(auth_router)
app.include_router(docs_router)
app.include_router(tasks_router)
app.include_router(github_router)
app.include_router(daily_reports_router)

# Error handling
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error(f"Validation error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )

# Health check endpoint
@app.get("/health", tags=["status"])
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    }

# Create database tables on startup
@app.on_event("startup")
def startup_db_client():
    try:
        # Initialize the Supabase client
        supabase_client = get_supabase_client()
        logger.info("Supabase client initialized")
        
        # Database schema is managed via Supabase migrations in supabase/schemas
        logger.info("Database tables are managed declaratively via supabase/schemas")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise

# Schedule daily tasks
def schedule_tasks():
    schedule.every().day.at("01:00").do(daily_maintenance)
    
    # Run scheduled tasks in background
    while True:
        schedule.run_pending()
        time.sleep(60)

def daily_maintenance():
    """Run daily maintenance tasks."""
    try:
        logger.info("Running daily maintenance tasks")
        # Example: Clean up old data, generate reports, etc.
        supabase = get_supabase_client()
        
        # Run notifications for overdue tasks
        notification_service = NotificationService(supabase)
        notification_service.send_task_reminders()
        
        logger.info("Daily maintenance completed")
    except Exception as e:
        logger.error(f"Error in daily maintenance: {e}")

# Start scheduler in background on startup
@app.on_event("startup")
def start_scheduler():
    t = threading.Thread(target=schedule_tasks, daemon=True)
    t.start()
    logger.info("Scheduler started")

# Main entry point
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )