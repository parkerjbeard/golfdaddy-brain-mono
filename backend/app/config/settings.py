import json
import logging
import os
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv
from pydantic import Field, HttpUrl, Json, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# Load .env file if it exists (for Render secret files)
# Check multiple possible locations
for env_path in [Path(".env"), Path("/etc/secrets/.env"), Path("/app/.env")]:
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded environment from {env_path}")
        break
else:
    # Also try loading without a specific path (uses default search)
    load_dotenv()


class Settings(BaseSettings):
    # Supabase Config
    SUPABASE_URL: HttpUrl = Field(..., env="SUPABASE_URL")
    SUPABASE_SERVICE_KEY: str = Field(..., env="SUPABASE_SERVICE_KEY")
    SUPABASE_ANON_KEY: Optional[str] = Field(
        None, env="SUPABASE_ANON_KEY"
    )  # Public key, needed for client-side JS/frontend

    # PostgreSQL Database URL (for SQLAlchemy)
    DATABASE_URL: str = Field(..., env="DATABASE_URL")

    # General App Settings
    TESTING_MODE: bool = Field(False, env="TESTING_MODE")  # Added for testing purposes
    REANALYZE_EXISTING_COMMITS: bool = Field(
        False, env="REANALYZE_EXISTING_COMMITS"
    )  # Controls whether to reprocess commits already in the database
    FRONTEND_URL: str = Field("http://localhost:8080", env="FRONTEND_URL")  # Frontend URL for links in notifications

    # Documentation agent removed — related config deleted

    # Slack Config
    SLACK_BOT_TOKEN: Optional[str] = Field(None, env="SLACK_BOT_TOKEN")  # Bot user OAuth token
    SLACK_SIGNING_SECRET: Optional[str] = Field(None, env="SLACK_SIGNING_SECRET")
    SLACK_DEFAULT_CHANNEL: Optional[str] = Field(None, env="SLACK_DEFAULT_CHANNEL")  # Default channel for notifications

    # Slack Circuit Breaker Settings
    SLACK_CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = Field(5, env="SLACK_CIRCUIT_BREAKER_FAILURE_THRESHOLD")
    SLACK_CIRCUIT_BREAKER_TIMEOUT: int = Field(60, env="SLACK_CIRCUIT_BREAKER_TIMEOUT")

    # EOD Reminder Settings
    EOD_REMINDER_TIME: str = Field("16:30", env="EOD_REMINDER_TIME")  # 24-hour format (4:30 PM)
    EOD_REMINDER_TIMEZONE: str = Field("America/Los_Angeles", env="EOD_REMINDER_TIMEZONE")

    # Integration Keys
    GITHUB_TOKEN: Optional[str] = Field(None, env="GITHUB_TOKEN")  # Legacy PAT, prefer GitHub App
    AI_SERVICE_KEY: Optional[str] = Field(None, env="AI_SERVICE_KEY")
    # Optional legacy integration key support (env: MAKE_INTEGRATION_API_KEY)

    # GitHub App Configuration (preferred over PAT)
    GITHUB_APP_ID: Optional[str] = Field(None, env="GITHUB_APP_ID")
    GITHUB_APP_PRIVATE_KEY: Optional[str] = Field(None, env="GITHUB_APP_PRIVATE_KEY")
    GITHUB_APP_INSTALLATION_ID: Optional[str] = Field(None, env="GITHUB_APP_INSTALLATION_ID")

    # GitHub Webhook Configuration
    GITHUB_WEBHOOK_SECRET: Optional[str] = Field(None, env="GITHUB_WEBHOOK_SECRET")

    # Legacy integration/webhook values (optional). Defining to avoid AttributeError when accessed via properties.
    MAKE_INTEGRATION_API_KEY: Optional[str] = Field(None, env="MAKE_INTEGRATION_API_KEY")
    MAKE_WEBHOOK_TASK_CREATED: Optional[str] = Field(None, env="MAKE_WEBHOOK_TASK_CREATED")
    MAKE_WEBHOOK_TASK_BLOCKED: Optional[str] = Field(None, env="MAKE_WEBHOOK_TASK_BLOCKED")
    MAKE_WEBHOOK_EOD_REMINDER: Optional[str] = Field(None, env="MAKE_WEBHOOK_EOD_REMINDER")
    MAKE_WEBHOOK_MASTERY_REMINDER: Optional[str] = Field(None, env="MAKE_WEBHOOK_MASTERY_REMINDER")

    # Legacy webhook URL placeholders removed; direct Slack messages are generally disabled

    # OpenAI settings
    OPENAI_API_KEY: Optional[str] = Field(None, env="OPENAI_API_KEY")
    OPENAI_MODEL: Optional[str] = Field("gpt-5-2025-08-07", env="OPENAI_MODEL")
    # Doc agent model removed
    OPENAI_REASONING_EFFORT: str = Field("medium", env="OPENAI_REASONING_EFFORT")

    # Service-specific AI models
    COMMIT_ANALYSIS_MODEL: Optional[str] = Field("gpt-5-2025-08-07", env="COMMIT_ANALYSIS_MODEL")
    CODE_QUALITY_MODEL: Optional[str] = Field("gpt-5-2025-08-07", env="CODE_QUALITY_MODEL")

    # Health check toggles
    HEALTH_CHECK_TIMEOUT: int = Field(10, env="HEALTH_CHECK_TIMEOUT")
    ENABLE_DETAILED_HEALTH_CHECKS: bool = Field(False, env="ENABLE_DETAILED_HEALTH_CHECKS")

    # Embeddings/semantic search removed — related config deleted

    # Data Retention and Archiving Settings
    DAILY_REPORTS_RETENTION_MONTHS: int = Field(12, env="DAILY_REPORTS_RETENTION_MONTHS")
    COMMITS_RETENTION_MONTHS: int = Field(24, env="COMMITS_RETENTION_MONTHS")
    COMPLETED_TASKS_RETENTION_MONTHS: int = Field(6, env="COMPLETED_TASKS_RETENTION_MONTHS")
    # Docs retention removed with doc agent
    ENABLE_AUTO_ARCHIVE: bool = Field(True, env="ENABLE_AUTO_ARCHIVE")
    ARCHIVE_SCHEDULE_HOUR: int = Field(2, env="ARCHIVE_SCHEDULE_HOUR")  # Run at 2 AM daily

    # Zapier Integration Settings
    ZAPIER_WEEKLY_ANALYTICS_URL: Optional[str] = Field(None, env="ZAPIER_WEEKLY_ANALYTICS_URL")
    ZAPIER_OBJECTIVES_URL: Optional[str] = Field(None, env="ZAPIER_OBJECTIVES_URL")
    ZAPIER_API_KEY: Optional[str] = Field(None, env="ZAPIER_API_KEY")

    # Zapier Webhook Settings
    ZAPIER_API_KEYS: Optional[str] = Field(None, env="ZAPIER_API_KEYS")  # Comma-separated list of valid API keys
    ZAPIER_WEBHOOK_SECRET: Optional[str] = Field(None, env="ZAPIER_WEBHOOK_SECRET")  # For HMAC signature verification
    ZAPIER_REQUIRE_AUTH: bool = Field(True, env="ZAPIER_REQUIRE_AUTH")  # Require authentication for webhooks
    ENVIRONMENT: str = Field("production", env="ENVIRONMENT")  # development, staging, production

    # API Gateway Settings
    ENABLE_API_AUTH: bool = Field(True, env="ENABLE_API_AUTH")
    ENABLE_RATE_LIMITING: bool = Field(True, env="ENABLE_RATE_LIMITING")
    API_KEY_HEADER: str = Field("X-API-Key", env="API_KEY_HEADER")
    DEFAULT_RATE_LIMIT: int = Field(60, env="DEFAULT_RATE_LIMIT")  # requests per minute
    AUTH_EXCLUDE_PATHS: str = Field(
        "/docs,/redoc,/openapi.json,/health,/auth/login", env="AUTH_EXCLUDE_PATHS"
    )  # Adjusted exclude paths
    RATE_LIMIT_EXCLUDE_PATHS: str = Field(
        "/health,/auth/login", env="RATE_LIMIT_EXCLUDE_PATHS"
    )  # Adjusted exclude paths
    API_KEYS: Optional[Dict[str, Dict[str, Any]]] = Field(None, env="API_KEYS")
    API_KEYS_FILE_PATH: Optional[str] = Field(None, env="API_KEYS_FILE_PATH")

    # CORS Settings removed — unified same-origin deployment

    @field_validator("API_KEYS", mode="before")
    @classmethod
    def load_and_merge_api_keys(cls, v, info):
        """
        Load API keys from file and merge with environment variables.
        Priority: Environment variables override file values.
        """
        # Get file path from environment since it might not be in info.data yet
        file_path = os.environ.get("API_KEYS_FILE_PATH")

        # Start with keys from file if path is provided
        file_keys = {}
        if file_path:
            try:
                file_path_obj = Path(file_path)
                if file_path_obj.exists():
                    logger.info(f"Loading API keys from file: {file_path}")

                    with open(file_path_obj, "r") as f:
                        if file_path_obj.suffix.lower() in [".yaml", ".yml"]:
                            file_keys = yaml.safe_load(f) or {}
                        else:  # Default to JSON
                            file_keys = json.load(f)

                    logger.info(f"Loaded {len(file_keys)} API keys from file")
                else:
                    logger.warning(f"API keys file not found: {file_path}")
            except Exception as e:
                logger.error(f"Error loading API keys file {file_path}: {e}")
                file_keys = {}

        # Parse environment variable keys (if provided)
        env_keys = {}
        if v:
            if isinstance(v, str):
                try:
                    env_keys = json.loads(v)
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing API_KEYS environment variable: {e}")
                    env_keys = {}
            elif isinstance(v, dict):
                env_keys = v

        # Merge keys: environment variables override file values
        merged_keys = {**file_keys, **env_keys}

        # Validate key structure
        validated_keys = {}
        for key, config in merged_keys.items():
            if isinstance(config, dict):
                validated_keys[key] = config
            else:
                logger.warning(f"Invalid API key config for '{key}': expected dict, got {type(config)}")

        logger.info(f"Final API keys count: {len(validated_keys)}")
        return validated_keys if validated_keys else None

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
    def slack_bot_token(self):
        return self.SLACK_BOT_TOKEN

    @property
    def slack_default_channel(self):
        return self.SLACK_DEFAULT_CHANNEL

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
    def github_webhook_secret(self):
        return self.GITHUB_WEBHOOK_SECRET

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
    def api_keys_file_path(self):
        return self.API_KEYS_FILE_PATH

    @property
    # CORS accessors removed

    @property
    # Documentation agent accessors removed

    @property
    def testing_mode(self):  # Added property for convenient access
        return self.TESTING_MODE

    @property
    def database_url(self):
        return self.DATABASE_URL

    @property
    def reanalyze_existing_commits(self):
        return self.REANALYZE_EXISTING_COMMITS

    @property
    # Doc agent model accessor removed

    @property
    def daily_reports_retention_months(self):
        return self.DAILY_REPORTS_RETENTION_MONTHS

    @property
    def commits_retention_months(self):
        return self.COMMITS_RETENTION_MONTHS

    @property
    def completed_tasks_retention_months(self):
        return self.COMPLETED_TASKS_RETENTION_MONTHS

    @property
    # Docs retention accessor removed

    @property
    def enable_auto_archive(self):
        return self.ENABLE_AUTO_ARCHIVE

    @property
    def archive_schedule_hour(self):
        return self.ARCHIVE_SCHEDULE_HOUR

    @property
    def slack_circuit_breaker_failure_threshold(self):
        return self.SLACK_CIRCUIT_BREAKER_FAILURE_THRESHOLD

    @property
    def slack_circuit_breaker_timeout(self):
        return self.SLACK_CIRCUIT_BREAKER_TIMEOUT

    @property
    # Documentation OpenAI model accessor removed

    @property
    def openai_reasoning_effort(self):
        return self.OPENAI_REASONING_EFFORT

    @property
    def frontend_url(self):
        return self.FRONTEND_URL

    # Daily Batch Analysis Settings
    ENABLE_DAILY_BATCH_ANALYSIS: bool = True
    SKIP_INDIVIDUAL_COMMIT_ANALYSIS: bool = False  # Keep individual analysis by default for backward compatibility

    # EOD Reminder Settings
    ENABLE_EOD_REMINDERS: bool = True
    EOD_REMINDER_HOUR: int = 17  # 5 PM
    EOD_REMINDER_MINUTE: int = 30  # 5:30 PM
    SKIP_WEEKEND_REMINDERS: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra fields from environment


# Create a single instance for easy import
settings = Settings()


# Function to get settings instance
def get_settings() -> Settings:
    return settings
