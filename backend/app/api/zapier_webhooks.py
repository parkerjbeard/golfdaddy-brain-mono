from fastapi import APIRouter, Request, HTTPException, Depends, Header
from datetime import datetime
from typing import Optional, Dict, Any
import json
import hashlib
import hmac
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.zapier_models import (
    SocialMediaMetric,
    UserFeedback,
    Objective,
    Win,
    Analytics,
    FormSubmission,
    Employee
)
from app.config.settings import settings

router = APIRouter(prefix="/api/zapier", tags=["zapier"])


def verify_webhook_signature(
    request_body: bytes,
    signature: Optional[str] = Header(None, alias="X-Zapier-Signature"),
    api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> bool:
    """Verify webhook authenticity using API key or signature"""
    
    # Method 1: API Key verification (recommended)
    if api_key:
        valid_keys = settings.ZAPIER_API_KEYS.split(",") if settings.ZAPIER_API_KEYS else []
        if api_key in valid_keys:
            return True
    
    # Method 2: HMAC signature verification (if Zapier supports it)
    if signature and settings.ZAPIER_WEBHOOK_SECRET:
        expected_signature = hmac.new(
            settings.ZAPIER_WEBHOOK_SECRET.encode(),
            request_body,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected_signature)
    
    # If no auth method is configured, allow in development only
    if settings.ENVIRONMENT == "development" and not settings.ZAPIER_REQUIRE_AUTH:
        return True
    
    return False


async def validate_webhook(request: Request) -> Dict[str, Any]:
    """Common webhook validation and data extraction"""
    # Get raw body for signature verification
    body = await request.body()
    
    # Verify webhook authenticity
    api_key = request.headers.get("X-API-Key")
    signature = request.headers.get("X-Zapier-Signature")
    
    if not verify_webhook_signature(body, signature, api_key):
        raise HTTPException(status_code=401, detail="Invalid webhook signature or API key")
    
    # Parse JSON body
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    return data


@router.post("/social-media-views")
async def social_media_views_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Receive social media metrics from Zapier"""
    data = await validate_webhook(request)
    
    # Extract and validate data
    metric = SocialMediaMetric(
        platform=data.get("platform", "unknown"),
        views=int(data.get("views", 0)),
        engagement=float(data.get("engagement", 0.0)),
        reach=int(data.get("reach", 0)) if data.get("reach") else None,
        impressions=int(data.get("impressions", 0)) if data.get("impressions") else None,
        zap_run_id=data.get("zap_meta", {}).get("id"),
        raw_data=data
    )
    
    db.add(metric)
    db.commit()
    db.refresh(metric)
    
    return {
        "status": "success",
        "id": str(metric.id),
        "message": f"Social media metrics for {metric.platform} recorded"
    }


@router.post("/csat-feedback")
async def csat_feedback_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Receive CSAT and user feedback from Zapier"""
    data = await validate_webhook(request)
    
    # Validate CSAT score
    csat_score = int(data.get("csat_score", 0))
    if not 1 <= csat_score <= 5:
        raise HTTPException(status_code=400, detail="CSAT score must be between 1 and 5")
    
    feedback = UserFeedback(
        csat_score=csat_score,
        feedback_text=data.get("feedback_text", ""),
        user_id=data.get("user_id"),
        user_email=data.get("user_email"),
        feedback_category=data.get("category"),
        sentiment=data.get("sentiment"),
        zap_run_id=data.get("zap_meta", {}).get("id"),
        raw_data=data
    )
    
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    
    return {
        "status": "success",
        "id": str(feedback.id),
        "message": "User feedback recorded"
    }


@router.post("/current-objective")
async def current_objective_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Receive current objectives from Zapier"""
    data = await validate_webhook(request)
    
    # Check if we should update existing or create new
    objective_id = data.get("objective_id")
    if objective_id:
        # Update existing objective
        objective = db.query(Objective).filter(Objective.id == objective_id).first()
        if objective:
            objective.title = data.get("title", objective.title)
            objective.description = data.get("description", objective.description)
            objective.status = data.get("status", objective.status)
            objective.progress = int(data.get("progress", objective.progress))
            objective.updated_at = datetime.utcnow()
        else:
            raise HTTPException(status_code=404, detail="Objective not found")
    else:
        # Create new objective
        objective = Objective(
            title=data.get("title", "Untitled Objective"),
            description=data.get("description", ""),
            status=data.get("status", "active"),
            priority=data.get("priority", "medium"),
            due_date=datetime.fromisoformat(data["due_date"]) if data.get("due_date") else None,
            progress=int(data.get("progress", 0)),
            zap_run_id=data.get("zap_meta", {}).get("id"),
            raw_data=data
        )
        db.add(objective)
    
    db.commit()
    db.refresh(objective)
    
    return {
        "status": "success",
        "id": str(objective.id),
        "message": f"Objective '{objective.title}' saved"
    }


@router.post("/wins-section")
async def wins_section_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Receive wins data from Zapier (AI-generated or manual)"""
    data = await validate_webhook(request)
    
    win = Win(
        title=data.get("title", "Untitled Win"),
        description=data.get("description", ""),
        category=data.get("category", "general"),
        impact=data.get("impact", "medium"),
        ai_generated=data.get("ai_generated", True),
        ai_prompt=data.get("ai_prompt") if data.get("ai_generated") else None,
        team_members=data.get("team_members", []),
        zap_run_id=data.get("zap_meta", {}).get("id"),
        raw_data=data
    )
    
    db.add(win)
    db.commit()
    db.refresh(win)
    
    return {
        "status": "success",
        "id": str(win.id),
        "message": f"Win '{win.title}' recorded"
    }


@router.post("/analytics")
async def analytics_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Receive analytics data from Zapier"""
    data = await validate_webhook(request)
    
    # Handle different metric value types
    metric_value = data.get("metric_value")
    if isinstance(metric_value, (int, float)):
        metric_value = {"value": metric_value}
    elif not isinstance(metric_value, dict):
        metric_value = {"raw": str(metric_value)}
    
    analytics = Analytics(
        metric_name=data.get("metric_name", "unknown_metric"),
        metric_value=metric_value,
        category=data.get("category", "general"),
        source=data.get("source", "zapier"),
        tags=data.get("tags", []),
        period_start=datetime.fromisoformat(data["period_start"]) if data.get("period_start") else None,
        period_end=datetime.fromisoformat(data["period_end"]) if data.get("period_end") else None,
        zap_run_id=data.get("zap_meta", {}).get("id"),
        raw_data=data
    )
    
    db.add(analytics)
    db.commit()
    db.refresh(analytics)
    
    return {
        "status": "success",
        "id": str(analytics.id),
        "message": f"Analytics metric '{analytics.metric_name}' recorded"
    }


@router.post("/google-forms")
async def google_forms_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Receive Google Forms submission data from Zapier"""
    data = await validate_webhook(request)
    
    form_submission = FormSubmission(
        form_id=data.get("form_id", "unknown"),
        form_name=data.get("form_name", "Untitled Form"),
        respondent_email=data.get("respondent_email"),
        responses=data.get("responses", {}),
        form_type=data.get("form_type", "general"),
        submission_timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.utcnow(),
        zap_run_id=data.get("zap_meta", {}).get("id"),
        raw_data=data
    )
    
    db.add(form_submission)
    db.commit()
    db.refresh(form_submission)
    
    return {
        "status": "success",
        "id": str(form_submission.id),
        "message": f"Form submission for '{form_submission.form_name}' recorded"
    }


@router.post("/employee-directory")
async def employee_directory_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Receive employee directory updates from Zapier"""
    data = await validate_webhook(request)
    
    # Check if employee exists
    employee_id = data.get("employee_id")
    email = data.get("email")
    
    existing_employee = None
    if employee_id:
        existing_employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    elif email:
        existing_employee = db.query(Employee).filter(Employee.email == email).first()
    
    if existing_employee:
        # Update existing employee
        existing_employee.name = data.get("name", existing_employee.name)
        existing_employee.department = data.get("department", existing_employee.department)
        existing_employee.title = data.get("title", existing_employee.title)
        existing_employee.phone = data.get("phone", existing_employee.phone)
        existing_employee.location = data.get("location", existing_employee.location)
        existing_employee.manager = data.get("manager", existing_employee.manager)
        existing_employee.status = data.get("status", existing_employee.status)
        existing_employee.updated_at = datetime.utcnow()
        employee = existing_employee
    else:
        # Create new employee
        employee = Employee(
            employee_id=employee_id or data.get("email", "").split("@")[0],
            name=data.get("name", "Unknown Employee"),
            email=email,
            department=data.get("department"),
            title=data.get("title"),
            phone=data.get("phone"),
            location=data.get("location"),
            manager=data.get("manager"),
            status=data.get("status", "active"),
            start_date=datetime.fromisoformat(data["start_date"]) if data.get("start_date") else None,
            zap_run_id=data.get("zap_meta", {}).get("id"),
            raw_data=data
        )
        db.add(employee)
    
    db.commit()
    db.refresh(employee)
    
    return {
        "status": "success",
        "id": str(employee.id),
        "message": f"Employee '{employee.name}' {'updated' if existing_employee else 'created'}"
    }


@router.get("/health")
async def webhook_health():
    """Health check endpoint for Zapier webhooks"""
    return {
        "status": "healthy",
        "service": "zapier_webhooks",
        "timestamp": datetime.utcnow().isoformat(),
        "auth_required": bool(settings.ZAPIER_API_KEYS or settings.ZAPIER_WEBHOOK_SECRET)
    }


@router.post("/test")
async def test_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Test endpoint for Zapier webhook setup"""
    try:
        data = await validate_webhook(request)
        return {
            "status": "success",
            "message": "Webhook received successfully",
            "data_received": data,
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException as e:
        return {
            "status": "error",
            "message": str(e.detail),
            "timestamp": datetime.utcnow().isoformat()
        }