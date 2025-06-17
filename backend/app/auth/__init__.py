"""Authentication module for Supabase-based authentication."""

from app.auth.dependencies import get_current_user, get_admin_user

__all__ = ["get_current_user", "get_admin_user"] 