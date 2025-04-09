from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Dict, Any
import uuid

from app.models.user import User, UserRole

class UserRepository:
    """Repository for User model operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_user(self, slack_id: str, name: str, role: UserRole = UserRole.DEVELOPER, 
                   team: Optional[str] = None, personal_mastery: Optional[Dict] = None) -> User:
        """Create a new user record."""
        user = User(
            slack_id=slack_id,
            name=name,
            role=role,
            team=team,
            personal_mastery=personal_mastery
        )
        
        self.db.add(user)
        self.db.flush()  # Flush to get the ID
        return user
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_user_by_slack_id(self, slack_id: str) -> Optional[User]:
        """Get a user by Slack ID."""
        return self.db.query(User).filter(User.slack_id == slack_id).first()
    
    def list_users(self) -> List[User]:
        """List all users."""
        return self.db.query(User).all()
    
    def list_users_by_role(self, role: UserRole) -> List[User]:
        """List users by role."""
        return self.db.query(User).filter(User.role == role).all()
    
    def list_users_by_team(self, team: str) -> List[User]:
        """List users by team."""
        return self.db.query(User).filter(User.team == team).all()
    
    def update_user(self, user_id: str, **kwargs) -> Optional[User]:
        """Update user attributes."""
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        self.db.flush()
        return user
    
    def update_personal_mastery(self, user_id: str, personal_mastery: Dict) -> Optional[User]:
        """Update a user's personal mastery tasks/feedback."""
        return self.update_user(user_id, personal_mastery=personal_mastery)
    
    def delete_user(self, user_id: str) -> bool:
        """Delete a user by ID."""
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        
        self.db.delete(user)
        self.db.flush()
        return True