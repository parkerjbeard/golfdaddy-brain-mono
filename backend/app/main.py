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
import asyncio

from app.config.settings import settings
from app.config.supabase_client import get_supabase_client
from app.api.docs_generation import router as docs_router
from app.api.auth_endpoints import router as auth_router
from app.api.github_events import router as github_router
from app.api.daily_report_endpoints import router as daily_reports_router
from app.api.archive_endpoints import router as archive_router
from app.api.health import router as health_router
from app.api.v1.api import api_v1_router
from app.api.webhooks import router as webhooks_router
from app.api.slack_daily_reports import router as slack_daily_reports_router
from app.api.weekly_hours_endpoints import router as weekly_hours_router
from app.api.daily_commit_analysis_endpoints import router as daily_analysis_router
from app.api.zapier_endpoints import router as zapier_router
from app.api.raci_matrix import router as raci_matrix_router
from app.api.zapier_webhooks import router as zapier_webhooks_router
from app.repositories.user_repository import UserRepository
from app.api.dev_endpoints import router as dev_router
from app.services.notification_service import NotificationService
from app.services.archive_service import ArchiveService
from app.middleware.api_key_auth import ApiKeyMiddleware
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.request_metrics import RequestMetricsMiddleware
from app.core.error_handlers import add_exception_handlers
from app.services.scheduled_tasks import start_scheduled_tasks, stop_scheduled_tasks

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
root_logger = logging.getLogger()
if not root_logger.handlers:
    for handler in logging.getLogger("uvicorn.error").handlers:
        root_logger.addHandler(handler)
    root_logger.setLevel(logging.getLogger("uvicorn.error").level)

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
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
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
app.include_router(github_router)
app.include_router(daily_reports_router)
app.include_router(archive_router, prefix="/api/v1")
app.include_router(health_router)
app.include_router(api_v1_router, prefix="/api/v1")
app.include_router(webhooks_router)
app.include_router(slack_daily_reports_router, prefix="/api")
app.include_router(weekly_hours_router)
app.include_router(daily_analysis_router)
app.include_router(zapier_router, prefix="/api/v1")
app.include_router(raci_matrix_router, prefix="/api/v1")
app.include_router(zapier_webhooks_router)  # Zapier webhooks already have /api/zapier prefix

# Development endpoints (should be disabled in production)
if os.getenv("ENVIRONMENT", "development") == "development":
    app.include_router(dev_router)

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

# Initialize services on startup
@app.on_event("startup")
def startup_services():
    try:
        # Initialize the Supabase client
        supabase_client = get_supabase_client()
        logger.info("Supabase client initialized")
        
        # Database schema is managed via Supabase migrations in supabase/schemas
        logger.info("Database tables are managed declaratively via supabase/schemas")
        
        # Initialize circuit breakers and rate limiters for documentation services
        from app.core.circuit_breaker import create_github_circuit_breaker, create_openai_circuit_breaker
        from app.core.rate_limiter import create_github_rate_limiter, create_openai_rate_limiter
        
        github_breaker = create_github_circuit_breaker()
        openai_breaker = create_openai_circuit_breaker()
        github_limiter = create_github_rate_limiter()
        openai_limiter = create_openai_rate_limiter()
        
        logger.info("Circuit breakers and rate limiters initialized")
        logger.info(f"GitHub circuit breaker: {github_breaker.config.name} (threshold: {github_breaker.config.failure_threshold})")
        logger.info(f"OpenAI circuit breaker: {openai_breaker.config.name} (threshold: {openai_breaker.config.failure_threshold})")
        logger.info(f"GitHub rate limiter: {github_limiter.config.requests_per_hour} requests/hour")
        logger.info(f"OpenAI rate limiter: {openai_limiter.config.requests_per_hour} requests/hour")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise

# Schedule daily tasks
def schedule_tasks():
    schedule.every().day.at("01:00").do(daily_maintenance)
    
    # Schedule data archiving at configured time (default 2 AM)
    if settings.ENABLE_AUTO_ARCHIVE:
        archive_time = f"{settings.ARCHIVE_SCHEDULE_HOUR:02d}:00"
        schedule.every().day.at(archive_time).do(run_data_archiving)
        logger.info(f"Scheduled automatic data archiving at {archive_time}")
    
    # Schedule EOD reminders at configured time (default 5 PM)
    eod_time = getattr(settings, 'EOD_REMINDER_TIME', '17:00')
    schedule.every().day.at(eod_time).do(run_eod_reminders)
    logger.info(f"Scheduled EOD reminders at {eod_time}")
    
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

def run_data_archiving():
    """Run automatic data archiving based on retention policies."""
    try:
        logger.info("Starting automatic data archiving")
        supabase = get_supabase_client()
        
        archive_service = ArchiveService(supabase)
        results = asyncio.run(archive_service.archive_old_data(dry_run=False))
        
        # Log archiving results
        total_archived = 0
        for table_name, result in results.items():
            archived_count = result.get('records_archived', 0)
            total_archived += archived_count
            logger.info(f"Archived {archived_count} records from {table_name}")
        
        logger.info(f"Data archiving completed. Total records archived: {total_archived}")
        
    except Exception as e:
        logger.error(f"Error in data archiving: {e}")

def run_eod_reminders():
    """Run EOD reminder task."""
    try:
        logger.info("Starting EOD reminder task")
        from app.services.eod_reminder_service import send_daily_eod_reminders
        results = asyncio.run(send_daily_eod_reminders())
        logger.info(f"EOD reminders sent: {results}")
    except Exception as e:
        logger.error(f"Error in EOD reminders: {e}")

# Start scheduler in background on startup
@app.on_event("startup")
def start_scheduler():
    t = threading.Thread(target=schedule_tasks, daemon=True)
    t.start()
    logger.info("Scheduler started")

# Start new scheduled tasks
@app.on_event("startup")
async def start_async_tasks():
    await start_scheduled_tasks()

@app.on_event("shutdown")
async def shutdown_async_tasks():
    await stop_scheduled_tasks()

# Main entry point
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )