from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
from sqlalchemy.orm import Session
import os
from datetime import datetime, timedelta
import schedule
import time
import threading

from app.config.settings import settings
from app.config.database import Base, engine, get_db
from app.api.slack_events import router as slack_router
from app.api.slack import router as slack_webhook_router
from app.api.docs_generation import router as docs_router
from app.api.task_endpoints import router as tasks_router
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

# Create FastAPI app
app = FastAPI(
    title="GolfDaddy Brain API",
    description="Backend API for task management with RACI framework and AI-powered features",
    version="1.0.0",
)

# Create metrics middleware instance for metrics endpoint
metrics_middleware = RequestMetricsMiddleware(app)

# Add middleware
# Order is important - middleware executes in reverse order (last added, first executed)

# Add metrics middleware first (will be executed last)
app.add_middleware(RequestMetricsMiddleware)

# Add rate limiting middleware if enabled
if settings.enable_rate_limiting:
    logger.info("Adding rate limiting middleware")
    app.add_middleware(
        RateLimiterMiddleware,
        rate_limit_per_minute=settings.default_rate_limit,
        api_key_header=settings.api_key_header,
        api_keys={key: info.get("rate_limit", settings.default_rate_limit) 
                 for key, info in settings.api_keys.items()},
        exclude_paths=settings.rate_limit_exclude_paths
    )

# Add API key authentication middleware if enabled
if settings.enable_api_auth:
    logger.info("Adding API key authentication middleware")
    app.add_middleware(
        ApiKeyMiddleware,
        api_keys=settings.api_keys,
        api_key_header=settings.api_key_header,
        exclude_paths=settings.auth_exclude_paths
    )

# Add CORS middleware last (will be executed first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, this should be restricted
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(slack_router)
app.include_router(slack_webhook_router)
app.include_router(docs_router)
app.include_router(tasks_router)

# Create database tables on startup
@app.on_event("startup")
def startup_db_client():
    try:
        # Create tables if they don't exist
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created or verified")
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise

# Background scheduler for recurring tasks
def start_scheduler():
    """Start the background scheduler for recurring tasks."""
    
    def run_schedule():
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    # Schedule EOD reminders daily at 4:30 PM
    schedule.every().day.at("16:30").do(send_eod_reminders)
    
    # Start the scheduler in a background thread
    scheduler_thread = threading.Thread(target=run_schedule, daemon=True)
    scheduler_thread.start()
    logger.info("Background scheduler started")

def send_eod_reminders():
    """Send end-of-day task reminders to all users."""
    try:
        # Get database session
        db = next(get_db())
        
        # Get all users
        user_repository = UserRepository(db)
        notification_service = NotificationService(db)
        
        users = user_repository.list_users()
        
        # Send reminders to each user
        for user in users:
            notification_service.eod_reminder(user.id)
        
        logger.info(f"Sent EOD reminders to {len(users)} users")
    except Exception as e:
        logger.error(f"Error sending EOD reminders: {str(e)}")

# Metrics endpoint
@app.get("/metrics")
def get_metrics(request: Request):
    """
    Get API usage metrics.
    This endpoint is only accessible without authentication in development mode.
    """
    if not settings.testing_mode and request.url.hostname not in ["localhost", "127.0.0.1"]:
        # Check if request has a valid API key with admin role
        api_key_info = getattr(request.state, "api_key_info", {})
        if api_key_info.get("role") != "admin":
            return {"error": "Unauthorized", "message": "Admin role required"}
    
    return metrics_middleware.get_metrics()

# Simple health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": app.version
    }

# Root endpoint
@app.get("/")
def read_root():
    """Root endpoint with API information."""
    return {
        "name": "GolfDaddy Brain API",
        "version": app.version,
        "docs_url": "/docs",
        "health_check": "/health"
    }

if __name__ == "__main__":
    # Start the background scheduler
    start_scheduler()
    
    # Run the application with uvicorn when executed directly
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)