from typing import Dict, Any, Optional, List
from uuid import UUID

from app.models.user import User
from app.repositories.user_repository import UserRepository


class UserService:
    """Business logic layer for user operations."""

    def __init__(self) -> None:
        self.user_repo = UserRepository()

    async def create_user(self, user_in: User) -> Optional[User]:
        return await self.user_repo.create_user(user_in)

    async def get_user(self, user_id: UUID) -> Optional[User]:
        return await self.user_repo.get_user_by_id(user_id)

    async def get_user_by_slack_id(self, slack_id: str) -> Optional[User]:
        return await self.user_repo.get_user_by_slack_id(slack_id)

    async def update_user(self, user_id: UUID, data: Dict[str, Any]) -> Optional[User]:
        return await self.user_repo.update_user(user_id, data)

    async def delete_user(self, user_id: UUID) -> bool:
        return await self.user_repo.delete_user(user_id)

    async def change_password(self, user_id: UUID, new_password: str) -> bool:
        """Placeholder for password change logic."""
        # TODO: integrate with authentication provider to change password
        return False
    
    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID (alias for get_user)."""
        return await self.get_user(user_id)
    
    async def get_all_active_users(self) -> List[User]:
        """Get all active users with Slack IDs configured."""
        all_users, _ = await self.user_repo.list_all_users(limit=1000)
        # Filter for active users with Slack IDs
        active_users = []
        for user in all_users:
            if user.slack_id and user.is_active:
                active_users.append(user)
        return active_users
