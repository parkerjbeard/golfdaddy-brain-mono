from fastapi import FastAPI, Depends
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

# Add CORS middleware
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
    # Run the application with uvicorn when executed directly
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)