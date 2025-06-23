"""
Local user repository for development that uses PostgreSQL instead of Supabase.
This allows us to test without needing Supabase database access.
"""
import asyncio
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.db.database import SessionLocal
import logging
from datetime import datetime
from app.core.exceptions import DatabaseError, ResourceNotFoundError

logger = logging.getLogger(__name__)

class LocalUserRepository:
    def __init__(self):
        self._table = "users"

    def _get_db(self) -> Session:
        """Get a database session."""
        return SessionLocal()

    def _row_to_user(self, row: Any) -> User:
        """Convert a database row to a User model."""
        return User(
            id=row.id,
            email=row.email,
            name=row.name,
            slack_id=row.slack_id,
            team=row.team,
            role=UserRole(row.role),
            avatar_url=row.avatar_url,
            metadata=row.metadata or {},
            created_at=row.created_at,
            updated_at=row.updated_at,
            github_username=row.github_username,
            team_id=row.team_id,
            reports_to_id=row.reports_to_id,
            personal_mastery=row.personal_mastery or {},
            last_login_at=row.last_login_at,
            is_active=row.is_active,
            preferences=row.preferences or {}
        )

    async def create_user(self, user_data: User) -> Optional[User]:
        """Creates a new user profile record in the database."""
        db = self._get_db()
        try:
            # Convert User model to dict for insertion
            user_dict = {
                'id': str(user_data.id),
                'email': user_data.email,
                'name': user_data.name,
                'slack_id': user_data.slack_id,
                'team': user_data.team,
                'role': user_data.role.value if isinstance(user_data.role, UserRole) else user_data.role,
                'avatar_url': user_data.avatar_url,
                'metadata': user_data.metadata,
                'github_username': user_data.github_username,
                'team_id': str(user_data.team_id) if user_data.team_id else None,
                'reports_to_id': str(user_data.reports_to_id) if user_data.reports_to_id else None,
                'personal_mastery': user_data.personal_mastery,
                'is_active': user_data.is_active,
                'preferences': user_data.preferences
            }
            
            # Use raw SQL for simplicity
            query = text("""
                INSERT INTO users (
                    id, email, name, slack_id, team, role, avatar_url, 
                    metadata, github_username, team_id, reports_to_id, 
                    personal_mastery, is_active, preferences
                ) VALUES (
                    :id, :email, :name, :slack_id, :team, :role, :avatar_url,
                    :metadata, :github_username, :team_id, :reports_to_id,
                    :personal_mastery, :is_active, :preferences
                ) RETURNING *
            """)
            
            result = db.execute(query, user_dict)
            db.commit()
            
            row = result.fetchone()
            if row:
                logger.info(f"Successfully created user profile for ID: {row.id}")
                return self._row_to_user(row)
            else:
                raise DatabaseError("Failed to create user profile: No data returned.")
                
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating user profile: {e}", exc_info=True)
            raise DatabaseError(f"Error creating user profile: {str(e)}")
        finally:
            db.close()

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Retrieves a user by their UUID."""
        db = self._get_db()
        try:
            query = text("SELECT * FROM users WHERE id = :user_id")
            result = db.execute(query, {"user_id": str(user_id)})
            row = result.fetchone()
            
            if row:
                return self._row_to_user(row)
            else:
                logger.info(f"User with ID {user_id} not found.")
                return None
                
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"Error getting user by ID {user_id}: {str(e)}")
        finally:
            db.close()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Retrieves a user by their email."""
        db = self._get_db()
        try:
            query = text("SELECT * FROM users WHERE email = :email")
            result = db.execute(query, {"email": email})
            row = result.fetchone()
            
            if row:
                return self._row_to_user(row)
            else:
                logger.info(f"User with email {email} not found.")
                return None
                
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}", exc_info=True)
            raise DatabaseError(f"Error getting user by email {email}: {str(e)}")
        finally:
            db.close()

    async def update_user(self, user_id: UUID, update_data: Dict[str, Any]) -> Optional[User]:
        """Updates a user's profile."""
        db = self._get_db()
        try:
            # Build SET clause dynamically
            set_clauses = []
            params = {"user_id": str(user_id)}
            
            for key, value in update_data.items():
                if key not in ['id', 'created_at']:  # Don't update these fields
                    set_clauses.append(f"{key} = :{key}")
                    if isinstance(value, UUID):
                        params[key] = str(value)
                    elif isinstance(value, UserRole):
                        params[key] = value.value
                    else:
                        params[key] = value
            
            if not set_clauses:
                return await self.get_user_by_id(user_id)
            
            query = text(f"""
                UPDATE users 
                SET {', '.join(set_clauses)}, updated_at = NOW()
                WHERE id = :user_id
                RETURNING *
            """)
            
            result = db.execute(query, params)
            db.commit()
            
            row = result.fetchone()
            if row:
                logger.info(f"Successfully updated user {user_id}")
                return self._row_to_user(row)
            else:
                return None
                
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"Error updating user {user_id}: {str(e)}")
        finally:
            db.close()

    async def get_all_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        """Retrieves all users with pagination."""
        # Use asyncio.to_thread for blocking database operations
        def _get_users():
            db = self._get_db()
            try:
                query = text("SELECT * FROM users ORDER BY created_at DESC LIMIT :limit OFFSET :offset")
                result = db.execute(query, {"limit": limit, "offset": offset})
                rows = result.fetchall()
                return [self._row_to_user(row) for row in rows]
            except Exception as e:
                logger.error(f"Error getting all users: {e}", exc_info=True)
                raise DatabaseError(f"Error getting all users: {str(e)}")
            finally:
                db.close()
        
        return await asyncio.to_thread(_get_users)

    async def get_users_by_role(self, role: UserRole) -> List[User]:
        """Retrieves users by role."""
        def _get_users_by_role():
            db = self._get_db()
            try:
                query = text("SELECT * FROM users WHERE role = :role ORDER BY created_at DESC")
                result = db.execute(query, {"role": role.value})
                rows = result.fetchall()
                return [self._row_to_user(row) for row in rows]
            except Exception as e:
                logger.error(f"Error getting users by role {role}: {e}", exc_info=True)
                raise DatabaseError(f"Error getting users by role {role}: {str(e)}")
            finally:
                db.close()
        
        return await asyncio.to_thread(_get_users_by_role)