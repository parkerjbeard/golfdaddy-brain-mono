from typing import Dict, Any, Optional
import os
from dotenv import load_dotenv

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

# Create a global settings instance
settings = Settings()