"""
Slack service for direct API integration.
Replaces Make.com webhooks with native Slack API calls.
"""
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from functools import lru_cache

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.repositories.user_repository import UserRepository
from app.models.user import User

logger = logging.getLogger(__name__)


class SlackService:
    """Service for direct Slack API integration."""
    
    def __init__(self):
        self.client = WebClient(token=settings.SLACK_BOT_TOKEN)
        
        # Create circuit breaker config
        circuit_config = CircuitBreakerConfig(
            failure_threshold=settings.SLACK_CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            timeout=settings.SLACK_CIRCUIT_BREAKER_TIMEOUT,
            name="slack_api"
        )
        self.circuit_breaker = CircuitBreaker(circuit_config)
        
        self.user_repository = UserRepository()
        self._user_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = timedelta(hours=1)
        
    async def send_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
        thread_ts: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Send a message to Slack channel or thread."""
        try:
            with self.circuit_breaker:
                response = self.client.chat_postMessage(
                    channel=channel,
                    text=text,
                    blocks=blocks,
                    thread_ts=thread_ts
                )
                logger.info(f"Message sent to channel {channel}")
                return response.data
        except SlackApiError as e:
            logger.error(f"Failed to send Slack message: {e.response['error']}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error sending Slack message: {str(e)}")
            return None
    
    async def send_direct_message(
        self,
        user_id: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """Send a direct message to a Slack user."""
        try:
            # Open a conversation with the user
            with self.circuit_breaker:
                conversation = self.client.conversations_open(users=[user_id])
                channel_id = conversation["channel"]["id"]
                
                return await self.send_message(
                    channel=channel_id,
                    text=text,
                    blocks=blocks
                )
        except SlackApiError as e:
            logger.error(f"Failed to send DM to user {user_id}: {e.response['error']}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error sending DM: {str(e)}")
            return None
    
    async def find_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Find Slack user by email address."""
        # Check cache first
        cache_key = f"email:{email}"
        if cache_key in self._user_cache:
            cached = self._user_cache[cache_key]
            if datetime.now() - cached['timestamp'] < self._cache_ttl:
                return cached['data']
        
        try:
            with self.circuit_breaker:
                response = self.client.users_lookupByEmail(email=email)
                user_data = response["user"]
                
                # Cache the result
                self._user_cache[cache_key] = {
                    'data': user_data,
                    'timestamp': datetime.now()
                }
                
                return user_data
        except SlackApiError as e:
            if e.response['error'] == 'users_not_found':
                logger.warning(f"No Slack user found with email: {email}")
            else:
                logger.error(f"Error looking up user by email: {e.response['error']}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error finding user: {str(e)}")
            return None
    
    async def find_user_by_github_username(
        self,
        github_username: str,
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """Find Slack user by GitHub username via database mapping."""
        # Check cache first
        cache_key = f"github:{github_username}"
        if cache_key in self._user_cache:
            cached = self._user_cache[cache_key]
            if datetime.now() - cached['timestamp'] < self._cache_ttl:
                return cached['data']
        
        try:
            # Look up user in our database
            user = await self.user_repository.get_by_github_username(db, github_username)
            if not user or not user.email:
                logger.warning(f"No user found with GitHub username: {github_username}")
                return None
            
            # Find Slack user by email
            slack_user = await self.find_user_by_email(user.email)
            if slack_user:
                # Cache the GitHub -> Slack mapping
                self._user_cache[cache_key] = {
                    'data': slack_user,
                    'timestamp': datetime.now()
                }
            
            return slack_user
        except Exception as e:
            logger.error(f"Error finding user by GitHub username: {str(e)}")
            return None
    
    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get Slack user information by user ID."""
        # Check cache first
        cache_key = f"id:{user_id}"
        if cache_key in self._user_cache:
            cached = self._user_cache[cache_key]
            if datetime.now() - cached['timestamp'] < self._cache_ttl:
                return cached['data']
        
        try:
            with self.circuit_breaker:
                response = self.client.users_info(user=user_id)
                user_data = response["user"]
                
                # Cache the result
                self._user_cache[cache_key] = {
                    'data': user_data,
                    'timestamp': datetime.now()
                }
                
                return user_data
        except SlackApiError as e:
            logger.error(f"Failed to get user info: {e.response['error']}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting user info: {str(e)}")
            return None
    
    def clear_cache(self):
        """Clear the user cache."""
        self._user_cache.clear()
        logger.info("Slack user cache cleared")
    
    def _format_user_mention(self, user_id: str) -> str:
        """Format a user mention for Slack."""
        return f"<@{user_id}>"
    
    def _format_channel_mention(self, channel_id: str) -> str:
        """Format a channel mention for Slack."""
        return f"<#{channel_id}>"
    
    def _format_link(self, url: str, text: str) -> str:
        """Format a link for Slack markdown."""
        return f"<{url}|{text}>"
    
    async def open_dm(self, user_id: str) -> Optional[str]:
        """Open a DM channel with a user and return the channel ID."""
        try:
            with self.circuit_breaker:
                response = self.client.conversations_open(users=user_id)
                if response["ok"]:
                    return response["channel"]["id"]
                return None
        except SlackApiError as e:
            logger.error(f"Failed to open DM with user {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error opening DM: {e}")
            return None
    
    async def send_response_url_message(
        self,
        response_url: str,
        message: Dict[str, Any]
    ) -> bool:
        """Send a message using a Slack response URL."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(response_url, json=message) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.error(f"Failed to send response URL message: {e}")
            return False
    
    async def schedule_message(
        self,
        channel: str,
        post_at: int,  # Unix timestamp
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[str]:
        """Schedule a message to be sent at a specific time."""
        try:
            with self.circuit_breaker:
                response = self.client.chat_scheduleMessage(
                    channel=channel,
                    post_at=post_at,
                    text=text,
                    blocks=blocks
                )
                if response["ok"]:
                    return response["scheduled_message_id"]
                return None
        except SlackApiError as e:
            logger.error(f"Failed to schedule message: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error scheduling message: {e}")
            return None