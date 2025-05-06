from pydantic_settings import BaseSettings
from pydantic import Field, HttpUrl, Json
from typing import Dict, Any, List, Optional
import os
from dotenv import load_dotenv
import json
import secrets

class Settings(BaseSettings):
    # Supabase Config
    SUPABASE_URL: HttpUrl = Field(..., env="SUPABASE_URL")
    SUPABASE_SERVICE_KEY: str = Field(..., env="SUPABASE_SERVICE_KEY")
    SUPABASE_ANON_KEY: Optional[str] = Field(None, env="SUPABASE_ANON_KEY") # Public key, needed for client-side JS/frontend

    # General App Settings
    TESTING_MODE: bool = Field(False, env="TESTING_MODE") # Added for testing purposes

    # Documentation Config
    DOCS_REPOSITORY: Optional[str] = Field(None, env="DOCS_REPOSITORY")  # Format: owner/repo
    ENABLE_DOCS_UPDATES: bool = Field(False, env="ENABLE_DOCS_UPDATES")  # Whether to enable documentation scanning

    # Slack Config (Keep ONLY if needed for non-auth integrations)
    SLACK_TOKEN: Optional[str] = Field(None, env="SLACK_TOKEN")
    SLACK_SIGNING_SECRET: Optional[str] = Field(None, env="SLACK_SIGNING_SECRET")

    # Integration Keys
    GITHUB_TOKEN: Optional[str] = Field(None, env="GITHUB_TOKEN")
    AI_SERVICE_KEY: Optional[str] = Field(None, env="AI_SERVICE_KEY")
    MAKE_INTEGRATION_API_KEY: Optional[str] = Field(None, env="MAKE_INTEGRATION_API_KEY")

    # Make.com Webhook URLs
    MAKE_WEBHOOK_TASK_CREATED: Optional[str] = Field(None, env="MAKE_WEBHOOK_TASK_CREATED")
    MAKE_WEBHOOK_TASK_BLOCKED: Optional[str] = Field(None, env="MAKE_WEBHOOK_TASK_BLOCKED")
    MAKE_WEBHOOK_EOD_REMINDER: Optional[str] = Field(None, env="MAKE_WEBHOOK_EOD_REMINDER")
    MAKE_WEBHOOK_MASTERY_REMINDER: Optional[str] = Field(None, env="MAKE_WEBHOOK_MASTERY_REMINDER")

    # OpenAI settings
    OPENAI_API_KEY: Optional[str] = Field(None, env="OPENAI_API_KEY")
    OPENAI_MODEL: Optional[str] = Field("gpt-4.1-2025-04-14", env="OPENAI_MODEL")
    DOCUMENTATION_OPENAI_MODEL: Optional[str] = Field("gpt-4.1-2025-04-14", env="DOCUMENTATION_OPENAI_MODEL")

    # Service-specific AI models
    COMMIT_ANALYSIS_MODEL: Optional[str] = Field("o3-mini-2025-01-31", env="COMMIT_ANALYSIS_MODEL")
    CODE_QUALITY_MODEL: Optional[str] = Field("gpt-4o-mini", env="CODE_QUALITY_MODEL") # Default to gpt-4o-mini if not set

    # API Gateway Settings
    ENABLE_API_AUTH: bool = Field(True, env="ENABLE_API_AUTH")
    ENABLE_RATE_LIMITING: bool = Field(True, env="ENABLE_RATE_LIMITING")
    API_KEY_HEADER: str = Field("X-API-Key", env="API_KEY_HEADER")
    DEFAULT_RATE_LIMIT: int = Field(60, env="DEFAULT_RATE_LIMIT") # requests per minute
    AUTH_EXCLUDE_PATHS: str = Field("/docs,/redoc,/openapi.json,/health,/auth/login", env="AUTH_EXCLUDE_PATHS") # Adjusted exclude paths
    RATE_LIMIT_EXCLUDE_PATHS: str = Field("/health,/auth/login", env="RATE_LIMIT_EXCLUDE_PATHS") # Adjusted exclude paths
    API_KEYS: Optional[Json[Dict[str, Dict[str, Any]]]] = Field(None, env="API_KEYS")
    API_KEYS_FILE: Optional[str] = Field(None, env="API_KEYS_FILE")

    # Property aliases for consistent case access
    @property
    def supabase_url(self):
        return str(self.SUPABASE_URL)
    
    @property
    def supabase_service_key(self):
        return self.SUPABASE_SERVICE_KEY
    
    @property
    def supabase_anon_key(self):
        return self.SUPABASE_ANON_KEY
    
    @property
    def slack_token(self):
        return self.SLACK_TOKEN
    
    @property
    def slack_signing_secret(self):
        return self.SLACK_SIGNING_SECRET
    
    @property
    def github_token(self):
        return self.GITHUB_TOKEN
    
    @property
    def ai_service_key(self):
        return self.AI_SERVICE_KEY
    
    @property
    def make_integration_api_key(self):
        return self.MAKE_INTEGRATION_API_KEY

    @property
    def make_webhook_task_created(self):
        return self.MAKE_WEBHOOK_TASK_CREATED

    @property
    def make_webhook_task_blocked(self):
        return self.MAKE_WEBHOOK_TASK_BLOCKED

    @property
    def make_webhook_eod_reminder(self):
        return self.MAKE_WEBHOOK_EOD_REMINDER

    @property
    def make_webhook_mastery_reminder(self):
        return self.MAKE_WEBHOOK_MASTERY_REMINDER

    @property
    def openai_api_key(self):
        return self.OPENAI_API_KEY

    @property
    def openai_model(self):
        return self.OPENAI_MODEL

    @property
    def commit_analysis_model(self):
        return self.COMMIT_ANALYSIS_MODEL
    
    @property
    def code_quality_model(self):
        return self.CODE_QUALITY_MODEL
    
    @property
    def enable_api_auth(self):
        return self.ENABLE_API_AUTH
    
    @property
    def enable_rate_limiting(self):
        return self.ENABLE_RATE_LIMITING
    
    @property
    def api_key_header(self):
        return self.API_KEY_HEADER
    
    @property
    def default_rate_limit(self):
        return self.DEFAULT_RATE_LIMIT
    
    @property
    def auth_exclude_paths(self):
        return self.AUTH_EXCLUDE_PATHS
    
    @property
    def rate_limit_exclude_paths(self):
        return self.RATE_LIMIT_EXCLUDE_PATHS
    
    @property
    def api_keys(self):
        return self.API_KEYS
    
    @property
    def api_keys_file(self):
        return self.API_KEYS_FILE
    
    @property
    def docs_repository(self):
        return self.DOCS_REPOSITORY
    
    @property
    def enable_docs_updates(self):
        return self.ENABLE_DOCS_UPDATES

    @property
    def testing_mode(self): # Added property for convenient access
        return self.TESTING_MODE

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        extra = 'ignore' # Ignore extra fields from environment

# Create a single instance for easy import
settings = Settings()