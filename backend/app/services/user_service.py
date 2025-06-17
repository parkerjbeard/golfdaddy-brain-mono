from typing import Dict, Any, Optional
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

    async def update_user(self, user_id: UUID, data: Dict[str, Any]) -> Optional[User]:
        return await self.user_repo.update_user(user_id, data)

    async def delete_user(self, user_id: UUID) -> bool:
        return await self.user_repo.delete_user(user_id)

    async def change_password(self, user_id: UUID, new_password: str) -> bool:
        """Placeholder for password change logic."""
        # TODO: integrate with authentication provider to change password
        return False
