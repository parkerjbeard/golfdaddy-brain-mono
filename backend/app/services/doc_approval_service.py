"""
Documentation Approval Workflow Service

Manages approval workflows for documentation changes including Slack integration,
review assignments, and approval tracking.
"""

import logging
import json
import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import requests

from supabase import Client

from app.config.settings import settings
from app.core.exceptions import ExternalServiceError, ValidationError, ResourceNotFoundError
from app.services.doc_quality_service import QualityMetrics, QualityLevel

logger = logging.getLogger(__name__)


class ApprovalStatus(Enum):
    """Approval workflow status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"
    AUTO_APPROVED = "auto_approved"
    EXPIRED = "expired"


class ReviewerRole(Enum):
    """Reviewer role types."""
    AUTHOR = "author"
    TECHNICAL_REVIEWER = "technical_reviewer"
    CONTENT_REVIEWER = "content_reviewer"
    APPROVER = "approver"
    ADMIN = "admin"


@dataclass
class ApprovalRequest:
    """Documentation approval request."""
    id: str
    document_id: str
    title: str
    content: str
    doc_type: str
    author_id: str
    status: ApprovalStatus
    quality_metrics: Optional[Dict[str, Any]]
    
    # Workflow tracking
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]
    
    # Review assignments
    reviewers: List[str]  # User IDs
    approvers: List[str]  # User IDs
    
    # Review results
    reviews: List[Dict[str, Any]]
    slack_thread_id: Optional[str] = None
    auto_approval_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        data = asdict(self)
        data["status"] = self.status.value
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        if self.expires_at:
            data["expires_at"] = self.expires_at.isoformat()
        return data


@dataclass
class ReviewDecision:
    """Individual review decision."""
    reviewer_id: str
    reviewer_role: ReviewerRole
    decision: str  # "approve", "reject", "request_changes"
    comments: str
    reviewed_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "reviewer_id": self.reviewer_id,
            "reviewer_role": self.reviewer_role.value,
            "decision": self.decision,
            "comments": self.comments,
            "reviewed_at": self.reviewed_at.isoformat()
        }


class DocApprovalService:
    """Service for managing documentation approval workflows."""
    
    def __init__(self, supabase: Client):
        """Initialize the approval service."""
        self.supabase = supabase
        self.slack_webhook_url = getattr(settings, 'SLACK_WEBHOOK_URL', None)
        
        # Approval configuration
        self.auto_approval_enabled = getattr(settings, 'ENABLE_AUTO_APPROVAL', True)
        self.approval_timeout_hours = getattr(settings, 'APPROVAL_TIMEOUT_HOURS', 72)
        self.require_technical_review = getattr(settings, 'REQUIRE_TECHNICAL_REVIEW', True)
        
        logger.info(f"DocApprovalService initialized with auto_approval={self.auto_approval_enabled}")
    
    async def create_approval_request(self, document_id: str, title: str, content: str,
                                    doc_type: str, author_id: str, 
                                    quality_metrics: Optional[QualityMetrics] = None,
                                    reviewers: Optional[List[str]] = None) -> ApprovalRequest:
        """
        Create a new documentation approval request.
        
        Args:
            document_id: ID of the document
            title: Document title
            content: Document content
            doc_type: Type of document
            author_id: ID of the author
            quality_metrics: Quality assessment results
            reviewers: Optional list of specific reviewers
            
        Returns:
            ApprovalRequest instance
        """
        request_id = str(uuid.uuid4())
        now = datetime.now()
        expires_at = now + timedelta(hours=self.approval_timeout_hours)
        
        # Determine if this should be auto-approved
        auto_approve = False
        auto_approval_reason = None
        
        if self.auto_approval_enabled and quality_metrics:
            from app.services.doc_quality_service import DocQualityService
            quality_service = DocQualityService()
            
            if quality_service.should_approve_automatically(quality_metrics, doc_type):
                auto_approve = True
                auto_approval_reason = f"Auto-approved: Quality score {quality_metrics.overall_score}/100"
        
        # Assign reviewers if not specified
        if not reviewers:
            reviewers = await self._assign_reviewers(doc_type, author_id)
        
        # Assign approvers
        approvers = await self._assign_approvers(doc_type, author_id)
        
        # Create approval request
        approval_request = ApprovalRequest(
            id=request_id,
            document_id=document_id,
            title=title,
            content=content,
            doc_type=doc_type,
            author_id=author_id,
            status=ApprovalStatus.AUTO_APPROVED if auto_approve else ApprovalStatus.PENDING,
            quality_metrics=quality_metrics.to_dict() if quality_metrics else None,
            created_at=now,
            updated_at=now,
            expires_at=None if auto_approve else expires_at,
            reviewers=reviewers,
            approvers=approvers,
            reviews=[],
            auto_approval_reason=auto_approval_reason
        )
        
        # Save to database
        await self._save_approval_request(approval_request)
        
        # Send notifications if not auto-approved
        if not auto_approve:
            await self._send_approval_notifications(approval_request)
        
        logger.info(f"Created approval request {request_id} for document {document_id} "
                   f"(auto_approved: {auto_approve})")
        
        return approval_request
    
    async def submit_review(self, request_id: str, reviewer_id: str, 
                          decision: str, comments: str,
                          reviewer_role: ReviewerRole = ReviewerRole.TECHNICAL_REVIEWER) -> ApprovalRequest:
        """
        Submit a review decision for an approval request.
        
        Args:
            request_id: ID of the approval request
            reviewer_id: ID of the reviewer
            decision: Review decision ("approve", "reject", "request_changes")
            comments: Review comments
            reviewer_role: Role of the reviewer
            
        Returns:
            Updated ApprovalRequest
        """
        # Get existing approval request
        approval_request = await self.get_approval_request(request_id)
        
        if approval_request.status not in [ApprovalStatus.PENDING, ApprovalStatus.NEEDS_REVIEW]:
            raise ValidationError(f"Cannot review request in status: {approval_request.status.value}")
        
        # Create review decision
        review = ReviewDecision(
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            decision=decision,
            comments=comments,
            reviewed_at=datetime.now()
        )
        
        # Add review to request
        approval_request.reviews.append(review.to_dict())
        approval_request.updated_at = datetime.now()
        
        # Update status based on reviews
        new_status = self._calculate_approval_status(approval_request)
        approval_request.status = new_status
        
        # Save updated request
        await self._save_approval_request(approval_request)
        
        # Send notifications
        await self._send_review_notifications(approval_request, review)
        
        logger.info(f"Review submitted for request {request_id} by {reviewer_id}: {decision}")
        
        return approval_request
    
    async def get_approval_request(self, request_id: str) -> ApprovalRequest:
        """Get approval request by ID."""
        try:
            response = self.supabase.table("doc_approval_requests").select("*").eq("id", request_id).single().execute()
            
            if not response.data:
                raise ResourceNotFoundError(resource_name="ApprovalRequest", resource_id=request_id)
            
            return self._approval_request_from_db(response.data)
            
        except Exception as e:
            logger.error(f"Error fetching approval request {request_id}: {e}")
            raise
    
    async def list_approval_requests(self, filters: Optional[Dict[str, Any]] = None,
                                   limit: int = 50, offset: int = 0) -> List[ApprovalRequest]:
        """List approval requests with optional filters."""
        try:
            query = self.supabase.table("doc_approval_requests").select("*")
            
            # Apply filters
            if filters:
                if filters.get("status"):
                    query = query.eq("status", filters["status"])
                if filters.get("author_id"):
                    query = query.eq("author_id", filters["author_id"])
                if filters.get("doc_type"):
                    query = query.eq("doc_type", filters["doc_type"])
                if filters.get("reviewer_id"):
                    # This requires checking the reviewers array
                    query = query.contains("reviewers", [filters["reviewer_id"]])
            
            query = query.order("created_at", desc=True).limit(limit).offset(offset)
            response = query.execute()
            
            return [self._approval_request_from_db(row) for row in response.data]
            
        except Exception as e:
            logger.error(f"Error listing approval requests: {e}")
            raise
    
    async def get_pending_approvals_for_user(self, user_id: str) -> List[ApprovalRequest]:
        """Get pending approval requests assigned to a user."""
        try:
            # Get requests where user is a reviewer or approver
            response = self.supabase.table("doc_approval_requests").select("*").in_(
                "status", [ApprovalStatus.PENDING.value, ApprovalStatus.NEEDS_REVIEW.value]
            ).execute()
            
            # Filter to requests where user is assigned
            user_requests = []
            for row in response.data:
                reviewers = row.get("reviewers", [])
                approvers = row.get("approvers", [])
                if user_id in reviewers or user_id in approvers:
                    user_requests.append(self._approval_request_from_db(row))
            
            return user_requests
            
        except Exception as e:
            logger.error(f"Error getting pending approvals for user {user_id}: {e}")
            raise
    
    async def expire_old_requests(self) -> List[str]:
        """Expire old approval requests that have timed out."""
        try:
            now = datetime.now()
            
            # Find expired requests
            response = self.supabase.table("doc_approval_requests").select("*").eq(
                "status", ApprovalStatus.PENDING.value
            ).lt("expires_at", now.isoformat()).execute()
            
            expired_ids = []
            for row in response.data:
                request_id = row["id"]
                
                # Update status to expired
                self.supabase.table("doc_approval_requests").update({
                    "status": ApprovalStatus.EXPIRED.value,
                    "updated_at": now.isoformat()
                }).eq("id", request_id).execute()
                
                expired_ids.append(request_id)
            
            logger.info(f"Expired {len(expired_ids)} approval requests")
            return expired_ids
            
        except Exception as e:
            logger.error(f"Error expiring approval requests: {e}")
            raise
    
    async def _assign_reviewers(self, doc_type: str, author_id: str) -> List[str]:
        """Assign reviewers based on document type and availability."""
        try:
            # Get potential reviewers (excluding author)
            response = self.supabase.table("users").select("id, role").neq("id", author_id).execute()
            
            reviewers = []
            
            # Assign based on document type and user roles
            for user in response.data:
                role = user.get("role", "").lower()
                
                # Technical reviewers for API docs
                if doc_type == "api" and "developer" in role:
                    reviewers.append(user["id"])
                
                # Content reviewers for guides
                elif doc_type in ["guide", "tutorial"] and "manager" in role:
                    reviewers.append(user["id"])
                
                # Admin can review anything
                elif "admin" in role:
                    reviewers.append(user["id"])
            
            # Limit to 2-3 reviewers
            return reviewers[:3]
            
        except Exception as e:
            logger.warning(f"Error assigning reviewers: {e}")
            return []  # Return empty list if assignment fails
    
    async def _assign_approvers(self, doc_type: str, author_id: str) -> List[str]:
        """Assign approvers based on document type."""
        try:
            # Get users with approval permissions
            response = self.supabase.table("users").select("id, role").in_(
                "role", ["manager", "admin"]
            ).neq("id", author_id).execute()
            
            approvers = [user["id"] for user in response.data]
            
            # Limit to 1-2 approvers
            return approvers[:2]
            
        except Exception as e:
            logger.warning(f"Error assigning approvers: {e}")
            return []
    
    def _calculate_approval_status(self, request: ApprovalRequest) -> ApprovalStatus:
        """Calculate new approval status based on reviews."""
        if not request.reviews:
            return ApprovalStatus.PENDING
        
        # Count decisions
        approvals = sum(1 for review in request.reviews if review["decision"] == "approve")
        rejections = sum(1 for review in request.reviews if review["decision"] == "reject")
        change_requests = sum(1 for review in request.reviews if review["decision"] == "request_changes")
        
        # If any rejection, mark as rejected
        if rejections > 0:
            return ApprovalStatus.REJECTED
        
        # If any change requests, mark as needs review
        if change_requests > 0:
            return ApprovalStatus.NEEDS_REVIEW
        
        # Check if we have enough approvals
        required_approvals = max(1, len(request.approvers))
        approver_reviews = [r for r in request.reviews if r["reviewer_id"] in request.approvers]
        approver_approvals = sum(1 for review in approver_reviews if review["decision"] == "approve")
        
        if approver_approvals >= required_approvals:
            return ApprovalStatus.APPROVED
        
        return ApprovalStatus.PENDING
    
    async def _save_approval_request(self, request: ApprovalRequest) -> None:
        """Save approval request to database."""
        try:
            data = {
                "id": request.id,
                "document_id": request.document_id,
                "title": request.title,
                "content": request.content,
                "doc_type": request.doc_type,
                "author_id": request.author_id,
                "status": request.status.value,
                "quality_metrics": request.quality_metrics,
                "created_at": request.created_at.isoformat(),
                "updated_at": request.updated_at.isoformat(),
                "expires_at": request.expires_at.isoformat() if request.expires_at else None,
                "reviewers": request.reviewers,
                "approvers": request.approvers,
                "reviews": request.reviews,
                "slack_thread_id": request.slack_thread_id,
                "auto_approval_reason": request.auto_approval_reason
            }
            
            # Upsert (insert or update)
            self.supabase.table("doc_approval_requests").upsert(data).execute()
            
        except Exception as e:
            logger.error(f"Error saving approval request {request.id}: {e}")
            raise
    
    def _approval_request_from_db(self, data: Dict[str, Any]) -> ApprovalRequest:
        """Convert database row to ApprovalRequest object."""
        return ApprovalRequest(
            id=data["id"],
            document_id=data["document_id"],
            title=data["title"],
            content=data["content"],
            doc_type=data["doc_type"],
            author_id=data["author_id"],
            status=ApprovalStatus(data["status"]),
            quality_metrics=data.get("quality_metrics"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            reviewers=data.get("reviewers", []),
            approvers=data.get("approvers", []),
            reviews=data.get("reviews", []),
            slack_thread_id=data.get("slack_thread_id"),
            auto_approval_reason=data.get("auto_approval_reason")
        )
    
    async def _send_approval_notifications(self, request: ApprovalRequest) -> None:
        """Send notifications for new approval requests."""
        if not self.slack_webhook_url:
            logger.warning("Slack webhook not configured - skipping notifications")
            return
        
        try:
            # Get quality info
            quality_info = ""
            if request.quality_metrics:
                score = request.quality_metrics.get("overall_score", 0)
                level = request.quality_metrics.get("level", "unknown")
                quality_info = f"Quality Score: {score}/100 ({level})"
            
            # Create Slack message
            message = {
                "text": f"📝 Documentation Review Request: {request.title}",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"📝 Documentation Review: {request.title}"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Type:* {request.doc_type}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Author:* <@{request.author_id}>"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Expires:* {request.expires_at.strftime('%Y-%m-%d %H:%M') if request.expires_at else 'No expiration'}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": quality_info if quality_info else "*Quality:* Not assessed"
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Content Preview:*\n```{request.content[:300]}{'...' if len(request.content) > 300 else ''}```"
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "✅ Approve"
                                },
                                "style": "primary",
                                "value": f"approve_{request.id}"
                            },
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "❌ Reject"
                                },
                                "style": "danger",
                                "value": f"reject_{request.id}"
                            },
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "🔄 Request Changes"
                                },
                                "value": f"changes_{request.id}"
                            }
                        ]
                    }
                ]
            }
            
            # Send to Slack
            response = requests.post(self.slack_webhook_url, json=message, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Sent approval notification to Slack for request {request.id}")
            
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
            # Don't raise - notification failure shouldn't break the workflow
    
    async def _send_review_notifications(self, request: ApprovalRequest, review: ReviewDecision) -> None:
        """Send notifications when reviews are submitted."""
        if not self.slack_webhook_url:
            return
        
        try:
            decision_emoji = {
                "approve": "✅",
                "reject": "❌", 
                "request_changes": "🔄"
            }
            
            emoji = decision_emoji.get(review.decision, "📝")
            
            message = {
                "text": f"{emoji} Review submitted for: {request.title}",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{emoji} *Review Decision:* {review.decision.replace('_', ' ').title()}\n"
                                   f"*Document:* {request.title}\n"
                                   f"*Reviewer:* <@{review.reviewer_id}>\n"
                                   f"*Status:* {request.status.value.replace('_', ' ').title()}"
                        }
                    }
                ]
            }
            
            if review.comments:
                message["blocks"].append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Comments:*\n{review.comments}"
                    }
                })
            
            response = requests.post(self.slack_webhook_url, json=message, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Sent review notification to Slack for request {request.id}")
            
        except Exception as e:
            logger.error(f"Error sending review notification: {e}")


# Database schema for doc_approval_requests table
DOC_APPROVAL_REQUESTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS doc_approval_requests (
    id UUID PRIMARY KEY,
    document_id VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    content TEXT NOT NULL,
    doc_type VARCHAR NOT NULL,
    author_id UUID NOT NULL,
    status VARCHAR NOT NULL,
    quality_metrics JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    reviewers JSONB DEFAULT '[]',
    approvers JSONB DEFAULT '[]',
    reviews JSONB DEFAULT '[]',
    slack_thread_id VARCHAR,
    auto_approval_reason TEXT,
    
    FOREIGN KEY (author_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_doc_approval_requests_status ON doc_approval_requests(status);
CREATE INDEX IF NOT EXISTS idx_doc_approval_requests_author ON doc_approval_requests(author_id);
CREATE INDEX IF NOT EXISTS idx_doc_approval_requests_expires ON doc_approval_requests(expires_at);
"""