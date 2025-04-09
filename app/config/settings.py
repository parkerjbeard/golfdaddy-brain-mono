from typing import Dict, Any, Optional, List
import os
from dotenv import load_dotenv
import json

class Settings:
    """Centralized configuration settings for the application.
    
    Loads environment variables from .env file or system environment.
    """
    
    def __init__(self):
        # Load environment variables from .env file if it exists
        load_dotenv()
        
        # Application mode
        self.testing_mode = os.getenv("TESTING_MODE", "False").lower() in ("true", "1", "t")
        
        # Database settings
        self.db_host = os.getenv("DB_HOST", "db")
        self.db_port = int(os.getenv("DB_PORT", "5432"))
        self.db_name = os.getenv("DB_NAME", "golfdaddy")
        self.db_user = os.getenv("DB_USER", "postgres")
        self.db_password = os.getenv("DB_PASSWORD", "postgres")
        
        # External service tokens
        self.slack_token = os.getenv("SLACK_TOKEN")
        self.slack_signing_secret = os.getenv("SLACK_SIGNING_SECRET")
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.clickup_token = os.getenv("CLICKUP_TOKEN")
        self.ai_service_key = os.getenv("AI_SERVICE_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", self.ai_service_key)
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4-0125-preview")
        
        # Specific AI models for different services
        self.commit_analysis_model = os.getenv("COMMIT_ANALYSIS_MODEL", self.openai_model)
        
        # API Gateway settings
        self.enable_api_auth = os.getenv("ENABLE_API_AUTH", "True").lower() in ("true", "1", "t")
        self.enable_rate_limiting = os.getenv("ENABLE_RATE_LIMITING", "True").lower() in ("true", "1", "t")
        self.api_key_header = os.getenv("API_KEY_HEADER", "X-API-Key")
        self.default_rate_limit = int(os.getenv("DEFAULT_RATE_LIMIT", "60"))  # Requests per minute
        
        # Load API keys from environment or config file
        self.api_keys = self._load_api_keys()
        
        # Paths excluded from API key verification
        self.auth_exclude_paths = self._parse_list_env("AUTH_EXCLUDE_PATHS", 
                                                      ["/docs", "/redoc", "/openapi.json", "/health"])
        
        # Paths excluded from rate limiting
        self.rate_limit_exclude_paths = self._parse_list_env("RATE_LIMIT_EXCLUDE_PATHS", 
                                                           ["/health"])
        
    def validate(self) -> bool:
        """Validate that all required environment variables are set."""
        # Skip validation in testing mode
        if self.testing_mode:
            return True
            
        required_vars = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", 
                        "SLACK_TOKEN", "GITHUB_TOKEN", "AI_SERVICE_KEY"]
        
        missing_vars = [var for var in required_vars if not getattr(self, self._convert_var_name(var), None)]
        
        if missing_vars:
            print(f"Missing required environment variables: {', '.join(missing_vars)}")
            return False
            
        return True
    
    def _convert_var_name(self, env_var: str) -> str:
        """Convert environment variable name to attribute name."""
        return env_var.lower()
        
    def _load_api_keys(self) -> Dict[str, Dict[str, Any]]:
        """Load API keys from environment or file."""
        # Check if API keys are defined in environment
        api_keys_env = os.getenv("API_KEYS")
        if api_keys_env:
            try:
                return json.loads(api_keys_env)
            except json.JSONDecodeError:
                print("Warning: Failed to parse API_KEYS environment variable")
        
        # Check if API keys file is defined
        api_keys_file = os.getenv("API_KEYS_FILE")
        if api_keys_file and os.path.exists(api_keys_file):
            try:
                with open(api_keys_file, 'r') as file:
                    return json.load(file)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load API keys from {api_keys_file}: {str(e)}")
        
        # Default to a test API key in development
        if os.getenv("ENVIRONMENT", "development") == "development":
            return {
                "dev-api-key": {
                    "owner": "development",
                    "role": "admin",
                    "rate_limit": 1000
                }
            }
        
        return {}
        
    def _parse_list_env(self, env_var: str, default: List[str]) -> List[str]:
        """Parse a comma-separated list from environment variable."""
        value = os.getenv(env_var)
        if value:
            return [item.strip() for item in value.split(",")]
        return default

# Create a global settings instance
settings = Settings()